"""
RTH-LM adapter for governed execution from Jarvis.

Actions are proposal-first:
- checkpoint_probe: inspect checkpoint metadata (step/loss/tensor counts)
- launch_interactive: start ZETAGRID_INFERENCE.py as background job
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import subprocess
import tempfile

from .permissions import permission_gate, Capability, RiskLevel
from .memory_vault import memory_vault
from .pathmap import map_path

logger = logging.getLogger(__name__)

ROOT_CANDIDATES = [
    Path("E:/ZETAGRID"),
    Path("E:/zetagrid"),
    Path("E:/ZetaGrid"),
]

INFERENCE_SCRIPT = "ZETAGRID_INFERENCE.py"
GENOME_FILE = "zetagrid_25b_production.npy"
CHECKPOINT_FILE = "zeta25b_step15000.pt"
GGUF_FILE = "rth_lm_25b_v1.gguf"

ACTION_KEYS = {"checkpoint_probe", "launch_interactive"}


class RTHLMAdapter:
    def __init__(self):
        self.active_jobs: Dict[str, Dict[str, Any]] = {}

    def status(self) -> Dict[str, Any]:
        root = self._resolve_root()
        artifacts = self._artifact_map(root)
        return {
            "module": "rth_lm_adapter",
            "root": str(root) if root else None,
            "root_candidates": [str(x) for x in ROOT_CANDIDATES],
            "artifacts": artifacts,
            "ready_for_probe": bool(artifacts.get("checkpoint", {}).get("exists")),
            "ready_for_interactive": bool(
                artifacts.get("script", {}).get("exists")
                and artifacts.get("genome", {}).get("exists")
            ),
            "jobs": self.jobs(),
        }

    def propose(
        self,
        action: str,
        reason: str,
        prompt: Optional[str] = None,
        max_new: int = 256,
        temperature: float = 0.7,
        top_k: int = 40,
        top_p: float = 0.9,
    ) -> Dict[str, Any]:
        action = str(action or "").strip().lower()
        if action not in ACTION_KEYS:
            raise ValueError(f"Unsupported action: {action}")

        root = self._resolve_root()
        if not root:
            raise FileNotFoundError("ZETAGRID root not found on E:/")
        artifacts = self._artifact_map(root)

        if action == "checkpoint_probe" and not artifacts["checkpoint"]["exists"]:
            raise FileNotFoundError("Checkpoint file not found")

        if action == "launch_interactive":
            if not artifacts["script"]["exists"]:
                raise FileNotFoundError("Inference script not found")
            if not artifacts["genome"]["exists"]:
                raise FileNotFoundError("Genome file not found")

        risk = RiskLevel.MEDIUM if action == "checkpoint_probe" else RiskLevel.HIGH
        scope = {
            "action": action,
            "root": str(root),
            "script_path": str(root / INFERENCE_SCRIPT),
            "checkpoint_path": str(root / CHECKPOINT_FILE),
            "genome_path": str(root / GENOME_FILE),
            "gguf_path": str(root / GGUF_FILE),
            "prompt": prompt,
            "max_new": int(max_new),
            "temperature": float(temperature),
            "top_k": int(top_k),
            "top_p": float(top_p),
        }

        request = permission_gate.propose(
            capability=Capability.PROCESS_EXEC,
            action="rth_lm_action",
            scope=scope,
            reason=reason,
            risk=risk,
        )
        return request.to_dict()

    def execute(self, request_id: str) -> Dict[str, Any]:
        if not permission_gate.check(request_id):
            return {"status": "denied", "request_id": request_id}

        req = permission_gate.requests.get(request_id)
        if not req:
            return {"status": "not_found", "request_id": request_id}

        scope = req.scope or {}
        action = str(scope.get("action", "")).strip().lower()
        if action == "checkpoint_probe":
            return self._run_checkpoint_probe(request_id=request_id, scope=scope)
        if action == "launch_interactive":
            return self._launch_interactive(request_id=request_id, scope=scope)
        return {"status": "invalid_action", "action": action}

    def jobs(self) -> Dict[str, Any]:
        out = []
        for job in self.active_jobs.values():
            proc = job.get("_proc")
            if proc and job.get("status") == "running":
                rc = proc.poll()
                if rc is not None:
                    job["status"] = "completed" if rc == 0 else "failed"
                    job["returncode"] = rc
                    job["ended_at"] = datetime.now().isoformat()
                    for key in ("_stdout", "_stderr"):
                        fh = job.get(key)
                        if fh:
                            try:
                                fh.close()
                            except Exception:
                                pass
            out.append({k: v for k, v in job.items() if not k.startswith("_")})
        out.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return {"count": len(out), "items": out}

    def _resolve_root(self) -> Optional[Path]:
        for c in ROOT_CANDIDATES:
            if c.exists():
                return c
            try:
                mapped = Path(map_path(str(c)))
                if mapped.exists():
                    return mapped
            except Exception:
                continue
        return None

    def _artifact_map(self, root: Optional[Path]) -> Dict[str, Any]:
        if not root:
            return {
                "script": {"path": None, "exists": False},
                "genome": {"path": None, "exists": False},
                "checkpoint": {"path": None, "exists": False},
                "gguf": {"path": None, "exists": False},
            }

        def info(name: str) -> Dict[str, Any]:
            p = root / name
            exists = p.exists()
            return {
                "path": str(p),
                "exists": exists,
                "size": p.stat().st_size if exists and p.is_file() else None,
                "mtime": datetime.fromtimestamp(p.stat().st_mtime).isoformat() if exists else None,
            }

        return {
            "script": info(INFERENCE_SCRIPT),
            "genome": info(GENOME_FILE),
            "checkpoint": info(CHECKPOINT_FILE),
            "gguf": info(GGUF_FILE),
        }

    def _run_checkpoint_probe(self, request_id: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        ckpt_path = Path(str(scope.get("checkpoint_path", "")))
        if not ckpt_path.exists():
            return {"status": "checkpoint_missing", "checkpoint_path": str(ckpt_path)}

        started_at = datetime.now().isoformat()
        try:
            import torch
        except Exception as e:
            return {"status": "error", "error": f"torch_import_failed: {e}"}

        try:
            ckpt = torch.load(ckpt_path, map_location="cpu")
            model = ckpt.get("model", {}) if isinstance(ckpt, dict) else {}
            numel_total = 0
            dtype_counts: Dict[str, int] = {}
            for v in model.values() if isinstance(model, dict) else []:
                if hasattr(v, "numel"):
                    try:
                        numel_total += int(v.numel())
                    except Exception:
                        pass
                if hasattr(v, "dtype"):
                    key = str(v.dtype)
                    dtype_counts[key] = dtype_counts.get(key, 0) + 1

            payload = {
                "status": "ok",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
                "started_at": started_at,
                "checkpoint_path": str(ckpt_path),
                "summary": {
                    "step": ckpt.get("step") if isinstance(ckpt, dict) else None,
                    "loss": float(ckpt.get("loss")) if isinstance(ckpt, dict) and ckpt.get("loss") is not None else None,
                    "model_tensors": len(model) if isinstance(model, dict) else 0,
                    "model_numel_total_est": numel_total,
                    "dtype_counts": dtype_counts,
                },
            }
            self._write_latest_json("rth_lm_probe_latest.json", payload)
            memory_vault.record_event("rth_lm_probe", payload, tags={"mode": "read_only"})
            return payload
        except Exception as e:
            return {
                "status": "error",
                "request_id": request_id,
                "checkpoint_path": str(ckpt_path),
                "error": str(e),
            }

    def _launch_interactive(self, request_id: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        script_path = Path(str(scope.get("script_path", "")))
        root = script_path.parent
        if not script_path.exists():
            return {"status": "script_missing", "script_path": str(script_path)}

        logs = self._writable_logs_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = logs / f"rth_lm_interactive_{ts}.log"
        err_path = logs / f"rth_lm_interactive_{ts}.err.log"

        try:
            out_f = open(log_path, "a", encoding="utf-8")
            err_f = open(err_path, "a", encoding="utf-8")
            proc = subprocess.Popen(
                ["python", str(script_path)],
                cwd=str(root),
                stdout=out_f,
                stderr=err_f,
                shell=False,
            )
            job_id = f"rthlm_{proc.pid}"
            self.active_jobs[job_id] = {
                "job_id": job_id,
                "request_id": request_id,
                "action": "launch_interactive",
                "pid": proc.pid,
                "status": "running",
                "started_at": datetime.now().isoformat(),
                "root": str(root),
                "script_path": str(script_path),
                "log_path": str(log_path),
                "err_path": str(err_path),
                "_proc": proc,
                "_stdout": out_f,
                "_stderr": err_f,
            }
            payload = {
                "status": "started",
                "request_id": request_id,
                "job_id": job_id,
                "pid": proc.pid,
                "log_path": str(log_path),
                "err_path": str(err_path),
            }
            memory_vault.record_event("rth_lm_launch", payload, tags={"mode": "interactive"})
            return payload
        except Exception as e:
            return {"status": "error", "request_id": request_id, "error": str(e)}

    def _writable_logs_dir(self) -> Path:
        candidates = [
            Path("logs"),
            Path("storage_runtime") / "logs",
            Path(tempfile.gettempdir()) / "rth_core" / "logs",
        ]
        for c in candidates:
            try:
                c.mkdir(parents=True, exist_ok=True)
                probe = c / ".probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return c
            except Exception:
                continue
        p = Path(tempfile.gettempdir()) / "rth_core" / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _write_latest_json(self, filename: str, payload: Dict[str, Any]) -> None:
        path = self._writable_logs_dir() / filename
        try:
            path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write {filename}: {e}")


rth_lm_adapter = RTHLMAdapter()
