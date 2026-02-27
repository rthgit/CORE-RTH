"""
SHADOW CCS adapter for governed execution inside CORE RTH.

Proposal-first actions:
- artifact_probe: inspect SHADOW bundle readiness and key artifacts
- validate_text: run one deterministic SHADOW v15 validation request
- benchmark_validation: run repeated SHADOW validations and report p50/p95/p99/throughput
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
import hashlib
import importlib.util
import io
from pathlib import Path
import os
import threading
import time
import math
from typing import Any, Dict, List, Optional

from .memory_vault import memory_vault
from .permissions import permission_gate, Capability, RiskLevel


ROOT_ENV = "RTH_SHADOW_ROOT"
ACTION_KEYS = {"artifact_probe", "validate_text", "benchmark_validation"}
MAX_HISTORY = 200


class ShadowCCSAdapter:
    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def status(self) -> Dict[str, Any]:
        root = self._resolve_root()
        artifacts = self._artifact_map(root)
        return {
            "module": "shadow_ccs_adapter",
            "root": str(root) if root else None,
            "root_candidates": [str(p) for p in self._candidate_roots()],
            "artifacts": artifacts,
            "ready_for_probe": bool(root and artifacts.get("core_module", {}).get("exists")),
            "ready_for_validation": bool(root and artifacts.get("core_module", {}).get("exists")),
            "jobs": self.jobs(),
        }

    def propose(
        self,
        action: str,
        reason: str,
        output: Optional[str] = None,
        policy_id: str = "default",
        cluster_size: int = 3,
        context: Optional[Dict[str, Any]] = None,
        iterations: int = 100,
        warmup: int = 10,
    ) -> Dict[str, Any]:
        action = str(action or "").strip().lower()
        if action not in ACTION_KEYS:
            raise ValueError(f"Unsupported action: {action}")

        root = self._resolve_root()
        if not root:
            raise FileNotFoundError("SHADOW root not found")

        artifacts = self._artifact_map(root)
        if action == "validate_text":
            if not output or not str(output).strip():
                raise ValueError("output is required for validate_text")
            if not artifacts["core_module"]["exists"]:
                raise FileNotFoundError("shadow_v15_core.py not found")
        if action == "benchmark_validation":
            if not artifacts["core_module"]["exists"]:
                raise FileNotFoundError("shadow_v15_core.py not found")
            if int(iterations) <= 0 or int(iterations) > 5000:
                raise ValueError("iterations must be between 1 and 5000")
            if int(warmup) < 0 or int(warmup) > 2000:
                raise ValueError("warmup must be between 0 and 2000")

        capability = Capability.FILESYSTEM_READ if action == "artifact_probe" else Capability.PROCESS_EXEC
        risk = RiskLevel.LOW if action == "artifact_probe" else RiskLevel.HIGH
        scope = {
            "action": action,
            "root": str(root),
            "output": output,
            "policy_id": policy_id,
            "cluster_size": int(cluster_size),
            "context": context or {},
            "iterations": int(iterations),
            "warmup": int(warmup),
        }
        request = permission_gate.propose(
            capability=capability,
            action="shadow_ccs_action",
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
        if action == "artifact_probe":
            return self._run_artifact_probe(request_id=request_id, scope=scope)
        if action == "validate_text":
            return self._run_validate_text(request_id=request_id, scope=scope)
        if action == "benchmark_validation":
            return self._run_benchmark_validation(request_id=request_id, scope=scope)
        return {"status": "invalid_action", "action": action}

    def jobs(self) -> Dict[str, Any]:
        items = list(self.history)
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return {"count": len(items), "items": items}

    def _run_artifact_probe(self, request_id: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        root = Path(str(scope.get("root", "")))
        if not root.exists():
            return {"status": "root_missing", "request_id": request_id, "root": str(root)}

        artifacts = self._artifact_map(root)
        lora_count = self._count_lora_files(root / "lora_hub")
        payload = {
            "status": "ok",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "root": str(root),
            "artifacts": artifacts,
            "summary": {
                "has_core_module": artifacts["core_module"]["exists"],
                "has_phantom_kernel": artifacts["phantom_kernel"]["exists"],
                "lora_files": lora_count,
            },
        }
        self._remember(payload)
        memory_vault.record_event("shadow_ccs_probe", payload, tags={"mode": "read_only"})
        return payload

    def _run_validate_text(self, request_id: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        root = Path(str(scope.get("root", "")))
        output = str(scope.get("output") or "").strip()
        policy_id = str(scope.get("policy_id") or "default").strip() or "default"
        cluster_size = int(scope.get("cluster_size") or 3)
        context = scope.get("context") or {}

        if not root.exists():
            return {"status": "root_missing", "request_id": request_id, "root": str(root)}
        if not output:
            return {"status": "invalid", "request_id": request_id, "detail": "output_required"}

        module_path = root / "shadow_v15_core.py"
        if not module_path.exists():
            return {
                "status": "module_missing",
                "request_id": request_id,
                "module_path": str(module_path),
            }

        started_at = datetime.now().isoformat()
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                module = self._load_shadow_module(module_path)
                create_cluster = getattr(module, "create_cluster", None)
                validation_request_cls = getattr(module, "ValidationRequest", None)
                if not create_cluster or not validation_request_cls:
                    return {"status": "invalid_module", "request_id": request_id, "module_path": str(module_path)}
                cluster = create_cluster(cluster_size)
            req = validation_request_cls(
                output=output,
                context=context,
                policy_id=policy_id,
                timestamp_ns=time.time_ns(),
            )
            result = self._run_coro(cluster.validate(req))
            node_votes = {
                str(node_id): getattr(status, "value", str(status))
                for node_id, status in getattr(result, "node_votes", {}).items()
            }
            payload = {
                "status": "ok",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
                "started_at": started_at,
                "root": str(root),
                "input": {
                    "output": output,
                    "policy_id": policy_id,
                    "cluster_size": cluster_size,
                },
                "result": {
                    "status": getattr(getattr(result, "status", None), "value", None),
                    "confidence": float(getattr(result, "confidence", 0.0)),
                    "hash": getattr(result, "hash", None),
                    "node_votes": node_votes,
                    "latency_ms": float(getattr(result, "latency_ms", 0.0)),
                    "consensus_reached": bool(getattr(result, "consensus_reached", False)),
                    "request_hash": getattr(req, "request_hash", None),
                },
            }
            self._remember(payload)
            memory_vault.record_event("shadow_ccs_validate", payload, tags={"mode": "consensus"})
            return payload
        except Exception as e:
            payload = {
                "status": "error",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
                "root": str(root),
                "error": str(e),
            }
            self._remember(payload)
            return payload

    def _run_benchmark_validation(self, request_id: str, scope: Dict[str, Any]) -> Dict[str, Any]:
        root = Path(str(scope.get("root", "")))
        output = str(scope.get("output") or "shadow benchmark payload").strip()
        policy_id = str(scope.get("policy_id") or "default").strip() or "default"
        cluster_size = int(scope.get("cluster_size") or 3)
        context = scope.get("context") or {}
        iterations = int(scope.get("iterations") or 100)
        warmup = int(scope.get("warmup") or 10)

        if not root.exists():
            return {"status": "root_missing", "request_id": request_id, "root": str(root)}
        if iterations <= 0:
            return {"status": "invalid", "request_id": request_id, "detail": "iterations_must_be_positive"}

        module_path = root / "shadow_v15_core.py"
        if not module_path.exists():
            return {
                "status": "module_missing",
                "request_id": request_id,
                "module_path": str(module_path),
            }

        started_at = datetime.now().isoformat()
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                module = self._load_shadow_module(module_path)
                create_cluster = getattr(module, "create_cluster", None)
                validation_request_cls = getattr(module, "ValidationRequest", None)
                if not create_cluster or not validation_request_cls:
                    return {"status": "invalid_module", "request_id": request_id, "module_path": str(module_path)}
                cluster = create_cluster(cluster_size)

            async def _runner():
                status_counts: Dict[str, int] = {}
                lat_ms: List[float] = []

                for i in range(max(0, warmup)):
                    req = validation_request_cls(
                        output=f"{output} [warmup:{i}]",
                        context=context,
                        policy_id=policy_id,
                        timestamp_ns=time.time_ns(),
                    )
                    await cluster.validate(req)

                bench_start = time.perf_counter()
                for i in range(iterations):
                    req = validation_request_cls(
                        output=f"{output} [run:{i}]",
                        context=context,
                        policy_id=policy_id,
                        timestamp_ns=time.time_ns(),
                    )
                    t0 = time.perf_counter()
                    res = await cluster.validate(req)
                    dt = (time.perf_counter() - t0) * 1000.0
                    lat_ms.append(dt)
                    status = getattr(getattr(res, "status", None), "value", "UNKNOWN")
                    status_counts[status] = status_counts.get(status, 0) + 1
                bench_seconds = max(1e-9, (time.perf_counter() - bench_start))
                return lat_ms, status_counts, bench_seconds

            lat_ms, status_counts, bench_seconds = self._run_coro(_runner())
            lat_ms = sorted(lat_ms)
            n = len(lat_ms)

            def pct(p: float) -> float:
                if n == 0:
                    return 0.0
                idx = max(0, min(n - 1, int(math.ceil((p / 100.0) * n) - 1)))
                return float(lat_ms[idx])

            payload = {
                "status": "ok",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
                "started_at": started_at,
                "root": str(root),
                "input": {
                    "output": output,
                    "policy_id": policy_id,
                    "cluster_size": cluster_size,
                    "iterations": iterations,
                    "warmup": warmup,
                },
                "metrics": {
                    "runs": n,
                    "benchmark_seconds": bench_seconds,
                    "throughput_rps": float(n / bench_seconds) if bench_seconds > 0 else 0.0,
                    "latency_ms": {
                        "min": float(lat_ms[0]) if n else 0.0,
                        "p50": pct(50),
                        "p95": pct(95),
                        "p99": pct(99),
                        "max": float(lat_ms[-1]) if n else 0.0,
                    },
                    "status_counts": status_counts,
                },
            }
            self._remember(payload)
            memory_vault.record_event("shadow_ccs_benchmark", payload, tags={"mode": "benchmark"})
            return payload
        except Exception as e:
            payload = {
                "status": "error",
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
                "root": str(root),
                "error": str(e),
            }
            self._remember(payload)
            return payload

    def _candidate_roots(self) -> List[Path]:
        raw = []
        env_root = os.getenv(ROOT_ENV, "").strip()
        if env_root:
            raw.append(Path(env_root))
        raw.extend(
            [
                Path("C:/Users/PC/Desktop/Biome/shadow_x_models"),
                Path("D:/SIMULATORE_RCQ/shadow_x_models"),
                Path("shadow_x_models"),
            ]
        )

        out: List[Path] = []
        seen = set()
        for p in raw:
            key = str(p).replace("\\", "/").lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
        return out

    def _resolve_root(self) -> Optional[Path]:
        for candidate in self._candidate_roots():
            if candidate.exists():
                return candidate
        return None

    def _artifact_map(self, root: Optional[Path]) -> Dict[str, Any]:
        if not root:
            return {
                "core_module": {"path": None, "exists": False},
                "phantom_kernel": {"path": None, "exists": False},
                "lora_hub": {"path": None, "exists": False},
                "data_dir": {"path": None, "exists": False},
                "server_py": {"path": None, "exists": False},
                "health_py": {"path": None, "exists": False},
            }

        return {
            "core_module": self._path_info(root / "shadow_v15_core.py"),
            "phantom_kernel": self._path_info(root / "phantom_kernel.py", with_hash=True),
            "lora_hub": self._path_info(root / "lora_hub", is_dir=True),
            "data_dir": self._path_info(root / "v11_Morpho_Optimized", is_dir=True),
            "server_py": self._path_info(root / "server.py"),
            "health_py": self._path_info(root / "health.py"),
        }

    def _path_info(self, path: Path, is_dir: bool = False, with_hash: bool = False) -> Dict[str, Any]:
        exists = path.exists()
        data: Dict[str, Any] = {
            "path": str(path),
            "exists": exists,
        }
        if not exists:
            return data
        try:
            stat = path.stat()
            data["mtime"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            data["size"] = stat.st_size if path.is_file() else None
        except Exception:
            data["mtime"] = None
            data["size"] = None
        if is_dir and path.is_dir():
            try:
                data["files_count"] = len([x for x in path.iterdir() if x.is_file()])
            except Exception:
                data["files_count"] = None
        if with_hash and path.is_file():
            data["sha256"] = self._sha256(path)
        return data

    def _sha256(self, path: Path) -> Optional[str]:
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return None

    def _count_lora_files(self, lora_dir: Path) -> int:
        try:
            if not lora_dir.exists() or not lora_dir.is_dir():
                return 0
            return len([x for x in lora_dir.glob("*.pkl") if x.is_file()])
        except Exception:
            return 0

    def _load_shadow_module(self, module_path: Path):
        module_name = f"shadow_v15_core_{int(time.time() * 1000)}"
        spec = importlib.util.spec_from_file_location(module_name, str(module_path))
        if spec is None or spec.loader is None:
            raise RuntimeError("failed_to_build_module_spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _run_coro(self, coro):
        try:
            asyncio.get_running_loop()
            has_running = True
        except RuntimeError:
            has_running = False

        if not has_running:
            return asyncio.run(coro)

        result_box: Dict[str, Any] = {}

        def _runner():
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                result_box["result"] = loop.run_until_complete(coro)
            except Exception as e:
                result_box["error"] = e
            finally:
                loop.close()

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join()
        if "error" in result_box:
            raise result_box["error"]
        return result_box.get("result")

    def _remember(self, payload: Dict[str, Any]) -> None:
        self.history.append(payload)
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]


shadow_ccs_adapter = ShadowCCSAdapter()
