"""
Persistent memory vault for events and scan data.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import json
import logging
import hashlib
import tempfile
import os
from .config import settings

logger = logging.getLogger(__name__)

@dataclass
class VaultStats:
    events: int = 0
    files: int = 0
    scans: int = 0
    last_event: Optional[str] = None
    last_scan: Optional[str] = None

class MemoryVault:
    def __init__(self):
        self.diskless = getattr(settings, "RTH_DISKLESS", False)
        self.base = None
        if not self.diskless:
            self.base = self._select_base_dir()
        self.stats = VaultStats()

    def _select_base_dir(self) -> Optional[Path]:
        env_base = os.getenv("RTH_MEMORY_BASE", "").strip()
        if env_base:
            candidates = [Path(env_base)]
        else:
            candidates = [
                Path("storage") / "memory",
                Path("storage_runtime") / "memory",
                Path(tempfile.gettempdir()) / "rth_core" / "memory",
            ]
        for base in candidates:
            try:
                base.mkdir(parents=True, exist_ok=True)
                probe = base / ".write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return base
            except Exception:
                continue
        return None

    def _path(self, name: str) -> Optional[Path]:
        if not self.base:
            return None
        return self.base / name

    def _files_dir(self) -> Optional[Path]:
        if not self.base:
            return None
        files_dir = self.base / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        return files_dir

    def record_event(self, event_type: str, payload: Dict[str, Any], tags: Optional[Dict[str, Any]] = None):
        data = {
            "event_type": event_type,
            "payload": payload,
            "tags": tags or {},
            "timestamp": datetime.now().isoformat()
        }
        self._append("events.jsonl", data)
        self.stats.events += 1
        self.stats.last_event = data["timestamp"]

    def record_file(self, record: Dict[str, Any]):
        self._append("files.jsonl", record)
        self.stats.files += 1

    def record_scan(self, summary: Dict[str, Any]):
        self._append("scans.jsonl", summary)
        self.stats.scans += 1
        self.stats.last_scan = summary.get("timestamp")

    def store_file_content(self, path: str, content: str) -> Optional[Dict[str, Any]]:
        if self.diskless:
            return None
        files_dir = self._files_dir()
        if not files_dir:
            return None
        encoded = content.encode("utf-8", errors="ignore")
        content_hash = hashlib.sha256(encoded).hexdigest()
        content_path = files_dir / f"{content_hash}.txt"
        if not content_path.exists():
            try:
                content_path.write_text(content, encoding="utf-8", errors="ignore")
            except PermissionError as e:
                logger.warning(f"Failed to store file content: {e}")
                return None
        return {
            "content_ref": str(content_path),
            "content_hash": content_hash,
            "content_bytes": len(encoded)
        }

    def _append(self, filename: str, data: Dict[str, Any]):
        if self.diskless:
            return
        path = self._path(filename)
        if not path:
            return
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, default=str) + "\n")
        except PermissionError as e:
            logger.warning(f"Failed to append memory record: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "diskless": self.diskless,
            "base_path": str(self.base) if self.base else None,
            "events": self.stats.events,
            "files": self.stats.files,
            "scans": self.stats.scans,
            "last_event": self.stats.last_event,
            "last_scan": self.stats.last_scan
        }

memory_vault = MemoryVault()
