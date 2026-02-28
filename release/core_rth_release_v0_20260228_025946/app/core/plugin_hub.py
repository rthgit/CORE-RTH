"""
Plugin candidate hub sourced from high-ranking local projects.
Activation is proposal-only unless explicitly approved.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
import hashlib
import json
from pathlib import Path
import tempfile
import logging

from .permissions import permission_gate, Capability, RiskLevel
from .memory_vault import memory_vault
from .root_policy import load_strategic_roots, is_within_roots, normalize_path

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    DISABLED = "disabled"


@dataclass
class PluginCandidate:
    plugin_id: str
    root: str
    score: float
    source: str
    rationale: List[str] = field(default_factory=list)
    status: PluginStatus = PluginStatus.CANDIDATE
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    activated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "root": self.root,
            "score": self.score,
            "source": self.source,
            "rationale": self.rationale,
            "status": self.status.value,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PluginCandidate":
        status_raw = str(data.get("status", PluginStatus.CANDIDATE.value))
        try:
            status = PluginStatus(status_raw)
        except Exception:
            status = PluginStatus.CANDIDATE
        return PluginCandidate(
            plugin_id=str(data.get("plugin_id", "")),
            root=str(data.get("root", "")),
            score=float(data.get("score", 0.0)),
            source=str(data.get("source", "ranking")),
            rationale=list(data.get("rationale", []) or []),
            status=status,
            created_at=str(data.get("created_at", datetime.now().isoformat())),
            activated_at=data.get("activated_at"),
        )


class PluginHub:
    def __init__(self):
        self.plugins: Dict[str, PluginCandidate] = {}
        self._load_state()

    def sync_from_high_ranked(self, high_ranked: List[Dict[str, Any]]) -> Dict[str, Any]:
        strategic_roots = load_strategic_roots()
        created = 0
        skipped_out_of_scope = 0
        updated = 0
        for entry in high_ranked:
            root = str(entry.get("root", "")).strip()
            if not root:
                continue
            if not is_within_roots(root, strategic_roots):
                skipped_out_of_scope += 1
                continue
            score = float(entry.get("score", 0.0))
            plugin_id = self._plugin_id(root)
            reasons = entry.get("reasons", [])
            source = str(entry.get("source", "ranking"))
            if plugin_id in self.plugins:
                plugin = self.plugins[plugin_id]
                plugin.score = max(plugin.score, score)
                plugin.rationale = reasons or plugin.rationale
                updated += 1
            else:
                self.plugins[plugin_id] = PluginCandidate(
                    plugin_id=plugin_id,
                    root=root,
                    score=score,
                    source=source,
                    rationale=reasons,
                )
                created += 1
        self._save_state()
        memory_vault.record_event("plugin_sync", {"created": created, "updated": updated})
        return {
            "created": created,
            "updated": updated,
            "skipped_out_of_scope": skipped_out_of_scope,
            "total": len(self.plugins),
            "strategic_roots": strategic_roots,
        }

    def list_plugins(self, min_score: float = 0.0) -> List[Dict[str, Any]]:
        items = [p for p in self.plugins.values() if p.score >= min_score]
        items.sort(key=lambda x: x.score, reverse=True)
        return [p.to_dict() for p in items]

    def propose_activation(self, plugin_id: str, reason: str) -> Dict[str, Any]:
        plugin = self.plugins.get(plugin_id)
        if not plugin:
            raise ValueError("plugin_id not found")
        # Guard: do not allow activation of out-of-scope plugins.
        strategic_roots = load_strategic_roots()
        if not is_within_roots(plugin.root, strategic_roots):
            raise ValueError(f"plugin root out of scope by policy: {plugin.root}")
        request = permission_gate.propose(
            capability=Capability.FILESYSTEM_WRITE,
            action="plugin_activation",
            scope={"plugin_id": plugin_id, "root": plugin.root},
            reason=reason,
            risk=RiskLevel.HIGH,
        )
        return request.to_dict()

    def weed_kill(self, scope_roots: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Disable plugins that are out of strategic scope.
        Optionally also disable nested duplicates if a parent plugin exists.
        """
        strategic_roots = scope_roots or load_strategic_roots()

        disabled = []
        kept = []
        changed = 0

        # First pass: out-of-scope plugins.
        for plugin in self.plugins.values():
            if is_within_roots(plugin.root, strategic_roots):
                kept.append(plugin)
                continue
            if plugin.status != PluginStatus.DISABLED:
                plugin.status = PluginStatus.DISABLED
                plugin.activated_at = plugin.activated_at  # preserve audit field
                changed += 1
            disabled.append(plugin)

        # Second pass: nested duplicates (keep the shortest root when parent exists).
        kept_sorted = sorted(kept, key=lambda p: len(normalize_path(p.root)))
        keep_roots: List[str] = []
        nested_disabled = []
        for plugin in kept_sorted:
            r = normalize_path(plugin.root)
            if any(r == parent or r.startswith(parent + "/") for parent in keep_roots):
                if plugin.status != PluginStatus.DISABLED:
                    plugin.status = PluginStatus.DISABLED
                    changed += 1
                nested_disabled.append(plugin)
            else:
                keep_roots.append(r)

        self._save_state()
        payload = {
            "timestamp": datetime.now().isoformat(),
            "strategic_roots": strategic_roots,
            "changed": changed,
            "disabled_out_of_scope": [p.to_dict() for p in disabled],
            "disabled_nested": [p.to_dict() for p in nested_disabled],
            "kept": [p.to_dict() for p in self.plugins.values() if p.status != PluginStatus.DISABLED],
        }
        memory_vault.record_event("plugin_weedkill", {
            "changed": changed,
            "disabled_out_of_scope": len(disabled),
            "disabled_nested": len(nested_disabled),
            "kept": len(payload["kept"]),
        })
        return payload

    def activate(self, request_id: str) -> Dict[str, Any]:
        if not permission_gate.check(request_id):
            return {"status": "denied", "request_id": request_id}
        request = permission_gate.requests.get(request_id)
        if not request:
            return {"status": "denied", "request_id": request_id}
        plugin_id = request.scope.get("plugin_id")
        plugin = self.plugins.get(plugin_id)
        if not plugin:
            return {"status": "not_found", "plugin_id": plugin_id}
        plugin.status = PluginStatus.ACTIVE
        plugin.activated_at = datetime.now().isoformat()
        self._save_state()
        memory_vault.record_event("plugin_activated", plugin.to_dict())
        return {"status": "active", "plugin": plugin.to_dict()}

    def _plugin_id(self, root: str) -> str:
        return f"plg_{hashlib.md5(root.lower().encode()).hexdigest()[:10]}"

    def _state_path(self) -> Optional[Path]:
        candidates = [
            Path("storage") / "plugins",
            Path("storage_runtime") / "plugins",
            Path(tempfile.gettempdir()) / "rth_core" / "plugins",
        ]
        for base in candidates:
            try:
                base.mkdir(parents=True, exist_ok=True)
                probe = base / ".write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return base / "plugin_hub.json"
            except Exception:
                continue
        return None

    def _save_state(self):
        path = self._state_path()
        if not path:
            return
        payload = {
            "saved_at": datetime.now().isoformat(),
            "plugins": [p.to_dict() for p in self.plugins.values()],
        }
        try:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save plugin hub state: {e}")

    def _load_state(self):
        path = self._state_path()
        if not path or not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            loaded = 0
            for item in payload.get("plugins", []):
                plugin = PluginCandidate.from_dict(item)
                if not plugin.plugin_id or not plugin.root:
                    continue
                self.plugins[plugin.plugin_id] = plugin
                loaded += 1
            if loaded:
                logger.info(f"PluginHub loaded {loaded} plugins from state")
        except Exception as e:
            logger.warning(f"Failed to load plugin hub state: {e}")


plugin_hub = PluginHub()
