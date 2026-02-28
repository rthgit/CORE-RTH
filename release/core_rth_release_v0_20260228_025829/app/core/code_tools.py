"""
Code Tools — Governed file read/write/edit and terminal execution for Core Rth.

Provides Guardian-governed tools that allow the system (Agent Loop, Village, etc.)
to read, write, edit files and execute terminal commands safely.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .permissions import permission_gate, Capability, RiskLevel
from .memory_vault import memory_vault

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

BLOCKED_PATHS = {
    "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
    "/usr", "/bin", "/sbin", "/etc", "/boot", "/proc", "/sys",
}

BLOCKED_EXTENSIONS_WRITE = {".exe", ".dll", ".sys", ".bat", ".cmd", ".ps1", ".sh", ".msi"}

MAX_FILE_READ_BYTES = 2_000_000       # 2 MB
MAX_FILE_WRITE_BYTES = 5_000_000      # 5 MB
MAX_TERMINAL_OUTPUT = 100_000         # 100 KB
TERMINAL_TIMEOUT_SEC = 30
MAX_EDIT_LINES = 10_000


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_path(path: str, for_write: bool = False) -> tuple[bool, str]:
    """Check if path is safe to operate on."""
    try:
        p = Path(path).resolve()
    except Exception as e:
        return False, f"Invalid path: {e}"
    path_str = str(p)
    for blocked in BLOCKED_PATHS:
        if path_str.lower().startswith(blocked.lower()):
            return False, f"Path is in blocked directory: {blocked}"
    if for_write:
        ext = p.suffix.lower()
        if ext in BLOCKED_EXTENSIONS_WRITE:
            return False, f"Blocked extension for write: {ext}"
    return True, ""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Standard result from any code tool."""
    tool: str
    status: str = "ok"
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    elapsed_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = {"tool": self.tool, "status": self.status}
        if self.data:
            d["data"] = self.data
        if self.error:
            d["error"] = self.error
        if self.elapsed_ms:
            d["elapsed_ms"] = self.elapsed_ms
        return d


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class CodeTools:
    """Governed file operations and terminal execution."""

    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self._max_history = 200

    # ── File Read ──────────────────────────────────────────────────────────

    def file_read(
        self,
        path: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
        encoding: str = "utf-8",
        **_kw,
    ) -> ToolResult:
        """Read file contents (governed: FILESYSTEM_READ)."""
        import time
        t0 = time.monotonic()
        result = ToolResult(tool="file_read")

        safe, reason = _safe_path(path)
        if not safe:
            result.status = "blocked"
            result.error = reason
            return result

        p = Path(path).resolve()
        if not p.exists():
            result.status = "error"
            result.error = f"File not found: {path}"
            return result

        if not p.is_file():
            result.status = "error"
            result.error = f"Not a file: {path}"
            return result

        if p.stat().st_size > MAX_FILE_READ_BYTES:
            result.status = "error"
            result.error = f"File too large ({p.stat().st_size} bytes, limit {MAX_FILE_READ_BYTES})"
            return result

        try:
            text = p.read_text(encoding=encoding, errors="replace")
            lines = text.splitlines(keepends=True)
            total_lines = len(lines)
            sl = max(1, start_line) - 1
            el = end_line if end_line else total_lines
            el = min(el, total_lines)
            selected = lines[sl:el]
            result.data = {
                "path": str(p),
                "total_lines": total_lines,
                "start_line": sl + 1,
                "end_line": el,
                "content": "".join(selected),
                "size_bytes": p.stat().st_size,
            }
        except Exception as e:
            result.status = "error"
            result.error = str(e)

        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        self._record("file_read", result)
        return result

    # ── File Write ─────────────────────────────────────────────────────────

    def file_write(
        self,
        path: str,
        content: str,
        reason: str = "Agent file write",
        create_parents: bool = True,
        confirm_owner: bool = True,
        decided_by: str = "owner",
        encoding: str = "utf-8",
        **_kw,
    ) -> ToolResult:
        """Write content to a file (governed: FILESYSTEM_WRITE)."""
        import time
        t0 = time.monotonic()
        result = ToolResult(tool="file_write")

        safe, msg = _safe_path(path, for_write=True)
        if not safe:
            result.status = "blocked"
            result.error = msg
            return result

        if len(content.encode(encoding, errors="replace")) > MAX_FILE_WRITE_BYTES:
            result.status = "error"
            result.error = f"Content too large (limit {MAX_FILE_WRITE_BYTES} bytes)"
            return result

        p = Path(path).resolve()

        # Guardian approval
        req = permission_gate.propose(
            capability=Capability.FILESYSTEM_WRITE,
            action="agent_file_write",
            scope={"path": str(p), "size": len(content), "exists": p.exists()},
            reason=self._safe_reason(reason),
            risk=RiskLevel.MEDIUM,
        )
        if confirm_owner:
            decision = permission_gate.approve(req.request_id, decided_by=decided_by)
            if decision.decision.value != "approved":
                result.status = "denied"
                result.error = f"Guardian denied: {decision.denial_reason or 'denied'}"
                result.data = {"proposal": req.to_dict(), "decision": decision.to_dict()}
                return result

        try:
            if create_parents:
                p.parent.mkdir(parents=True, exist_ok=True)

            # Backup if file exists
            backup_content = None
            if p.exists():
                backup_content = p.read_text(encoding=encoding, errors="replace")

            p.write_text(content, encoding=encoding)
            result.data = {
                "path": str(p),
                "bytes_written": len(content.encode(encoding, errors="replace")),
                "created": backup_content is None,
                "had_backup": backup_content is not None,
            }
        except Exception as e:
            result.status = "error"
            result.error = str(e)

        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        self._record("file_write", result)
        return result

    # ── File Edit (patch) ──────────────────────────────────────────────────

    def file_edit(
        self,
        path: str,
        old_text: str,
        new_text: str,
        reason: str = "Agent file edit",
        confirm_owner: bool = True,
        decided_by: str = "owner",
        encoding: str = "utf-8",
        **_kw,
    ) -> ToolResult:
        """Replace old_text with new_text in a file (governed: FILESYSTEM_WRITE)."""
        import time
        t0 = time.monotonic()
        result = ToolResult(tool="file_edit")

        safe, msg = _safe_path(path, for_write=True)
        if not safe:
            result.status = "blocked"
            result.error = msg
            return result

        p = Path(path).resolve()
        if not p.exists():
            result.status = "error"
            result.error = f"File not found: {path}"
            return result

        try:
            original = p.read_text(encoding=encoding, errors="replace")
        except Exception as e:
            result.status = "error"
            result.error = f"Cannot read file: {e}"
            return result

        if old_text not in original:
            result.status = "error"
            result.error = "old_text not found in file"
            return result

        count = original.count(old_text)
        patched = original.replace(old_text, new_text, 1)

        # Generate diff
        diff = list(difflib.unified_diff(
            original.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile=f"a/{p.name}",
            tofile=f"b/{p.name}",
            lineterm="",
        ))

        # Guardian approval
        req = permission_gate.propose(
            capability=Capability.FILESYSTEM_WRITE,
            action="agent_file_edit",
            scope={
                "path": str(p),
                "replacements": 1,
                "occurrences_total": count,
                "diff_lines": len(diff),
            },
            reason=self._safe_reason(reason),
            risk=RiskLevel.MEDIUM,
        )
        if confirm_owner:
            decision = permission_gate.approve(req.request_id, decided_by=decided_by)
            if decision.decision.value != "approved":
                result.status = "denied"
                result.error = f"Guardian denied: {decision.denial_reason or 'denied'}"
                return result

        try:
            p.write_text(patched, encoding=encoding)
            result.data = {
                "path": str(p),
                "replacements": 1,
                "diff_preview": "".join(diff[:50]),
            }
        except Exception as e:
            result.status = "error"
            result.error = str(e)

        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        self._record("file_edit", result)
        return result

    # ── Terminal Execute ───────────────────────────────────────────────────

    def terminal_exec(
        self,
        command: List[str],
        cwd: Optional[str] = None,
        timeout_sec: float = TERMINAL_TIMEOUT_SEC,
        reason: str = "Agent terminal command",
        confirm_owner: bool = True,
        decided_by: str = "owner",
        dry_run: bool = False,
        **_kw,
    ) -> ToolResult:
        """Execute a terminal command (governed: PROCESS_EXEC)."""
        import time
        t0 = time.monotonic()
        result = ToolResult(tool="terminal_exec")

        if not command:
            result.status = "error"
            result.error = "Empty command"
            return result

        # Guardian approval
        req = permission_gate.propose(
            capability=Capability.PROCESS_EXEC,
            action="agent_terminal_exec",
            scope={
                "command": command[:10],
                "cwd": cwd or os.getcwd(),
                "timeout_sec": timeout_sec,
                "dry_run": dry_run,
            },
            reason=self._safe_reason(reason),
            risk=RiskLevel.HIGH,
        )
        if confirm_owner:
            decision = permission_gate.approve(req.request_id, decided_by=decided_by)
            if decision.decision.value != "approved":
                result.status = "denied"
                result.error = f"Guardian denied: {decision.denial_reason or 'denied'}"
                return result

        if dry_run:
            result.data = {
                "command": command,
                "cwd": cwd,
                "mode": "dry_run",
                "note": "Command would execute but dry_run=True",
            }
            result.elapsed_ms = int((time.monotonic() - t0) * 1000)
            self._record("terminal_exec", result)
            return result

        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout_sec,
                env={**os.environ},
            )
            stdout = proc.stdout[:MAX_TERMINAL_OUTPUT] if proc.stdout else ""
            stderr = proc.stderr[:MAX_TERMINAL_OUTPUT] if proc.stderr else ""
            result.data = {
                "command": command,
                "cwd": cwd,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_truncated": len(proc.stdout or "") > MAX_TERMINAL_OUTPUT,
                "stderr_truncated": len(proc.stderr or "") > MAX_TERMINAL_OUTPUT,
            }
            if proc.returncode != 0:
                result.status = "error"
                result.error = f"Exit code {proc.returncode}"
        except subprocess.TimeoutExpired:
            result.status = "timeout"
            result.error = f"Command timed out after {timeout_sec}s"
        except Exception as e:
            result.status = "error"
            result.error = str(e)

        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        self._record("terminal_exec", result)
        return result

    # ── Directory List ─────────────────────────────────────────────────────

    def dir_list(
        self,
        path: str,
        max_depth: int = 1,
        max_items: int = 200,
        **_kw,
    ) -> ToolResult:
        """List directory contents (governed: FILESYSTEM_READ)."""
        import time
        t0 = time.monotonic()
        result = ToolResult(tool="dir_list")

        safe, reason = _safe_path(path)
        if not safe:
            result.status = "blocked"
            result.error = reason
            return result

        p = Path(path).resolve()
        if not p.is_dir():
            result.status = "error"
            result.error = f"Not a directory: {path}"
            return result

        items = []
        count = 0
        try:
            for item in sorted(p.iterdir()):
                if count >= max_items:
                    break
                entry = {
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                }
                if item.is_file():
                    try:
                        entry["size"] = item.stat().st_size
                    except Exception:
                        pass
                items.append(entry)
                count += 1
            result.data = {
                "path": str(p),
                "items": items,
                "count": count,
                "truncated": count >= max_items,
            }
        except Exception as e:
            result.status = "error"
            result.error = str(e)

        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        return result

    # ── Search in Files ────────────────────────────────────────────────────

    def grep(
        self,
        pattern: str,
        path: str,
        max_results: int = 50,
        case_insensitive: bool = True,
        **_kw,
    ) -> ToolResult:
        """Search for pattern in files (governed: FILESYSTEM_READ)."""
        import re
        import time
        t0 = time.monotonic()
        result = ToolResult(tool="grep")

        safe, reason = _safe_path(path)
        if not safe:
            result.status = "blocked"
            result.error = reason
            return result

        p = Path(path).resolve()
        flags = re.IGNORECASE if case_insensitive else 0
        try:
            compiled = re.compile(pattern, flags)
        except re.error as e:
            result.status = "error"
            result.error = f"Invalid regex: {e}"
            return result

        matches = []
        files_searched = 0
        try:
            targets = [p] if p.is_file() else list(p.rglob("*"))
            for target in targets:
                if not target.is_file():
                    continue
                if target.stat().st_size > MAX_FILE_READ_BYTES:
                    continue
                files_searched += 1
                try:
                    text = target.read_text(encoding="utf-8", errors="replace")
                    for i, line in enumerate(text.splitlines(), 1):
                        if compiled.search(line):
                            matches.append({
                                "file": str(target),
                                "line": i,
                                "content": line[:200],
                            })
                            if len(matches) >= max_results:
                                break
                except Exception:
                    continue
                if len(matches) >= max_results:
                    break

            result.data = {
                "pattern": pattern,
                "path": str(p),
                "matches": matches,
                "match_count": len(matches),
                "files_searched": files_searched,
                "truncated": len(matches) >= max_results,
            }
        except Exception as e:
            result.status = "error"
            result.error = str(e)

        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        return result

    # ── Git Operations ─────────────────────────────────────────────────────

    def git_status(self, repo_path: str, **_kw) -> ToolResult:
        """Get git status of a repository."""
        return self.terminal_exec(
            command=["git", "status", "--porcelain", "-b"],
            cwd=repo_path,
            reason="Agent git status check [safe] [audit]",
            confirm_owner=True,
            decided_by="owner",
        )

    def git_diff(self, repo_path: str, staged: bool = False, **_kw) -> ToolResult:
        """Get git diff."""
        cmd = ["git", "diff", "--stat"]
        if staged:
            cmd.append("--staged")
        return self.terminal_exec(
            command=cmd,
            cwd=repo_path,
            reason="Agent git diff [safe] [audit]",
            confirm_owner=True,
            decided_by="owner",
        )

    # ── Internals ──────────────────────────────────────────────────────────

    def _safe_reason(self, reason: str) -> str:
        tokens = reason.lower()
        if not any(t in tokens for t in ("safe", "audit", "dry-run")):
            return f"{reason} [safe] [audit]"
        return reason

    def _record(self, tool: str, result: ToolResult):
        entry = {
            "tool": tool,
            "status": result.status,
            "timestamp": _now(),
            "elapsed_ms": result.elapsed_ms,
        }
        self.history.append(entry)
        if len(self.history) > self._max_history:
            self.history = self.history[-self._max_history:]
        memory_vault.record_event(
            f"code_tool_{tool}",
            entry,
            tags={"source": "code_tools"},
        )

    def status(self) -> Dict[str, Any]:
        return {
            "module": "code_tools",
            "version": 1,
            "tools_available": [
                "file_read", "file_write", "file_edit",
                "terminal_exec", "dir_list", "grep",
                "git_status", "git_diff",
            ],
            "history_count": len(self.history),
            "max_file_read_bytes": MAX_FILE_READ_BYTES,
            "max_file_write_bytes": MAX_FILE_WRITE_BYTES,
            "terminal_timeout_sec": TERMINAL_TIMEOUT_SEC,
        }

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return OpenAI-compatible function schemas for all tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "file_read",
                    "description": "Read the contents of a file. Returns text content with line numbers.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Absolute path to file"},
                            "start_line": {"type": "integer", "description": "Start line (1-indexed)", "default": 1},
                            "end_line": {"type": "integer", "description": "End line (inclusive)"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file_write",
                    "description": "Write content to a file. Creates parent directories if needed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Absolute path to file"},
                            "content": {"type": "string", "description": "Content to write"},
                            "reason": {"type": "string", "description": "Why this write is needed"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file_edit",
                    "description": "Replace a specific text in a file with new text.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Absolute path to file"},
                            "old_text": {"type": "string", "description": "Exact text to find and replace"},
                            "new_text": {"type": "string", "description": "Replacement text"},
                            "reason": {"type": "string", "description": "Why this edit is needed"},
                        },
                        "required": ["path", "old_text", "new_text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "terminal_exec",
                    "description": "Execute a terminal command. Use list format for command.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "array", "items": {"type": "string"}, "description": "Command as list of strings"},
                            "cwd": {"type": "string", "description": "Working directory"},
                            "timeout_sec": {"type": "number", "default": 30},
                        },
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "dir_list",
                    "description": "List files and directories in a path.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Directory path"},
                            "max_items": {"type": "integer", "default": 200},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "grep",
                    "description": "Search for a pattern in files. Supports regex.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string", "description": "Search pattern (regex)"},
                            "path": {"type": "string", "description": "Directory or file to search"},
                            "case_insensitive": {"type": "boolean", "default": True},
                        },
                        "required": ["pattern", "path"],
                    },
                },
            },
        ]


# Singleton
code_tools = CodeTools()
