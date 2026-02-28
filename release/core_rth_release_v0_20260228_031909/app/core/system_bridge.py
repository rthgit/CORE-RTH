"""
System bridge for workspace discovery and consent-gated desktop actions.
"""
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import subprocess
import os

from .permissions import permission_gate, Capability, RiskLevel


KNOWN_WORKSPACES = {
    "aletheion": [
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

ALLOWED_MOUSE_ACTIONS = {
    "position",
    "move",
    "click",
    "double_click",
    "right_click",
    "scroll",
}


@dataclass
class AppCandidate:
    path: str
    root: str
    size: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "root": self.root,
            "size": self.size,
        }


class SystemBridge:
    def _load_pyautogui(self):
        try:
            import pyautogui  # type: ignore
        except Exception:
            return None
        # Keep fail-safe enabled to allow manual abort from screen corner.
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        return pyautogui

    def discover_workspaces(self) -> Dict[str, Any]:
        out = {}
        for name, candidates in KNOWN_WORKSPACES.items():
            found = []
            for c in candidates:
                p = Path(c)
                if p.exists():
                    found.append(str(p))
            out[name] = {
                "candidates": candidates,
                "found": found,
                "available": len(found) > 0,
            }
        return out

    def discover_apps(self, roots: List[str], max_depth: int = 4, max_results: int = 300) -> Dict[str, Any]:
        # Include PowerShell scripts for operator stacks that use cmd wrappers + ps1 cores.
        executable_ext = {".exe", ".bat", ".cmd", ".ps1"}
        excluded_dirs = {
            ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
            "temp", "tmp", "cache", ".cache",
        }
        results: List[AppCandidate] = []
        for root in roots:
            rp = Path(root)
            if not rp.exists():
                continue
            for dirpath, dirnames, filenames in os.walk(rp):
                rel = os.path.relpath(dirpath, rp)
                depth = 0 if rel == "." else rel.count(os.sep) + 1
                if depth > max_depth:
                    dirnames[:] = []
                    continue
                dirnames[:] = [d for d in dirnames if d.lower() not in excluded_dirs]
                for fn in filenames:
                    ext = Path(fn).suffix.lower()
                    if ext not in executable_ext:
                        continue
                    full = Path(dirpath) / fn
                    try:
                        size = full.stat().st_size
                    except Exception:
                        size = 0
                    results.append(AppCandidate(path=str(full), root=str(rp), size=size))
                    if len(results) >= max_results:
                        return {
                            "count": len(results),
                            "items": [r.to_dict() for r in results]
                        }
        return {
            "count": len(results),
            "items": [r.to_dict() for r in results]
        }

    def propose_app_launch(self, app_path: str, args: Optional[List[str]], reason: str) -> Dict[str, Any]:
        request = permission_gate.propose(
            capability=Capability.PROCESS_EXEC,
            action="app_launch",
            scope={"app_path": app_path, "args": args or []},
            reason=reason,
            risk=RiskLevel.HIGH,
        )
        return request.to_dict()

    def execute_app_launch(self, request_id: str) -> Dict[str, Any]:
        if not permission_gate.check(request_id):
            return {"status": "denied", "request_id": request_id}
        req = permission_gate.requests.get(request_id)
        if not req:
            return {"status": "not_found", "request_id": request_id}
        app_path = req.scope.get("app_path")
        args = req.scope.get("args", [])
        if not app_path or not Path(app_path).exists():
            return {"status": "not_found", "app_path": app_path}
        try:
            proc = subprocess.Popen([app_path, *args], shell=False)
            return {
                "status": "launched",
                "pid": proc.pid,
                "app_path": app_path,
                "args": args,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def propose_mouse_action(self, action: str, x: Optional[int], y: Optional[int], reason: str) -> Dict[str, Any]:
        normalized_action = str(action or "").strip().lower()
        if normalized_action not in ALLOWED_MOUSE_ACTIONS:
            return {
                "status": "invalid",
                "detail": f"unknown action: {normalized_action}",
                "allowed_actions": sorted(ALLOWED_MOUSE_ACTIONS),
            }
        request = permission_gate.propose(
            capability=Capability.SYSTEM_MODIFY,
            action="mouse_action",
            scope={"action": normalized_action, "x": x, "y": y},
            reason=reason,
            risk=RiskLevel.HIGH,
        )
        return request.to_dict()

    def mouse_status(self) -> Dict[str, Any]:
        pyautogui = self._load_pyautogui()
        if pyautogui is None:
            return {
                "available": False,
                "detail": "pyautogui not installed",
                "allowed_actions": sorted(ALLOWED_MOUSE_ACTIONS),
            }
        try:
            pos = pyautogui.position()
            size = pyautogui.size()
            return {
                "available": True,
                "position": {"x": int(pos.x), "y": int(pos.y)},
                "screen": {"width": int(size.width), "height": int(size.height)},
                "failsafe": bool(pyautogui.FAILSAFE),
                "allowed_actions": sorted(ALLOWED_MOUSE_ACTIONS),
            }
        except Exception as e:
            return {"available": False, "status": "error", "error": str(e)}

    def execute_mouse_action(self, request_id: str) -> Dict[str, Any]:
        if not permission_gate.check(request_id):
            return {"status": "denied", "request_id": request_id}
        req = permission_gate.requests.get(request_id)
        if not req:
            return {"status": "not_found", "request_id": request_id}
        action = str(req.scope.get("action", ""))
        x = req.scope.get("x")
        y = req.scope.get("y")
        pyautogui = self._load_pyautogui()
        if pyautogui is None:
            return {"status": "unavailable", "detail": "pyautogui not installed"}
        try:
            if action == "position":
                pos = pyautogui.position()
                size = pyautogui.size()
                return {
                    "status": "ok",
                    "action": action,
                    "position": {"x": int(pos.x), "y": int(pos.y)},
                    "screen": {"width": int(size.width), "height": int(size.height)},
                }
            if action == "move":
                if x is None or y is None:
                    return {"status": "invalid", "detail": "x and y required"}
                pyautogui.moveTo(int(x), int(y), duration=0.2)
            elif action == "click":
                if x is not None and y is not None:
                    pyautogui.click(int(x), int(y))
                else:
                    pyautogui.click()
            elif action == "double_click":
                if x is not None and y is not None:
                    pyautogui.doubleClick(int(x), int(y))
                else:
                    pyautogui.doubleClick()
            elif action == "right_click":
                if x is not None and y is not None:
                    pyautogui.rightClick(int(x), int(y))
                else:
                    pyautogui.rightClick()
            elif action == "scroll":
                scroll_amount = int(y if y is not None else 0)
                pyautogui.scroll(scroll_amount)
            else:
                return {"status": "invalid", "detail": f"unknown action: {action}"}
            return {"status": "ok", "action": action, "x": x, "y": y}
        except Exception as e:
            return {"status": "error", "error": str(e)}


system_bridge = SystemBridge()
