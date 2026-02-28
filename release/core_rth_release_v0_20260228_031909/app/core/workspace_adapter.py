"""
Workspace adapter for Aletheion/Code/Cowork with consent-gated commands.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import subprocess
import tempfile
import os

from .permissions import permission_gate, Capability, RiskLevel
from .pathmap import map_path


WORKSPACE_CANDIDATES = {
    "reader": [
        "E:/lettore  documenti/SublimeOmniDoc",
    ],
    "antihaker": [
        "D:/SICUREZZA ANTIHAKER",
    ],
    "aletheion": [
        "C:/Users/PC/Desktop/aletheion",
        "D:/SIMULATORE_RCQ/aletheion_analysis",
        "D:/SIMULATORE_RCQ/biome_knowledge_expansion",
    ],
    "code": [
        "D:/CODEX/code-oss",
        "D:/CODEX/codex_hybrid_ai",
    ],
    "cowork": [
        "D:/CODEX/open-cowork",
    ],
}

ACTION_KEYS = {"build", "run", "test"}
ALLOWED_BINARIES = {"python", "pytest", "npm", "npx", "node", "pnpm", "yarn"}


@dataclass
class WorkspaceProfile:
    name: str
    root: str
    commands: Dict[str, List[List[str]]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "root": self.root,
            "commands": self.commands,
        }


class WorkspaceAdapter:
    def __init__(self):
        self.active_jobs: Dict[str, Dict[str, Any]] = {}

    def profiles(self) -> Dict[str, Any]:
        out = []
        for name, roots in WORKSPACE_CANDIDATES.items():
            profile = self._select_profile(roots, name)
            if not profile:
                continue
            out.append(profile.to_dict())
        return {"profiles": out, "count": len(out)}

    def propose(self, workspace: str, action: str, reason: str, command: Optional[List[str]] = None) -> Dict[str, Any]:
        action = action.lower().strip()
        if action not in ACTION_KEYS:
            raise ValueError(f"Unsupported action: {action}")

        profile = self._get_profile(workspace)
        options = profile.commands.get(action, [])
        if not options:
            raise ValueError(f"No command options for {workspace}:{action}")

        selected = command or options[0]
        if selected not in options:
            raise ValueError("Command not in approved workspace options")
        if not selected or selected[0].lower() not in ALLOWED_BINARIES:
            raise ValueError("Command binary not allowed")

        request = permission_gate.propose(
            capability=Capability.PROCESS_EXEC,
            action="workspace_command",
            scope={
                "workspace": workspace,
                "action": action,
                "root": profile.root,
                "command": selected,
            },
            reason=reason,
            risk=RiskLevel.HIGH,
        )
        return request.to_dict()

    def execute(self, request_id: str) -> Dict[str, Any]:
        if not permission_gate.check(request_id):
            return {"status": "denied", "request_id": request_id}
        req = permission_gate.requests.get(request_id)
        if not req:
            return {"status": "not_found", "request_id": request_id}
        root = req.scope.get("root")
        command = req.scope.get("command", [])
        workspace = req.scope.get("workspace")
        action = req.scope.get("action")
        if not root or not command:
            return {"status": "invalid_scope", "request_id": request_id}
        if not Path(root).exists():
            return {"status": "workspace_missing", "root": root}
        if str(command[0]).lower() not in ALLOWED_BINARIES:
            return {"status": "blocked", "detail": "binary not allowed"}

        logs_dir = self._writable_logs_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = logs_dir / f"{workspace}_{action}_{ts}.log"
        err_path = logs_dir / f"{workspace}_{action}_{ts}.err.log"

        try:
            out_f = open(log_path, "a", encoding="utf-8")
            err_f = open(err_path, "a", encoding="utf-8")
            proc = subprocess.Popen(
                command,
                cwd=root,
                stdout=out_f,
                stderr=err_f,
                shell=False,
            )
            job_id = f"job_{proc.pid}"
            self.active_jobs[job_id] = {
                "job_id": job_id,
                "workspace": workspace,
                "action": action,
                "command": command,
                "root": root,
                "pid": proc.pid,
                "started_at": datetime.now().isoformat(),
                "log_path": str(log_path),
                "err_path": str(err_path),
                "_stdout": out_f,
                "_stderr": err_f,
            }
            return {
                "status": "started",
                "job_id": job_id,
                "pid": proc.pid,
                "workspace": workspace,
                "action": action,
                "command": command,
                "root": root,
                "log_path": str(log_path),
                "err_path": str(err_path),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def jobs(self) -> Dict[str, Any]:
        clean = []
        for job in self.active_jobs.values():
            view = {k: v for k, v in job.items() if not k.startswith("_")}
            clean.append(view)
        clean.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return {"jobs": clean, "count": len(clean)}

    def _get_profile(self, workspace: str) -> WorkspaceProfile:
        workspace = workspace.lower().strip()
        roots = WORKSPACE_CANDIDATES.get(workspace)
        if not roots:
            raise ValueError(f"Unknown workspace: {workspace}")
        profile = self._select_profile(roots, workspace)
        if not profile:
            raise ValueError(f"Workspace unavailable: {workspace}")
        return profile

    def _select_profile(self, roots: List[str], name: str) -> Optional[WorkspaceProfile]:
        best: Optional[WorkspaceProfile] = None
        best_score = -1
        for root in roots:
            mapped = map_path(root)
            rp = Path(mapped)
            if not rp.exists():
                continue
            profile = self._build_profile(name, str(rp))
            score = sum(len(v) for v in profile.commands.values())
            if score > best_score:
                best = profile
                best_score = score
        return best

    def _build_profile(self, name: str, root: str) -> WorkspaceProfile:
        rp = Path(root)
        commands: Dict[str, List[List[str]]] = {
            "build": [],
            "run": [],
            "test": [],
        }

        if (rp / "package.json").exists():
            commands["build"].append(["npm", "run", "build"])
            commands["run"].append(["npm", "run", "dev"])
            commands["test"].append(["npm", "test"])
        if (rp / "pnpm-lock.yaml").exists():
            commands["build"].append(["pnpm", "build"])
            commands["run"].append(["pnpm", "dev"])
            commands["test"].append(["pnpm", "test"])
        if (rp / "yarn.lock").exists():
            commands["build"].append(["yarn", "build"])
            commands["run"].append(["yarn", "dev"])
            commands["test"].append(["yarn", "test"])

        if (rp / "requirements.txt").exists() or (rp / "pyproject.toml").exists():
            # Avoid compiling virtualenv/site-packages trees (slow + noisy permission errors on Windows).
            commands["build"].append([
                "python", "-m", "compileall", "-q",
                "-x", r"[/\\](\.venv|venv|\.tox|site-packages)[/\\]",
                ".",
            ])
            if (rp / "main.py").exists():
                commands["run"].append(["python", "main.py"])
            elif (rp / "app" / "main.py").exists():
                commands["run"].append(["python", "-m", "app.main"])
            commands["test"].append(["pytest", "-q"])

        # Python fallback for repos without explicit dependency markers.
        if not any(commands.values()) and self._has_python_files(rp):
            commands["build"].append([
                "python", "-m", "compileall", "-q",
                "-x", r"[/\\](\.venv|venv|\.tox|site-packages)[/\\]",
                ".",
            ])
            for entry in ["main.py", "app.py", "run.py"]:
                if (rp / entry).exists():
                    commands["run"].append(["python", entry])
                    break
            if (rp / "app" / "main.py").exists():
                commands["run"].append(["python", "-m", "app.main"])
            commands["test"].append(["pytest", "-q"])

        # Deduplicate while preserving order.
        for action, arr in commands.items():
            uniq = []
            seen = set()
            for cmd in arr:
                key = tuple(cmd)
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(cmd)
            commands[action] = uniq

        return WorkspaceProfile(name=name, root=root, commands=commands)

    def _first_existing(self, roots: List[str]) -> Optional[str]:
        for root in roots:
            if Path(root).exists():
                return root
        return None

    def _has_python_files(self, root: Path, max_depth: int = 3, max_hits: int = 20) -> bool:
        hits = 0
        for dirpath, dirnames, filenames in os.walk(root):
            rel = os.path.relpath(dirpath, root)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth > max_depth:
                dirnames[:] = []
                continue
            for fn in filenames:
                if fn.lower().endswith(".py"):
                    hits += 1
                    if hits >= max_hits:
                        return True
        return hits > 0

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
        return Path(tempfile.gettempdir())


workspace_adapter = WorkspaceAdapter()
