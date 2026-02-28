"""
Public plugin registry + manifest validator (v0).

Purpose:
- ship a credible public plugin ecosystem even without proprietary internal apps
- maintain a compatibility matrix for major commercial tools
- validate/register plugin manifests under Guardian control
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

from .permissions import permission_gate, Capability, RiskLevel

logger = logging.getLogger(__name__)


VALID_CATEGORY = {
    "development",
    "office",
    "communication",
    "knowledge",
    "browser",
    "storage",
    "database",
    "ai_runtime",
    "security",
    "automation",
    "other",
}
VALID_SURFACE = {"cli", "rest", "browser", "filesystem", "email", "database", "hybrid"}
VALID_TIER = {"first_class", "verified", "community", "fallback_browser"}
VALID_CAP = {
    "filesystem_scan",
    "filesystem_read",
    "filesystem_write",
    "process_exec",
    "network_access",
    "system_modify",
    "data_export",
    "plugin_runtime",
}
VALID_RISK = {"low", "medium", "high", "critical"}
VALID_SEVERITY = {"lenient", "balanced", "strict", "paranoid"}
VALID_INSTALL_STATE = {"planned", "registered", "enabled", "disabled", "broken"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _s(v: Any) -> str:
    return str(v or "").strip()


def _uniq(xs: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for x in xs:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _manifest_base(
    *,
    plugin_id: str,
    name: str,
    vendor: str,
    category: str,
    surface: str,
    tier: str,
    apps: List[Dict[str, Any]],
    capabilities: List[str],
    risk: str = "high",
    notes: str = "",
    healthcheck: Optional[Dict[str, Any]] = None,
    driver: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "manifest_version": "rth.plugin.v0",
        "id": plugin_id,
        "name": name,
        "version": "0.1.0",
        "vendor": vendor,
        "category": category,
        "surface": surface,
        "compatibility_tier": tier,
        "supported_apps": apps,
        "capabilities_requested": capabilities,
        "risk_class": risk,
        "consent_defaults": {
            "proposal_required": True,
            "dry_run_supported": True,
            "owner_approval_required": True,
            "suggested_guardian_severity_min": "balanced",
        },
        "config_schema": {},
        "healthcheck": dict(healthcheck or {"type": "none"}),
        "driver": dict(driver or {}),
        "actions": [
            {
                "id": "healthcheck",
                "label": "Healthcheck",
                "capability": "filesystem_read" if "filesystem_read" in capabilities else capabilities[0],
                "risk": "low",
                "dry_run_supported": True,
                "description": "Read-only healthcheck/probe of plugin target surface",
            }
        ],
        "notes": notes,
    }


class PluginRegistryPublic:
    def __init__(self):
        self._state = self._default_state()
        self._load_state()

    def status(self) -> Dict[str, Any]:
        items = self.catalog()["items"]
        builtin = [x for x in items if str(x.get("registry_source")) == "builtin"]
        custom = [x for x in items if str(x.get("registry_source")) == "registered"]
        by_tier: Dict[str, int] = {}
        by_health: Dict[str, int] = {}
        by_install: Dict[str, int] = {}
        enabled_total = 0
        for it in items:
            t = str(it.get("compatibility_tier") or "unknown")
            by_tier[t] = by_tier.get(t, 0) + 1
            hs = str((it.get("last_healthcheck") or {}).get("status") or "never")
            by_health[hs] = by_health.get(hs, 0) + 1
            st = str(it.get("install_state") or "unknown")
            by_install[st] = by_install.get(st, 0) + 1
            if bool(it.get("enabled")):
                enabled_total += 1
        return {
            "module": "plugin_registry_public",
            "version": 1,
            "registry_path": str(self._state_path()) if self._state_path() else None,
            "updated_at": self._state.get("updated_at"),
            "catalog_total": len(items),
            "builtin_total": len(builtin),
            "registered_total": len(custom),
            "tiers": by_tier,
            "health": by_health,
            "install_states": by_install,
            "enabled_total": enabled_total,
            "schema_path": str(self._schema_path()) if self._schema_path() else None,
        }

    def schema_document(self) -> Dict[str, Any]:
        p = self._schema_path()
        if not p or not p.exists():
            return {"status": "missing", "path": str(p) if p else None}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return {"status": "ok", "path": str(p), "schema": data}
        except Exception as e:
            return {"status": "error", "path": str(p), "error": str(e)}

    def catalog(self) -> Dict[str, Any]:
        merged: Dict[str, Dict[str, Any]] = {}
        for item in self._builtin_catalog():
            manifest = dict(item["manifest"])
            pid = str(manifest.get("id") or "")
            ps = self._plugin_state_snapshot(pid)
            install_state = self._resolve_install_state(
                plugin_id=pid,
                default_state="planned",
                legacy_install_state=None,
            )
            merged[manifest["id"]] = {
                **manifest,
                "registry_source": "builtin",
                "install_state": install_state,
                "enabled": bool(ps.get("enabled")) if isinstance(ps, dict) else False,
                "registry_meta": dict(item.get("meta") or {}),
                "last_healthcheck": self._healthcheck_snapshot(pid),
            }
        for item in self._state.get("items", []):
            if not isinstance(item, dict):
                continue
            manifest = item.get("manifest") if isinstance(item.get("manifest"), dict) else None
            if not manifest:
                continue
            pid = _s(manifest.get("id"))
            if not pid:
                continue
            ps = self._plugin_state_snapshot(pid)
            legacy_install = str(item.get("install_state") or "registered")
            install_state = self._resolve_install_state(
                plugin_id=pid,
                default_state="registered",
                legacy_install_state=legacy_install,
            )
            merged[pid] = {
                **manifest,
                "registry_source": "registered",
                "install_state": install_state,
                "enabled": bool(ps.get("enabled")) if isinstance(ps, dict) else install_state == "enabled",
                "registry_meta": {
                    "registered_at": item.get("registered_at"),
                    "updated_at": item.get("updated_at"),
                    "notes": item.get("notes", ""),
                    "overrides_builtin": bool(pid in {b["manifest"]["id"] for b in self._builtin_catalog()}),
                },
                "last_healthcheck": self._healthcheck_snapshot(pid),
            }
        rows = list(merged.values())
        rows.sort(key=lambda x: (x.get("category", ""), x.get("vendor", ""), x.get("name", "")))
        return {"status": "ok", "count": len(rows), "items": rows}

    def compatibility_matrix(self) -> Dict[str, Any]:
        items = self.catalog()["items"]
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for item in items:
            cat = str(item.get("category") or "other")
            groups.setdefault(cat, []).append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "vendor": item.get("vendor"),
                    "compatibility_tier": item.get("compatibility_tier"),
                    "surface": item.get("surface"),
                    "registry_source": item.get("registry_source"),
                    "install_state": item.get("install_state"),
                    "supported_apps": [a.get("name") for a in (item.get("supported_apps") or []) if isinstance(a, dict)],
                }
            )
        for cat in groups:
            groups[cat].sort(key=lambda x: (x["compatibility_tier"], x["vendor"], x["name"]))
        priority_targets = [
            "anthropic.claude_code",
            "anthropic.claude_cowork",
            "anthropic.claude_mem",
            "ai_ide.cursor",
            "ai_ide.windsurf",
            "ai_ide.trae",
            "ai_ide.lovable",
            "ai_ide.antigravity",
            "llm_runtime.llama_cpp",
            "llm_provider.groq_cloud",
        ]
        highlighted = [it for it in items if str(it.get("id")) in set(priority_targets)]
        highlighted.sort(key=lambda x: priority_targets.index(str(x.get("id"))) if str(x.get("id")) in priority_targets else 999)
        return {
            "status": "ok",
            "categories": groups,
            "priority_targets": highlighted,
            "count": len(items),
        }

    def validate_manifest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ok, errors, warnings = self._validate_manifest_payload(payload)
        return {
            "ok": ok,
            "errors": errors,
            "warnings": warnings,
            "summary": self._manifest_summary(payload) if ok else None,
        }

    def register_manifest(
        self,
        payload: Dict[str, Any],
        *,
        reason: str = "Register public plugin manifest",
        confirm_owner: bool = True,
        decided_by: str = "owner",
    ) -> Dict[str, Any]:
        validation = self.validate_manifest(payload)
        if not validation["ok"]:
            return {"status": "invalid", "validation": validation}
        manifest = self._normalize_manifest(payload)
        safe_reason = self._ensure_change_control_marker(reason)
        req = permission_gate.propose(
            capability=Capability.FILESYSTEM_WRITE,
            action="plugins_registry_register_manifest",
            scope={
                "plugin_id": manifest["id"],
                "target_path": str(self._state_path()) if self._state_path() else None,
                "category": manifest.get("category"),
                "compatibility_tier": manifest.get("compatibility_tier"),
            },
            reason=safe_reason,
            risk=RiskLevel.HIGH,
        )
        out: Dict[str, Any] = {"proposal": req.to_dict(), "validation": validation}
        if not confirm_owner:
            out["status"] = "proposal_only"
            return out
        decision = permission_gate.approve(req.request_id, decided_by=decided_by)
        out["decision"] = decision.to_dict()
        if decision.decision.value != "approved":
            out["status"] = "denied"
            return out
        self._upsert_item(manifest)
        self._upsert_plugin_state(
            manifest["id"],
            enabled=True,
            install_state="registered",
            source="register_manifest",
        )
        out["status"] = "ok"
        out["manifest"] = manifest
        return out

    def delete_manifest(
        self,
        plugin_id: str,
        *,
        reason: str = "Delete public plugin manifest",
        confirm_owner: bool = True,
        decided_by: str = "owner",
    ) -> Dict[str, Any]:
        pid = _s(plugin_id)
        if not pid:
            return {"status": "invalid", "detail": "plugin_id required"}
        idx = self._find_index(pid)
        if idx < 0:
            return {"status": "not_found", "plugin_id": pid}
        safe_reason = self._ensure_change_control_marker(reason)
        req = permission_gate.propose(
            capability=Capability.FILESYSTEM_WRITE,
            action="plugins_registry_delete_manifest",
            scope={"plugin_id": pid, "target_path": str(self._state_path()) if self._state_path() else None},
            reason=safe_reason,
            risk=RiskLevel.HIGH,
        )
        out: Dict[str, Any] = {"proposal": req.to_dict()}
        if not confirm_owner:
            out["status"] = "proposal_only"
            return out
        decision = permission_gate.approve(req.request_id, decided_by=decided_by)
        out["decision"] = decision.to_dict()
        if decision.decision.value != "approved":
            out["status"] = "denied"
            return out
        removed = self._state["items"].pop(idx)
        self._plugin_state_bucket().pop(pid, None)
        self._healthcheck_bucket().pop(pid, None)
        self._state["updated_at"] = _now()
        self._save_state()
        out["status"] = "ok"
        out["removed"] = removed
        return out

    def set_plugin_state(
        self,
        *,
        plugin_id: str,
        enabled: Optional[bool] = None,
        install_state: Optional[str] = None,
        reason: str = "Update plugin install state",
        confirm_owner: bool = True,
        decided_by: str = "owner",
    ) -> Dict[str, Any]:
        pid = _s(plugin_id)
        item = next((x for x in self.catalog().get("items", []) if _s(x.get("id")) == pid), None)
        if not item:
            return {"status": "not_found", "plugin_id": pid}
        requested_state = _s(install_state).lower() if install_state is not None else None
        if requested_state and requested_state not in VALID_INSTALL_STATE:
            return {"status": "invalid", "detail": "install_state invalid", "valid_install_states": sorted(VALID_INSTALL_STATE)}
        req = permission_gate.propose(
            capability=Capability.FILESYSTEM_WRITE,
            action="plugins_registry_set_state",
            scope={
                "plugin_id": pid,
                "target_path": str(self._state_path()) if self._state_path() else None,
                "enabled": enabled,
                "install_state": requested_state,
            },
            reason=self._ensure_change_control_marker(reason),
            risk=RiskLevel.MEDIUM,
        )
        out: Dict[str, Any] = {"proposal": req.to_dict(), "plugin_id": pid}
        if not confirm_owner:
            out["status"] = "proposal_only"
            return out
        dec = permission_gate.approve(req.request_id, decided_by=decided_by)
        out["decision"] = dec.to_dict()
        if dec.decision.value != "approved":
            out["status"] = "denied"
            return out
        snapshot = self._upsert_plugin_state(
            pid,
            enabled=enabled,
            install_state=requested_state,
            source="manual_override",
        )
        out["status"] = "ok"
        out["plugin_state"] = snapshot
        return out

    def driver_action(
        self,
        *,
        plugin_id: str,
        action: str,
        timeout_sec: float = 6.0,
        reason: str = "Run plugin driver action",
        confirm_owner: bool = True,
        decided_by: str = "owner",
    ) -> Dict[str, Any]:
        pid = _s(plugin_id)
        op = _s(action).lower()
        if op not in {"install", "enable", "disable"}:
            return {"status": "invalid", "detail": "action must be install|enable|disable", "action": op}
        manifest = self._catalog_manifest(pid)
        if not manifest:
            return {"status": "not_found", "plugin_id": pid}

        driver_cfg = self._driver_config(manifest, op)
        if not driver_cfg:
            return {
                "status": "not_supported",
                "plugin_id": pid,
                "action": op,
                "detail": f"no driver configuration for action '{op}'",
            }

        cap = self._driver_capability(driver_cfg, op)
        risk = self._driver_risk(driver_cfg, op)
        action_name = f"plugins_registry_driver_{op}" if cap == Capability.PROCESS_EXEC else "plugins_registry_set_state"
        req = permission_gate.propose(
            capability=cap,
            action=action_name,
            scope={
                "plugin_id": pid,
                "driver_action": op,
                "driver_type": _s(driver_cfg.get("type") or "unknown"),
                "commands": list(driver_cfg.get("commands") or [])[:8],
                "target_path": str(self._state_path()) if self._state_path() else None,
            },
            reason=self._ensure_change_control_marker(reason),
            risk=risk,
        )
        out: Dict[str, Any] = {
            "proposal": req.to_dict(),
            "plugin_id": pid,
            "action": op,
            "driver_config": driver_cfg,
        }
        if not confirm_owner:
            out["status"] = "proposal_only"
            return out
        dec = permission_gate.approve(req.request_id, decided_by=decided_by)
        out["decision"] = dec.to_dict()
        if dec.decision.value != "approved":
            out["status"] = "denied"
            return out
        result = self._execute_driver_action(manifest, op, driver_cfg, timeout_sec=timeout_sec)
        out["status"] = "ok"
        out["result"] = result
        return out

    def healthcheck_batch(
        self,
        *,
        plugin_ids: Optional[List[str]] = None,
        priority_only: bool = False,
        category: str = "",
        pack: str = "",
        tier: str = "",
        install_state: str = "",
        enabled_only: bool = False,
        include_not_configured: bool = False,
        limit: int = 20,
        timeout_sec: float = 2.5,
        reason: str = "Run plugin healthcheck batch",
        confirm_owner: bool = True,
        decided_by: str = "owner",
    ) -> Dict[str, Any]:
        rows = self.catalog().get("items", [])
        wanted_ids = {_s(x) for x in (plugin_ids or []) if _s(x)}
        cat = _s(category).lower()
        pk = _s(pack).lower()
        tr = _s(tier).lower()
        st = _s(install_state).lower()
        selected: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            pid = _s(row.get("id"))
            meta = row.get("registry_meta") if isinstance(row.get("registry_meta"), dict) else {}
            if wanted_ids and pid not in wanted_ids:
                continue
            if priority_only and str(meta.get("priority") or "").upper() != "P0":
                continue
            if cat and _s(row.get("category")).lower() != cat:
                continue
            if pk and _s(meta.get("pack")).lower() != pk:
                continue
            if tr and _s(row.get("compatibility_tier")).lower() != tr:
                continue
            if st and _s(row.get("install_state")).lower() != st:
                continue
            if enabled_only and not bool(row.get("enabled")):
                continue
            if not include_not_configured:
                hc = row.get("healthcheck") if isinstance(row.get("healthcheck"), dict) else {}
                if _s(hc.get("type")).lower() in {"", "none"}:
                    continue
            selected.append(row)
            if len(selected) >= max(1, min(int(limit or 20), 100)):
                break

        results: List[Dict[str, Any]] = []
        counts = {"ok": 0, "error": 0, "denied": 0, "proposal_only": 0, "not_configured": 0, "other": 0}
        for row in selected:
            pid = _s(row.get("id"))
            res = self.healthcheck_plugin(
                plugin_id=pid,
                timeout_sec=timeout_sec,
                reason=f"{reason}: {pid}",
                confirm_owner=confirm_owner,
                decided_by=decided_by,
            )
            item = {
                "plugin_id": pid,
                "name": row.get("name"),
                "status": res.get("status"),
                "proposal": {"request_id": ((res.get("proposal") or {}).get("request_id"))},
                "decision": {"decision": ((res.get("decision") or {}).get("decision"))} if isinstance(res.get("decision"), dict) else None,
            }
            r = res.get("result") if isinstance(res.get("result"), dict) else None
            if r:
                item["health_result"] = {
                    "status": r.get("status"),
                    "ok": r.get("ok"),
                    "summary": r.get("summary"),
                    "healthcheck_type": r.get("healthcheck_type"),
                }
            results.append(item)

            if res.get("status") in {"denied", "proposal_only"}:
                counts[str(res.get("status"))] = counts.get(str(res.get("status")), 0) + 1
            elif r:
                key = str(r.get("status") or "other")
                counts[key] = counts.get(key, 0) + 1
            else:
                counts["other"] = counts.get("other", 0) + 1

        return {
            "status": "ok",
            "filters": {
                "plugin_ids": sorted(wanted_ids),
                "priority_only": bool(priority_only),
                "category": cat or None,
                "pack": pk or None,
                "tier": tr or None,
                "install_state": st or None,
                "enabled_only": bool(enabled_only),
                "include_not_configured": bool(include_not_configured),
                "limit": max(1, min(int(limit or 20), 100)),
            },
            "selected_count": len(selected),
            "results_count": len(results),
            "counts": counts,
            "results": results,
        }

    def healthcheck_plugin(
        self,
        *,
        plugin_id: str = "",
        manifest: Optional[Dict[str, Any]] = None,
        timeout_sec: float = 2.5,
        reason: str = "Run plugin healthcheck",
        confirm_owner: bool = True,
        decided_by: str = "owner",
    ) -> Dict[str, Any]:
        resolved_manifest: Optional[Dict[str, Any]] = None
        source = ""
        if manifest is not None:
            validation = self.validate_manifest(manifest)
            if not validation["ok"]:
                return {"status": "invalid", "validation": validation}
            resolved_manifest = self._normalize_manifest(manifest)
            source = "payload"
        else:
            resolved_manifest = self._catalog_manifest(_s(plugin_id))
            if not resolved_manifest:
                return {"status": "not_found", "plugin_id": _s(plugin_id)}
            source = "catalog"

        hc = resolved_manifest.get("healthcheck") if isinstance(resolved_manifest.get("healthcheck"), dict) else {"type": "none"}
        hc_type = _s(hc.get("type")).lower() or "none"
        cap = self._healthcheck_capability(resolved_manifest, hc_type)
        risk = self._healthcheck_risk(resolved_manifest, hc_type)
        safe_reason = self._ensure_change_control_marker(reason)
        action_name = "plugins_registry_healthcheck_exec" if cap == Capability.PROCESS_EXEC else "plugins_registry_healthcheck"
        req = permission_gate.propose(
            capability=cap,
            action=action_name,
            scope={
                "plugin_id": resolved_manifest.get("id"),
                "healthcheck_type": hc_type,
                "surface": resolved_manifest.get("surface"),
                "category": resolved_manifest.get("category"),
                "target_urls": list(hc.get("urls") or [])[:8] if isinstance(hc, dict) else [],
                "commands": list(hc.get("commands") or [])[:8] if isinstance(hc, dict) else [],
                "paths": list(hc.get("paths") or [])[:8] if isinstance(hc, dict) else [],
            },
            reason=safe_reason,
            risk=risk,
        )
        out: Dict[str, Any] = {
            "proposal": req.to_dict(),
            "plugin": self._manifest_summary(resolved_manifest),
            "healthcheck_config": hc,
            "source": source,
        }
        if not confirm_owner:
            out["status"] = "proposal_only"
            return out
        decision = permission_gate.approve(req.request_id, decided_by=decided_by)
        out["decision"] = decision.to_dict()
        if decision.decision.value != "approved":
            out["status"] = "denied"
            return out

        result = self._run_healthcheck(resolved_manifest, timeout_sec=timeout_sec)
        out["status"] = "ok"
        out["result"] = result
        self._save_healthcheck_snapshot(_s(resolved_manifest.get("id")), result)
        return out

    # internals
    def _default_state(self) -> Dict[str, Any]:
        return {"version": 1, "updated_at": _now(), "items": [], "healthchecks": {}, "plugin_states": {}}

    def _state_path(self) -> Optional[Path]:
        for base in [
            Path("storage") / "plugins_public",
            Path("storage_runtime") / "plugins_public",
            Path(tempfile.gettempdir()) / "rth_core" / "plugins_public",
        ]:
            try:
                base.mkdir(parents=True, exist_ok=True)
                probe = base / ".write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return base / "registry.json"
            except Exception:
                continue
        return None

    def _schema_path(self) -> Optional[Path]:
        p = Path("docs") / "RTH_PLUGIN_MANIFEST_SCHEMA_V0.json"
        return p if p.exists() else None

    def _load_state(self) -> None:
        path = self._state_path()
        if not path or not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._state.update(data)
                if not isinstance(self._state.get("items"), list):
                    self._state["items"] = []
                if not isinstance(self._state.get("healthchecks"), dict):
                    self._state["healthchecks"] = {}
                if not isinstance(self._state.get("plugin_states"), dict):
                    self._state["plugin_states"] = {}
        except Exception as e:
            logger.warning(f"Plugin registry load failed: {e}")

    def _save_state(self) -> None:
        path = self._state_path()
        if not path:
            return
        try:
            path.write_text(json.dumps(self._state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception as e:
            logger.warning(f"Plugin registry save failed: {e}")

    def _catalog_manifest(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        pid = _s(plugin_id)
        if not pid:
            return None
        for item in self.catalog().get("items", []):
            if not isinstance(item, dict):
                continue
            if _s(item.get("id")) != pid:
                continue
            manifest = dict(item)
            manifest.pop("registry_source", None)
            manifest.pop("install_state", None)
            manifest.pop("registry_meta", None)
            manifest.pop("last_healthcheck", None)
            manifest.pop("enabled", None)
            return manifest
        return None

    def _plugin_state_bucket(self) -> Dict[str, Dict[str, Any]]:
        if not isinstance(self._state.get("plugin_states"), dict):
            self._state["plugin_states"] = {}
        return self._state["plugin_states"]

    def _plugin_state_snapshot(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        pid = _s(plugin_id)
        if not pid:
            return None
        row = self._plugin_state_bucket().get(pid)
        return dict(row) if isinstance(row, dict) else None

    def _resolve_install_state(self, *, plugin_id: str, default_state: str, legacy_install_state: Optional[str]) -> str:
        ps = self._plugin_state_snapshot(plugin_id)
        if isinstance(ps, dict):
            st = _s(ps.get("install_state")).lower()
            if st in VALID_INSTALL_STATE:
                return st
            if "enabled" in ps:
                return "enabled" if bool(ps.get("enabled")) else "disabled"
        legacy = _s(legacy_install_state).lower()
        if legacy in VALID_INSTALL_STATE:
            return legacy
        return default_state if default_state in VALID_INSTALL_STATE else "planned"

    def _upsert_plugin_state(
        self,
        plugin_id: str,
        *,
        enabled: Optional[bool] = None,
        install_state: Optional[str] = None,
        source: str = "system",
    ) -> Dict[str, Any]:
        pid = _s(plugin_id)
        bucket = self._plugin_state_bucket()
        cur = dict(bucket.get(pid) or {})
        if enabled is not None:
            cur["enabled"] = bool(enabled)
        st = _s(install_state).lower() if install_state is not None else ""
        if st in VALID_INSTALL_STATE:
            cur["install_state"] = st
            if enabled is None and st in {"enabled", "disabled", "broken"}:
                cur["enabled"] = (st == "enabled")
        elif "install_state" not in cur:
            cur["install_state"] = "registered"
        cur["updated_at"] = _now()
        cur["source"] = source
        bucket[pid] = cur
        self._state["updated_at"] = _now()
        self._save_state()
        return dict(cur)

    def _healthcheck_bucket(self) -> Dict[str, Dict[str, Any]]:
        if not isinstance(self._state.get("healthchecks"), dict):
            self._state["healthchecks"] = {}
        return self._state["healthchecks"]

    def _healthcheck_snapshot(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        pid = _s(plugin_id)
        if not pid:
            return None
        row = self._healthcheck_bucket().get(pid)
        return dict(row) if isinstance(row, dict) else None

    def _save_healthcheck_snapshot(self, plugin_id: str, result: Dict[str, Any]) -> None:
        pid = _s(plugin_id)
        if not pid:
            return
        summary = {
            "checked_at": result.get("checked_at") or _now(),
            "status": result.get("status"),
            "ok": bool(result.get("ok")),
            "healthcheck_type": result.get("healthcheck_type"),
            "summary": result.get("summary"),
        }
        bucket = self._healthcheck_bucket()
        bucket[pid] = summary
        self._reconcile_install_state_from_healthcheck(pid, summary)
        self._state["updated_at"] = _now()
        self._save_state()

    def _reconcile_install_state_from_healthcheck(self, plugin_id: str, summary: Dict[str, Any]) -> None:
        pid = _s(plugin_id)
        if not pid or not isinstance(summary, dict):
            return
        current = self._plugin_state_snapshot(pid) or {}
        current_state = _s(current.get("install_state")).lower() or "planned"
        if current_state == "disabled":
            return
        hc_status = _s(summary.get("status")).lower()
        hc_ok = bool(summary.get("ok"))
        if hc_ok:
            self._plugin_state_bucket()[pid] = {
                **current,
                "enabled": True,
                "install_state": "enabled",
                "updated_at": _now(),
                "source": "healthcheck_ok",
            }
            return
        if hc_status in {"error", "unsupported"}:
            self._plugin_state_bucket()[pid] = {
                **current,
                "enabled": False,
                "install_state": "broken",
                "updated_at": _now(),
                "source": "healthcheck_fail",
            }

    def _healthcheck_capability(self, manifest: Dict[str, Any], hc_type: str) -> Capability:
        action = self._healthcheck_action(manifest)
        cap_name = _s(action.get("capability")).lower() if isinstance(action, dict) else ""
        mapping = {
            "filesystem_read": Capability.FILESYSTEM_READ,
            "network_access": Capability.NETWORK_ACCESS,
            "process_exec": Capability.PROCESS_EXEC,
            "filesystem_write": Capability.FILESYSTEM_WRITE,
            "system_modify": Capability.SYSTEM_MODIFY,
        }
        if hc_type == "composite":
            hc = manifest.get("healthcheck") if isinstance(manifest.get("healthcheck"), dict) else {}
            subtypes = [_s(x.get("type")).lower() for x in (hc.get("checks") or []) if isinstance(x, dict)]
            if any(t in {"command_exec", "command_version"} for t in subtypes):
                return Capability.PROCESS_EXEC
            if any(t in {"http_get", "http_json", "http_json_signature"} for t in subtypes):
                return Capability.NETWORK_ACCESS
            return Capability.FILESYSTEM_READ
        if hc_type in {"http_get", "http_json", "http_json_signature"}:
            return Capability.NETWORK_ACCESS
        if hc_type in {"command_exists", "path_exists", "none"}:
            return Capability.FILESYSTEM_READ
        if hc_type in {"command_exec", "command_version"}:
            return Capability.PROCESS_EXEC
        if cap_name in mapping:
            return mapping[cap_name]
        return Capability.FILESYSTEM_READ

    def _healthcheck_risk(self, manifest: Dict[str, Any], hc_type: str) -> RiskLevel:
        action = self._healthcheck_action(manifest)
        risk_name = _s(action.get("risk")).lower() if isinstance(action, dict) else "low"
        mapping = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
        }
        if hc_type in {"command_exec", "command_version"} and risk_name == "low":
            return RiskLevel.MEDIUM
        if hc_type == "composite":
            hc = manifest.get("healthcheck") if isinstance(manifest.get("healthcheck"), dict) else {}
            subtypes = [_s(x.get("type")).lower() for x in (hc.get("checks") or []) if isinstance(x, dict)]
            if any(t in {"command_exec", "command_version"} for t in subtypes) and risk_name in {"low", "medium"}:
                return RiskLevel.HIGH if risk_name == "medium" else RiskLevel.MEDIUM
            if any(t in {"http_get", "http_json", "http_json_signature"} for t in subtypes) and risk_name == "low":
                return RiskLevel.MEDIUM
        return mapping.get(risk_name, RiskLevel.LOW)

    def _healthcheck_action(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        for action in manifest.get("actions") or []:
            if not isinstance(action, dict):
                continue
            if _s(action.get("id")) == "healthcheck":
                return action
        return {}

    def _run_healthcheck(self, manifest: Dict[str, Any], *, timeout_sec: float = 2.5) -> Dict[str, Any]:
        hc = manifest.get("healthcheck") if isinstance(manifest.get("healthcheck"), dict) else {"type": "none"}
        hc_type = _s(hc.get("type")).lower() or "none"
        plugin_id = _s(manifest.get("id"))
        checked_at = _now()
        timeout = max(0.2, min(float(timeout_sec or 2.5), 15.0))

        if hc_type == "composite":
            checks = [c for c in (hc.get("checks") or []) if isinstance(c, dict)]
            mode = _s(hc.get("mode")).lower() or "any"
            if mode not in {"any", "all"}:
                mode = "any"
            sub_results: List[Dict[str, Any]] = []
            for sub in checks[:20]:
                child = dict(manifest)
                child["healthcheck"] = dict(sub)
                sub_results.append(self._run_healthcheck(child, timeout_sec=timeout))
            oks = [bool(x.get("ok")) for x in sub_results]
            ok = (all(oks) if mode == "all" else any(oks)) if sub_results else False
            status = "ok" if ok else ("error" if sub_results else "not_configured")
            return {
                "status": status,
                "ok": ok,
                "plugin_id": plugin_id,
                "healthcheck_type": hc_type,
                "checked_at": checked_at,
                "summary": f"Composite {mode} {sum(1 for x in oks if x)}/{len(oks)} checks passed" if sub_results else "No composite checks configured",
                "mode": mode,
                "sub_results": sub_results,
            }
        if hc_type == "none":
            return {
                "status": "not_configured",
                "ok": False,
                "plugin_id": plugin_id,
                "healthcheck_type": hc_type,
                "checked_at": checked_at,
                "summary": "No healthcheck configured in manifest",
            }
        if hc_type == "command_exists":
            commands = [str(x).strip() for x in (hc.get("commands") or []) if str(x).strip()]
            attempts = []
            found = []
            for cmd in commands[:20]:
                path = shutil.which(cmd)
                row = {"command": cmd, "found": bool(path), "path": path}
                attempts.append(row)
                if path:
                    found.append(row)
            ok = bool(found)
            return {
                "status": "ok" if ok else "error",
                "ok": ok,
                "plugin_id": plugin_id,
                "healthcheck_type": hc_type,
                "checked_at": checked_at,
                "summary": f"Found {len(found)}/{len(attempts)} command candidates" if attempts else "No commands configured",
                "attempts": attempts,
                "found": found,
            }
        if hc_type == "command_version":
            commands = [str(x).strip() for x in (hc.get("commands") or []) if str(x).strip()]
            args = [str(x) for x in (hc.get("args") or ["--version"])]
            match_any = [str(x).strip().lower() for x in (hc.get("match_any") or []) if str(x).strip()]
            match_all = [str(x).strip().lower() for x in (hc.get("match_all") or []) if str(x).strip()]
            regex_any = [str(x).strip() for x in (hc.get("require_regex_any") or []) if str(x).strip()]
            regex_all = [str(x).strip() for x in (hc.get("require_regex_all") or []) if str(x).strip()]
            vendor_regex = _s(hc.get("vendor_regex"))
            vendor_group = int(hc.get("vendor_group") or 1)
            version_regex = _s(hc.get("version_regex"))
            version_group = int(hc.get("version_group") or 1)
            require_version = bool(hc.get("require_version", bool(version_regex)))
            attempts = []
            for cmd in commands[:20]:
                path = shutil.which(cmd)
                if not path:
                    attempts.append({"command": cmd, "found": False, "path": None})
                    continue
                probe = self._run_subprocess([path, *args], timeout=timeout)
                raw_text = f"{probe.get('stdout','')}\n{probe.get('stderr','')}"
                raw_with_identity = f"{raw_text}\n{cmd}\n{path}"
                text = raw_with_identity.lower()
                matched_any = (not match_any) or any(tok in text for tok in match_any)
                matched_all = (not match_all) or all(tok in text for tok in match_all)
                regex_any_ok = (not regex_any) or any(re.search(pat, raw_with_identity, flags=re.IGNORECASE) for pat in regex_any)
                regex_all_ok = (not regex_all) or all(re.search(pat, raw_with_identity, flags=re.IGNORECASE) for pat in regex_all)
                vendor_match = None
                if vendor_regex:
                    try:
                        vendor_match = re.search(vendor_regex, raw_with_identity, flags=re.IGNORECASE)
                    except re.error:
                        vendor_match = None
                version_match = None
                if version_regex:
                    try:
                        version_match = re.search(version_regex, raw_text, flags=re.IGNORECASE)
                    except re.error:
                        version_match = None
                if not version_match:
                    version_match = re.search(r"(\d+\.\d+(?:\.\d+)*)", raw_text)
                version_ok = bool(version_match) if require_version else True
                vendor_ok = bool(vendor_match) if vendor_regex else True
                row = {
                    "command": cmd,
                    "path": path,
                    **probe,
                    "matched_any": matched_any,
                    "matched_all": matched_all,
                    "regex_any_ok": regex_any_ok,
                    "regex_all_ok": regex_all_ok,
                    "vendor_regex_ok": vendor_ok,
                    "version_regex_ok": version_ok,
                    "vendor": (
                        vendor_match.group(vendor_group)
                        if (vendor_match and vendor_match.lastindex and vendor_group <= vendor_match.lastindex)
                        else (vendor_match.group(0) if vendor_match else None)
                    ),
                    "version": (version_match.group(version_group) if (version_match and version_match.lastindex and version_group <= version_match.lastindex) else (version_match.group(0) if version_match else None)),
                }
                attempts.append(row)
                if bool(probe.get("ok")) and matched_any and matched_all and regex_any_ok and regex_all_ok and vendor_ok and version_ok:
                    return {
                        "status": "ok",
                        "ok": True,
                        "plugin_id": plugin_id,
                        "healthcheck_type": hc_type,
                        "checked_at": checked_at,
                        "summary": f"Command version OK: {cmd}" + (f" {row['version']}" if row.get("version") else ""),
                        "attempts": attempts,
                        "matched": row,
                    }
            return {
                "status": "error",
                "ok": False,
                "plugin_id": plugin_id,
                "healthcheck_type": hc_type,
                "checked_at": checked_at,
                "summary": "No command matched version/signature requirements" if attempts else "No commands configured",
                "attempts": attempts,
            }
        if hc_type in {"http_get", "http_json"}:
            urls = [str(x).strip() for x in (hc.get("urls") or []) if str(x).strip()]
            headers = {"Accept": "application/json" if hc_type == "http_json" else "*/*"}
            attempts = []
            for url in urls[:20]:
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        raw = resp.read(2048).decode("utf-8", errors="replace")
                        attempts.append(
                            {
                                "url": url,
                                "ok": True,
                                "status_code": int(getattr(resp, "status", 200)),
                                "preview": raw[:300],
                            }
                        )
                        return {
                            "status": "ok",
                            "ok": True,
                            "plugin_id": plugin_id,
                            "healthcheck_type": hc_type,
                            "checked_at": checked_at,
                            "summary": f"HTTP probe OK: {url}",
                            "attempts": attempts,
                        }
                except urllib.error.HTTPError as e:
                    attempts.append({"url": url, "ok": False, "status_code": getattr(e, "code", None), "error": str(e)})
                except Exception as e:
                    attempts.append({"url": url, "ok": False, "error": str(e)})
            return {
                "status": "error",
                "ok": False,
                "plugin_id": plugin_id,
                "healthcheck_type": hc_type,
                "checked_at": checked_at,
                "summary": "HTTP probe failed for all configured URLs" if urls else "No URLs configured",
                "attempts": attempts,
            }
        if hc_type == "http_json_signature":
            urls = [str(x).strip() for x in (hc.get("urls") or []) if str(x).strip()]
            require_any_keys = [str(x).strip() for x in (hc.get("require_any_keys") or []) if str(x).strip()]
            require_all_keys = [str(x).strip() for x in (hc.get("require_all_keys") or []) if str(x).strip()]
            require_substrings = [str(x).strip().lower() for x in (hc.get("require_substrings") or []) if str(x).strip()]
            regex_any = [str(x).strip() for x in (hc.get("require_regex_any") or []) if str(x).strip()]
            regex_all = [str(x).strip() for x in (hc.get("require_regex_all") or []) if str(x).strip()]
            attempts = []
            for url in urls[:20]:
                try:
                    req = urllib.request.Request(url, headers={"Accept": "application/json"})
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        raw = resp.read(8192).decode("utf-8", errors="replace")
                        body = json.loads(raw) if raw.strip() else {}
                        keys = list(body.keys()) if isinstance(body, dict) else []
                        raw_low = raw.lower()
                        any_ok = (not require_any_keys) or any(k in keys for k in require_any_keys)
                        all_ok = (not require_all_keys) or all(k in keys for k in require_all_keys)
                        subs_ok = (not require_substrings) or all(s in raw_low for s in require_substrings)
                        regex_any_ok = (not regex_any) or any(re.search(pat, raw, flags=re.IGNORECASE) for pat in regex_any)
                        regex_all_ok = (not regex_all) or all(re.search(pat, raw, flags=re.IGNORECASE) for pat in regex_all)
                        row = {
                            "url": url,
                            "ok": bool(any_ok and all_ok and subs_ok and regex_any_ok and regex_all_ok),
                            "status_code": int(getattr(resp, "status", 200)),
                            "keys": keys[:40],
                            "preview": raw[:300],
                            "matched_any_keys": any_ok,
                            "matched_all_keys": all_ok,
                            "matched_substrings": subs_ok,
                            "matched_regex_any": regex_any_ok,
                            "matched_regex_all": regex_all_ok,
                        }
                        attempts.append(row)
                        if row["ok"]:
                            return {
                                "status": "ok",
                                "ok": True,
                                "plugin_id": plugin_id,
                                "healthcheck_type": hc_type,
                                "checked_at": checked_at,
                                "summary": f"HTTP JSON signature OK: {url}",
                                "attempts": attempts,
                            }
                except urllib.error.HTTPError as e:
                    attempts.append({"url": url, "ok": False, "status_code": getattr(e, "code", None), "error": str(e)})
                except Exception as e:
                    attempts.append({"url": url, "ok": False, "error": str(e)})
            return {
                "status": "error",
                "ok": False,
                "plugin_id": plugin_id,
                "healthcheck_type": hc_type,
                "checked_at": checked_at,
                "summary": "No endpoint matched JSON signature requirements" if urls else "No URLs configured",
                "attempts": attempts,
            }
        if hc_type == "path_exists":
            paths = [str(x).strip() for x in (hc.get("paths") or []) if str(x).strip()]
            checks = []
            for p in paths[:30]:
                expanded = os.path.expanduser(os.path.expandvars(p))
                exists = Path(expanded).exists()
                checks.append({"path": p, "expanded_path": expanded, "exists": exists})
            ok = any(x["exists"] for x in checks)
            return {
                "status": "ok" if ok else "error",
                "ok": ok,
                "plugin_id": plugin_id,
                "healthcheck_type": hc_type,
                "checked_at": checked_at,
                "summary": f"{sum(1 for x in checks if x['exists'])}/{len(checks)} paths found" if checks else "No paths configured",
                "checks": checks,
            }
        return {
            "status": "unsupported",
            "ok": False,
            "plugin_id": plugin_id,
            "healthcheck_type": hc_type,
            "checked_at": checked_at,
            "summary": f"Unsupported healthcheck type: {hc_type}",
        }

    def _driver_config(self, manifest: Dict[str, Any], action: str) -> Dict[str, Any]:
        driver = manifest.get("driver") if isinstance(manifest.get("driver"), dict) else {}
        cfg = driver.get(action) if isinstance(driver.get(action), dict) else {}
        resolved = dict(cfg)
        os_profiles = cfg.get("os_profiles") if isinstance(cfg.get("os_profiles"), dict) else {}
        selected_profile = None
        selected_key = ""
        for key in self._driver_os_candidates():
            prof = os_profiles.get(key)
            if isinstance(prof, dict):
                selected_profile = prof
                selected_key = key
                break
        if isinstance(selected_profile, dict):
            merged = dict(resolved)
            for k, v in selected_profile.items():
                merged[k] = v
            resolved = merged
        if "os_profiles" in resolved:
            resolved.pop("os_profiles", None)
        if os_profiles:
            resolved["_resolved_os_profile"] = selected_key or "default"
            resolved["_os_profile_candidates"] = self._driver_os_candidates()
        return resolved

    def _driver_os_candidates(self) -> List[str]:
        override = _s(os.environ.get("RTH_DRIVER_OS")).lower()
        if override:
            vals = [override]
        else:
            sysname = platform.system().lower()
            vals = [sysname]
            if os.name == "nt":
                vals += ["windows", "win"]
            elif sysname == "darwin":
                vals += ["macos", "mac", "darwin", "osx"]
            elif os.name == "posix":
                vals += ["linux", "unix", "posix"]
        vals += ["default", "*", "any"]
        out: List[str] = []
        for v in vals:
            s = _s(v).lower()
            if s and s not in out:
                out.append(s)
        return out

    def _driver_capability(self, cfg: Dict[str, Any], action: str) -> Capability:
        t = _s(cfg.get("type")).lower()
        if t in {"command", "command_sequence", "install_command"}:
            return Capability.PROCESS_EXEC
        if action == "install":
            return Capability.FILESYSTEM_WRITE
        if action in {"enable", "disable"}:
            return Capability.FILESYSTEM_WRITE
        return Capability.FILESYSTEM_WRITE

    def _driver_risk(self, cfg: Dict[str, Any], action: str) -> RiskLevel:
        rn = _s(cfg.get("risk") or ("high" if action == "install" else "medium")).lower()
        return {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
        }.get(rn, RiskLevel.MEDIUM)

    def _execute_driver_action(self, manifest: Dict[str, Any], action: str, cfg: Dict[str, Any], *, timeout_sec: float) -> Dict[str, Any]:
        pid = _s(manifest.get("id"))
        t = _s(cfg.get("type")).lower()
        timeout = max(0.2, min(float(timeout_sec or 6.0), 120.0))
        if t in {"", "none"}:
            return {"status": "not_supported", "plugin_id": pid, "action": action, "detail": "driver action not configured"}
        if t == "manual":
            instructions = cfg.get("instructions") or []
            next_state = _s(cfg.get("set_install_state")).lower() or ("registered" if action == "install" else ("enabled" if action == "enable" else "disabled"))
            enabled = cfg.get("set_enabled")
            if action == "disable" and enabled is None:
                enabled = False
            if action == "enable" and enabled is None:
                enabled = True
            snapshot = self._upsert_plugin_state(pid, enabled=enabled if isinstance(enabled, bool) else None, install_state=next_state, source=f"driver_{action}_manual")
            return {
                "status": "manual",
                "plugin_id": pid,
                "action": action,
                "instructions": instructions,
                "plugin_state": snapshot,
            }
        if t in {"healthcheck_enable", "healthcheck_then_state"} and action == "enable":
            hc_result = self._run_healthcheck(manifest, timeout_sec=min(timeout, 15.0))
            self._save_healthcheck_snapshot(pid, hc_result)
            if bool(hc_result.get("ok")):
                snapshot = self._upsert_plugin_state(pid, enabled=True, install_state="enabled", source="driver_enable_healthcheck")
                return {"status": "ok", "plugin_id": pid, "action": action, "healthcheck": hc_result, "plugin_state": snapshot}
            snapshot = self._upsert_plugin_state(pid, enabled=False, install_state="broken", source="driver_enable_healthcheck_fail")
            return {"status": "error", "plugin_id": pid, "action": action, "healthcheck": hc_result, "plugin_state": snapshot}
        if t == "state_only":
            target_state = _s(cfg.get("install_state")).lower() or ("disabled" if action == "disable" else ("enabled" if action == "enable" else "registered"))
            target_enabled = cfg.get("enabled")
            if not isinstance(target_enabled, bool):
                if action == "disable":
                    target_enabled = False
                elif action == "enable":
                    target_enabled = True
                else:
                    target_enabled = None
            snapshot = self._upsert_plugin_state(pid, enabled=target_enabled if isinstance(target_enabled, bool) else None, install_state=target_state, source=f"driver_{action}_state")
            return {"status": "ok", "plugin_id": pid, "action": action, "plugin_state": snapshot}
        if t in {"command", "command_sequence", "install_command"}:
            commands = cfg.get("commands") or []
            if isinstance(commands, str):
                commands = [commands]
            if not isinstance(commands, list) or not commands:
                return {"status": "invalid_driver", "plugin_id": pid, "action": action, "detail": "commands required"}
            runs = []
            for raw in commands[:10]:
                cmd = [str(x) for x in raw] if isinstance(raw, list) else [str(raw)]
                runs.append(self._run_subprocess(cmd, timeout=timeout))
                if not bool(runs[-1].get("ok")):
                    break
            all_ok = bool(runs) and all(bool(r.get("ok")) for r in runs)
            next_state = _s(cfg.get("set_install_state")).lower() or ("registered" if action == "install" else ("enabled" if action == "enable" else "disabled"))
            next_enabled = cfg.get("set_enabled")
            if not isinstance(next_enabled, bool):
                if action == "enable":
                    next_enabled = all_ok
                elif action == "disable":
                    next_enabled = False if all_ok else None
                else:
                    next_enabled = None
            if action in {"install", "enable", "disable"} and (all_ok or action == "disable"):
                snapshot = self._upsert_plugin_state(pid, enabled=next_enabled if isinstance(next_enabled, bool) else None, install_state=(next_state if all_ok or action == "disable" else "broken"), source=f"driver_{action}_command")
            else:
                snapshot = self._upsert_plugin_state(pid, enabled=False, install_state="broken", source=f"driver_{action}_command_fail")
            return {
                "status": "ok" if all_ok else "error",
                "plugin_id": pid,
                "action": action,
                "runs": runs,
                "plugin_state": snapshot,
            }
        return {"status": "unsupported_driver", "plugin_id": pid, "action": action, "driver_type": t}

    def _run_subprocess(self, cmd: List[str], *, timeout: float = 5.0) -> Dict[str, Any]:
        if not cmd:
            return {"ok": False, "error": "empty command", "cmd": []}
        exec_cmd = list(cmd)
        if len(exec_cmd) == 1 and shutil.which(exec_cmd[0]):
            exec_cmd[0] = shutil.which(exec_cmd[0]) or exec_cmd[0]
        elif exec_cmd and not os.path.isabs(exec_cmd[0]):
            resolved = shutil.which(exec_cmd[0])
            if resolved:
                exec_cmd[0] = resolved
        try:
            proc = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                timeout=max(0.2, min(float(timeout), 120.0)),
                shell=False,
            )
            return {
                "ok": proc.returncode == 0,
                "cmd": exec_cmd,
                "returncode": proc.returncode,
                "stdout": (proc.stdout or "")[:2000],
                "stderr": (proc.stderr or "")[:2000],
            }
        except FileNotFoundError as e:
            return {"ok": False, "cmd": exec_cmd, "error": str(e)}
        except subprocess.TimeoutExpired as e:
            return {
                "ok": False,
                "cmd": exec_cmd,
                "timeout": True,
                "stdout": str((e.stdout or "")[:2000]) if isinstance(e.stdout, str) else "",
                "stderr": str((e.stderr or "")[:2000]) if isinstance(e.stderr, str) else "",
                "error": "timeout",
            }
        except Exception as e:
            return {"ok": False, "cmd": exec_cmd, "error": str(e)}

    def _find_index(self, plugin_id: str) -> int:
        pid = _s(plugin_id)
        for i, row in enumerate(self._state.get("items", [])):
            if not isinstance(row, dict):
                continue
            m = row.get("manifest") if isinstance(row.get("manifest"), dict) else {}
            if _s(m.get("id")) == pid:
                return i
        return -1

    def _upsert_item(self, manifest: Dict[str, Any]) -> None:
        idx = self._find_index(manifest["id"])
        row = {
            "manifest": manifest,
            "install_state": "registered",
            "registered_at": _now(),
            "updated_at": _now(),
        }
        if idx >= 0:
            prev = self._state["items"][idx]
            if isinstance(prev, dict):
                row["registered_at"] = prev.get("registered_at") or row["registered_at"]
            self._state["items"][idx] = row
        else:
            self._state["items"].append(row)
        self._state["updated_at"] = _now()
        self._save_state()

    def _normalize_manifest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        m = json.loads(json.dumps(payload))  # deep copy JSON-safe
        m["manifest_version"] = "rth.plugin.v0"
        m["id"] = _s(m.get("id")).lower()
        m["name"] = _s(m.get("name"))
        m["version"] = _s(m.get("version"))
        m["vendor"] = _s(m.get("vendor"))
        m["category"] = _s(m.get("category")).lower()
        m["surface"] = _s(m.get("surface")).lower()
        m["compatibility_tier"] = _s(m.get("compatibility_tier")).lower()
        m["capabilities_requested"] = [str(x).strip() for x in (m.get("capabilities_requested") or []) if str(x).strip()]
        m["capabilities_requested"] = [x for x in _uniq(m["capabilities_requested"]) if x in VALID_CAP]
        m["risk_class"] = _s(m.get("risk_class")).lower()
        cd = m.get("consent_defaults") if isinstance(m.get("consent_defaults"), dict) else {}
        m["consent_defaults"] = {
            "proposal_required": bool(cd.get("proposal_required", True)),
            "dry_run_supported": bool(cd.get("dry_run_supported", False)),
            "owner_approval_required": bool(cd.get("owner_approval_required", True)),
            "suggested_guardian_severity_min": _s(cd.get("suggested_guardian_severity_min") or "balanced").lower()
            if _s(cd.get("suggested_guardian_severity_min") or "balanced").lower() in VALID_SEVERITY else "balanced",
        }
        m["supported_apps"] = [a for a in (m.get("supported_apps") or []) if isinstance(a, dict)]
        m["actions"] = [a for a in (m.get("actions") or []) if isinstance(a, dict)]
        return m

    def _manifest_summary(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        m = payload if isinstance(payload, dict) else {}
        return {
            "id": m.get("id"),
            "name": m.get("name"),
            "vendor": m.get("vendor"),
            "category": m.get("category"),
            "surface": m.get("surface"),
            "compatibility_tier": m.get("compatibility_tier"),
            "risk_class": m.get("risk_class"),
            "capabilities_requested": m.get("capabilities_requested") or [],
            "supported_apps_count": len([a for a in (m.get("supported_apps") or []) if isinstance(a, dict)]),
            "actions_count": len([a for a in (m.get("actions") or []) if isinstance(a, dict)]),
        }

    def _validate_manifest_payload(self, payload: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        errors: List[str] = []
        warnings: List[str] = []
        if not isinstance(payload, dict):
            return False, ["payload must be object"], []
        req = [
            "manifest_version", "id", "name", "version", "vendor", "category", "surface",
            "compatibility_tier", "capabilities_requested", "risk_class", "consent_defaults",
            "supported_apps", "actions",
        ]
        for k in req:
            if k not in payload:
                errors.append(f"missing field: {k}")
        if payload.get("manifest_version") != "rth.plugin.v0":
            errors.append("manifest_version must be 'rth.plugin.v0'")
        pid = _s(payload.get("id"))
        if not pid:
            errors.append("id required")
        if _s(payload.get("category")).lower() not in VALID_CATEGORY:
            errors.append("invalid category")
        if _s(payload.get("surface")).lower() not in VALID_SURFACE:
            errors.append("invalid surface")
        if _s(payload.get("compatibility_tier")).lower() not in VALID_TIER:
            errors.append("invalid compatibility_tier")
        if _s(payload.get("risk_class")).lower() not in VALID_RISK:
            errors.append("invalid risk_class")
        caps = payload.get("capabilities_requested")
        if not isinstance(caps, list) or not caps:
            errors.append("capabilities_requested must be non-empty array")
        else:
            bad = [str(x) for x in caps if str(x) not in VALID_CAP]
            if bad:
                errors.append(f"invalid capabilities_requested: {bad}")
        cd = payload.get("consent_defaults")
        if not isinstance(cd, dict):
            errors.append("consent_defaults must be object")
        else:
            if "proposal_required" not in cd:
                errors.append("consent_defaults.proposal_required required")
            sev = _s(cd.get("suggested_guardian_severity_min")).lower()
            if sev and sev not in VALID_SEVERITY:
                errors.append("consent_defaults.suggested_guardian_severity_min invalid")
        apps = payload.get("supported_apps")
        if not isinstance(apps, list) or not apps:
            errors.append("supported_apps must be non-empty array")
        else:
            for i, a in enumerate(apps[:50]):
                if not isinstance(a, dict):
                    errors.append(f"supported_apps[{i}] must be object")
                    continue
                if not _s(a.get("name")):
                    errors.append(f"supported_apps[{i}].name required")
        actions = payload.get("actions")
        if not isinstance(actions, list) or not actions:
            errors.append("actions must be non-empty array")
        else:
            ids = set()
            for i, a in enumerate(actions[:200]):
                if not isinstance(a, dict):
                    errors.append(f"actions[{i}] must be object")
                    continue
                aid = _s(a.get("id"))
                if not aid:
                    errors.append(f"actions[{i}].id required")
                elif aid in ids:
                    errors.append(f"actions[{i}].id duplicate: {aid}")
                ids.add(aid)
                if _s(a.get("capability")) not in VALID_CAP:
                    errors.append(f"actions[{i}].capability invalid")
                if _s(a.get("risk")).lower() not in VALID_RISK:
                    errors.append(f"actions[{i}].risk invalid")
        if _s(payload.get("compatibility_tier")) == "fallback_browser" and _s(payload.get("surface")) != "browser":
            warnings.append("fallback_browser tier typically uses surface='browser'")
        if "process_exec" in [str(x) for x in (payload.get("capabilities_requested") or [])] and _s(payload.get("risk_class")).lower() in {"low"}:
            warnings.append("process_exec plugin marked low risk; review risk_class")
        return (len(errors) == 0, errors, warnings)

    def _ensure_change_control_marker(self, reason: str) -> str:
        text = _s(reason) or "Register plugin manifest"
        if any(t in text.lower() for t in ("audit", "safe", "dry-run", "rollback")):
            return text
        return f"{text} [audit]"

    def _builtin_catalog(self) -> List[Dict[str, Any]]:
        # Prioritized connectors requested by user + foundational public pack examples.
        rows: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
        rows.append((
            _manifest_base(
                plugin_id="anthropic.claude_code",
                name="Claude Code Adapter",
                vendor="Anthropic",
                category="development",
                surface="cli",
                tier="verified",
                apps=[{"name": "Claude Code", "platforms": ["windows", "linux", "macos"]}],
                capabilities=["filesystem_read", "process_exec", "filesystem_write"],
                notes="Target priority pack (CLI/workflow integration).",
                healthcheck={
                    "type": "composite",
                    "mode": "any",
                    "checks": [
                        {
                            "type": "command_version",
                            "commands": ["claude", "claude-code"],
                            "args": ["--version"],
                            "match_all": ["claude"],
                            "vendor_regex": r"(?i)\b(claude(?:\s+code)?)\b",
                            "version_regex": r"(?i)\b(?:claude(?:\s+code)?(?:\s+version)?[:\s-]*)?(\d+\.\d+(?:\.\d+)*)\b",
                            "require_regex_all": [
                                r"(?i)\bclaude\b",
                                r"\d+\.\d+(?:\.\d+)*",
                            ],
                        },
                        {"type": "command_exists", "commands": ["claude", "claude-code"]},
                        {
                            "type": "path_exists",
                            "paths": [
                                r"%APPDATA%\npm\claude.cmd",
                                r"%APPDATA%\npm\claude-code.cmd",
                                r"%USERPROFILE%\.npm-global\bin\claude",
                            ],
                        },
                    ],
                },
                driver={
                    "install": {
                        "type": "command_sequence",
                        "risk": "high",
                        "set_install_state": "registered",
                        "commands": [
                            ["npm", "install", "-g", "@anthropic-ai/claude-code"],
                            ["claude", "--version"],
                        ],
                        "notes": "Comando ufficiale Anthropic CLI via npm (richiede rete + npm).",
                    },
                    "enable": {"type": "healthcheck_then_state", "risk": "medium"},
                    "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                },
            ),
            {"priority": "P0", "pack": "claude_ecosystem"},
        ))
        rows.append((
            _manifest_base(
                plugin_id="anthropic.claude_cowork",
                name="Claude Cowork Surface Adapter",
                vendor="Anthropic",
                category="communication",
                surface="hybrid",
                tier="community",
                apps=[{"name": "Claude cowork", "platforms": ["web"], "notes": "surface/API to be normalized"}],
                capabilities=["filesystem_read", "network_access", "browser"],
                risk="high",
                notes="Surface placeholder pending exact API/product normalization.",
                healthcheck={"type": "none"},
            ),
            {"priority": "P0", "pack": "claude_ecosystem", "status": "surface_unverified"},
        ))
        rows.append((
            _manifest_base(
                plugin_id="anthropic.claude_mem",
                name="Claude Mem Surface Adapter",
                vendor="Anthropic",
                category="knowledge",
                surface="hybrid",
                tier="community",
                apps=[{"name": "Claude mem", "platforms": ["web"], "notes": "surface/API to be normalized"}],
                capabilities=["filesystem_read", "network_access"],
                risk="medium",
                notes="Surface placeholder pending exact API/product normalization.",
                healthcheck={"type": "none"},
            ),
            {"priority": "P0", "pack": "claude_ecosystem", "status": "surface_unverified"},
        ))
        for pid, name in [
            ("ai_ide.cursor", "Cursor IDE Adapter"),
            ("ai_ide.windsurf", "Windsurf IDE Adapter"),
            ("ai_ide.trae", "Trae IDE Adapter"),
            ("ai_ide.lovable", "Lovable Builder Adapter"),
            ("ai_ide.antigravity", "Antigravity IDE Adapter"),
        ]:
            surface = "hybrid" if any(x in pid for x in ("lovable", "antigravity")) else "cli"
            tier = "fallback_browser" if "lovable" in pid else ("community" if "antigravity" in pid else "verified")
            ide_slug = pid.split(".")[-1]
            ide_path_candidates = {
                "cursor": [r"%LOCALAPPDATA%\Programs\Cursor\Cursor.exe", r"%LOCALAPPDATA%\cursor\Cursor.exe"],
                "windsurf": [r"%LOCALAPPDATA%\Programs\Windsurf\Windsurf.exe", r"%LOCALAPPDATA%\Programs\Codeium\Windsurf.exe"],
                "trae": [r"%LOCALAPPDATA%\Programs\Trae\Trae.exe"],
                "antigravity": [r"%LOCALAPPDATA%\Programs\Antigravity\Antigravity.exe"],
                "lovable": [],
            }
            ide_install_driver = {
                "type": "manual",
                "risk": "high",
                "set_install_state": "registered",
                "instructions": [
                    f"Installare {name.replace(' Adapter','')} dal canale ufficiale del vendor.",
                    f"Poi eseguire `rth plugins driver enable {pid}` per verifica versione/firma e attivazione adapter.",
                ],
                "os_profiles": {
                    "macos": {
                        "type": "manual",
                        "instructions": [
                            f"Installare {name.replace(' Adapter','')} su macOS dal canale ufficiale del vendor.",
                            f"Poi eseguire `rth plugins driver enable {pid}` per verifica versione/firma e attivazione adapter.",
                        ],
                    },
                    "linux": {
                        "type": "manual",
                        "instructions": [
                            f"Installare {name.replace(' Adapter','')} su Linux dal canale ufficiale del vendor oppure package manager supportato.",
                            f"Poi eseguire `rth plugins driver enable {pid}` per verifica versione/firma e attivazione adapter.",
                        ],
                    },
                },
            }
            if ide_slug == "cursor":
                ide_install_driver = {
                    "type": "manual",
                    "risk": "high",
                    "set_install_state": "registered",
                    "notes": "Profili install OS-specific: Windows automatico via winget; macOS/Linux manual-guided finché non vengono fissati comandi vendor ufficiali.",
                    "instructions": [
                        "Profilo Windows disponibile con install automatico via winget.",
                        "Per macOS/Linux al momento resta manual-guided (comandi vendor da confermare).",
                    ],
                    "os_profiles": {
                        "windows": {
                            "type": "command_sequence",
                            "commands": [
                                ["winget", "install", "--id", "Cursor.Cursor", "-e", "--accept-package-agreements", "--accept-source-agreements"],
                                ["cursor", "--version"],
                            ],
                            "notes": "Install automatico Windows via winget package `Cursor.Cursor`.",
                        },
                        "win": {
                            "type": "command_sequence",
                            "commands": [
                                ["winget", "install", "--id", "Cursor.Cursor", "-e", "--accept-package-agreements", "--accept-source-agreements"],
                                ["cursor", "--version"],
                            ],
                            "notes": "Install automatico Windows via winget package `Cursor.Cursor`.",
                        },
                        "macos": {
                            "type": "manual",
                            "instructions": [
                                "Installare Cursor su macOS dal canale ufficiale (download/sign-in vendor).",
                                "Poi eseguire `rth plugins driver enable ai_ide.cursor` per verifica versione/firma.",
                            ],
                        },
                        "linux": {
                            "type": "manual",
                            "instructions": [
                                "Installare Cursor su Linux dal canale ufficiale/package supportato dal vendor.",
                                "Poi eseguire `rth plugins driver enable ai_ide.cursor` per verifica versione/firma.",
                            ],
                        },
                    },
                }
            elif ide_slug == "windsurf":
                ide_install_driver = {
                    "type": "manual",
                    "risk": "high",
                    "set_install_state": "registered",
                    "notes": "Profili install OS-specific: Windows automatico via winget; macOS/Linux manual-guided finché non vengono fissati comandi vendor ufficiali.",
                    "instructions": [
                        "Profilo Windows disponibile con install automatico via winget.",
                        "Per macOS/Linux al momento resta manual-guided (comandi vendor da confermare).",
                    ],
                    "os_profiles": {
                        "windows": {
                            "type": "command_sequence",
                            "commands": [
                                ["winget", "install", "--id", "Codeium.Windsurf", "-e", "--accept-package-agreements", "--accept-source-agreements"],
                                ["windsurf", "--version"],
                            ],
                            "notes": "Install automatico Windows via winget package `Codeium.Windsurf`.",
                        },
                        "win": {
                            "type": "command_sequence",
                            "commands": [
                                ["winget", "install", "--id", "Codeium.Windsurf", "-e", "--accept-package-agreements", "--accept-source-agreements"],
                                ["windsurf", "--version"],
                            ],
                            "notes": "Install automatico Windows via winget package `Codeium.Windsurf`.",
                        },
                        "macos": {
                            "type": "manual",
                            "instructions": [
                                "Installare Windsurf su macOS dal canale ufficiale Codeium/Windsurf.",
                                "Poi eseguire `rth plugins driver enable ai_ide.windsurf` per verifica versione/firma.",
                            ],
                        },
                        "linux": {
                            "type": "manual",
                            "instructions": [
                                "Installare Windsurf su Linux dal canale ufficiale Codeium/Windsurf o package supportato.",
                                "Poi eseguire `rth plugins driver enable ai_ide.windsurf` per verifica versione/firma.",
                            ],
                        },
                    },
                }
            rows.append((
                _manifest_base(
                    plugin_id=pid,
                    name=name,
                    vendor="AI IDE",
                    category="development",
                    surface=surface if tier != "fallback_browser" else "browser",
                    tier=tier,
                    apps=[{"name": name.replace(" Adapter", ""), "platforms": ["windows", "macos", "web"]}],
                    capabilities=["filesystem_read", "filesystem_write", "process_exec"],
                    risk="high",
                    notes="Priority AI IDE connector target requested for public release.",
                    healthcheck={
                        "type": "composite",
                        "mode": "any",
                        "checks": [
                            {
                                "type": "command_version",
                                "commands": [
                                    ide_slug,
                                    name.lower().replace(" adapter", "").replace(" ", ""),
                                ],
                                "args": ["--version"],
                                "match_any": [ide_slug],
                                "vendor_regex": (
                                    r"(?i)\b(cursor)\b"
                                    if ide_slug == "cursor"
                                    else (r"(?i)\b(windsurf|codeium)\b" if ide_slug == "windsurf" else rf"(?i)\b({re.escape(ide_slug)})\b")
                                ),
                                "version_regex": r"(?i)\b(\d+\.\d+(?:\.\d+)*)\b",
                                "require_regex_all": [r"\d+\.\d+(?:\.\d+)*"],
                            },
                            {
                                "type": "command_exists",
                                "commands": [
                                    ide_slug,
                                    name.lower().replace(" adapter", "").replace(" ", ""),
                                ],
                            },
                            {"type": "path_exists", "paths": ide_path_candidates.get(ide_slug, [])},
                        ],
                    },
                    driver={
                        "install": ide_install_driver,
                        "enable": {"type": "healthcheck_then_state", "risk": "medium"},
                        "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                    },
                ),
                {"priority": "P0", "pack": "ai_ide"},
            ))
        rows.append((
            _manifest_base(
                plugin_id="llm_runtime.llama_cpp",
                name="llama.cpp Runtime Provider Adapter",
                vendor="llama.cpp",
                category="ai_runtime",
                surface="rest",
                tier="verified",
                apps=[{"name": "llama.cpp server", "platforms": ["windows", "linux", "macos"]}],
                capabilities=["network_access"],
                risk="medium",
                notes="OpenAI-compatible local runtime (`llama_cpp`) for multi-LLM control plane.",
                healthcheck={
                    "type": "composite",
                    "mode": "any",
                    "checks": [
                        {
                            "type": "http_json_signature",
                            "urls": [
                                "http://127.0.0.1:8080/v1/models",
                                "http://127.0.0.1:8080/models",
                            ],
                            "require_all_keys": ["data"],
                        },
                        {
                            "type": "command_version",
                            "commands": ["llama-server"],
                            "args": ["--version"],
                            "match_any": ["llama"],
                            "vendor_regex": r"(?i)\b(llama(?:\\.cpp)?|ggml)\b",
                            "version_regex": r"(?i)\b(?:version[:\\s-]*)?(\\d+\\.\\d+(?:\\.\\d+)*)\\b",
                            "require_regex_any": [r"(?i)\\bllama(?:\\.cpp)?\\b", r"(?i)\\bggml\\b"],
                        },
                        {
                            "type": "command_version",
                            "commands": ["python"],
                            "args": ["-c", "import llama_cpp; print('llama-cpp-python', getattr(llama_cpp, '__version__', '0.0.0'))"],
                            "match_any": ["llama-cpp-python", "llama_cpp"],
                            "vendor_regex": r"(?i)\b(llama[-_. ]?cpp(?:-python)?)\b",
                            "version_regex": r"(?i)\b(\d+\.\d+(?:\.\d+)*)\b",
                            "require_regex_any": [r"(?i)llama[-_. ]?cpp"],
                        },
                        {"type": "command_exists", "commands": ["llama-server"]},
                    ],
                },
                driver={
                    "install": {
                        "type": "command_sequence",
                        "risk": "high",
                        "set_install_state": "registered",
                        "commands": [
                            ["python", "-m", "pip", "install", "-U", "llama-cpp-python[server]"],
                        ],
                        "notes": "Installer automatico runtime OpenAI-compatible via llama-cpp-python server (alternativa pratica al binario `llama-server`).",
                        "instructions": [
                            "Installare `llama-server` (llama.cpp) oppure avviare un runtime OpenAI-compatible su porta configurata.",
                            "Alternativa: usare `llama-cpp-python` in modalità server.",
                            "Poi eseguire `rth plugins driver enable llm_runtime.llama_cpp` per verifica endpoint/versione.",
                        ],
                    },
                    "enable": {"type": "healthcheck_then_state", "risk": "medium"},
                    "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                },
            ),
            {"priority": "P0", "pack": "llm_runtime"},
        ))
        rows.append((
            _manifest_base(
                plugin_id="llm_provider.groq_cloud",
                name="Groq Cloud Provider Adapter",
                vendor="Groq",
                category="ai_runtime",
                surface="rest",
                tier="verified",
                apps=[{"name": "Groq API", "platforms": ["cloud", "web"]}],
                capabilities=["network_access"],
                risk="medium",
                notes="Costo basso/latenza alta performance per routing multi-LLM (reasoning/tool-use/vision/STT/TTS via catalogo Groq).",
                healthcheck={"type": "none"},
                driver={
                    "install": {
                        "type": "manual",
                        "risk": "medium",
                        "set_install_state": "registered",
                        "instructions": [
                            "Inserire API key Groq nella UI Providers (tipo `groq`) o via endpoint `/api/v1/models/providers/upsert`.",
                            "Configurare i modelli Groq desiderati e routing policy cost-aware.",
                        ],
                    },
                    "enable": {"type": "state_only", "risk": "low", "install_state": "enabled", "enabled": True},
                    "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                },
            ),
            {"priority": "P0", "pack": "llm_provider"},
        ))
        rows.extend([
            (
                _manifest_base(
                    plugin_id="workflow.n8n",
                    name="n8n Workflow Automation Adapter",
                    vendor="n8n",
                    category="automation",
                    surface="hybrid",
                    tier="verified",
                    apps=[{"name": "n8n", "platforms": ["windows", "linux", "macos", "cloud", "web"]}],
                    capabilities=["network_access", "process_exec", "filesystem_read", "data_export"],
                    risk="high",
                    notes="Workflow builder/orchestrator target (self-host or cloud) with CLI+HTTP healthchecks.",
                    healthcheck={
                        "type": "composite",
                        "mode": "any",
                        "checks": [
                            {
                                "type": "command_version",
                                "commands": ["n8n"],
                                "args": ["--version"],
                                "match_any": ["n8n"],
                                "vendor_regex": r"(?i)\bn8n\b",
                                "version_regex": r"(?i)\b(\d+\.\d+(?:\.\d+)*)\b",
                                "require_regex_all": [r"(?i)\bn8n\b", r"\d+\.\d+(?:\.\d+)*"],
                            },
                            {
                                "type": "command_exists",
                                "commands": ["n8n"],
                            },
                            {
                                "type": "path_exists",
                                "paths": [
                                    r"%APPDATA%\npm\n8n.cmd",
                                    r"%USERPROFILE%\.npm-global\bin\n8n",
                                ],
                            },
                            {
                                "type": "http_json_signature",
                                "urls": [
                                    "http://127.0.0.1:5678/healthz",
                                ],
                                "require_any_keys": ["status"],
                            },
                            {
                                "type": "http_get",
                                "urls": ["http://127.0.0.1:5678/"],
                            },
                        ],
                    },
                    driver={
                        "install": {
                            "type": "manual",
                            "risk": "high",
                            "set_install_state": "registered",
                            "notes": "Profili OS-specifici: install automatico via npm su Windows/macOS/Linux (richiede Node.js + permessi npm global).",
                            "instructions": [
                                "Il driver usera' il profilo OS-specifico (Windows/macOS/Linux) per installare n8n via npm.",
                                "Se npm global richiede permessi elevati o custom prefix, configurare npm e rilanciare il driver.",
                            ],
                            "os_profiles": {
                                "windows": {
                                    "type": "command_sequence",
                                    "commands": [
                                        ["npm", "install", "-g", "n8n"],
                                        ["n8n", "--version"],
                                    ],
                                    "notes": "Windows: install automatico n8n via npm globale.",
                                },
                                "win": {
                                    "type": "command_sequence",
                                    "commands": [
                                        ["npm", "install", "-g", "n8n"],
                                        ["n8n", "--version"],
                                    ],
                                    "notes": "Windows: install automatico n8n via npm globale.",
                                },
                                "macos": {
                                    "type": "command_sequence",
                                    "commands": [
                                        ["npm", "install", "-g", "n8n"],
                                        ["n8n", "--version"],
                                    ],
                                    "notes": "macOS: install automatico n8n via npm globale (potrebbero servire permessi/prefix npm).",
                                },
                                "darwin": {
                                    "type": "command_sequence",
                                    "commands": [
                                        ["npm", "install", "-g", "n8n"],
                                        ["n8n", "--version"],
                                    ],
                                    "notes": "macOS: install automatico n8n via npm globale (potrebbero servire permessi/prefix npm).",
                                },
                                "linux": {
                                    "type": "command_sequence",
                                    "commands": [
                                        ["npm", "install", "-g", "n8n"],
                                        ["n8n", "--version"],
                                    ],
                                    "notes": "Linux: install automatico n8n via npm globale (potrebbero servire permessi/prefix npm).",
                                },
                            },
                        },
                        "enable": {"type": "healthcheck_then_state", "risk": "medium"},
                        "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                    },
                ),
                {"priority": "P0", "pack": "workflow_automation"},
            ),
            (
                _manifest_base(
                    plugin_id="workflow.node_red",
                    name="Node-RED Workflow Adapter",
                    vendor="OpenJS Foundation",
                    category="automation",
                    surface="hybrid",
                    tier="community",
                    apps=[{"name": "Node-RED", "platforms": ["windows", "linux", "macos", "web"]}],
                    capabilities=["network_access", "process_exec", "filesystem_read"],
                    risk="high",
                    notes="Low-code local workflow editor/runtime (Node-RED) for automation integrations.",
                    healthcheck={
                        "type": "composite",
                        "mode": "any",
                        "checks": [
                            {
                                "type": "command_version",
                                "commands": ["node-red"],
                                "args": ["--version"],
                                "match_any": ["node-red"],
                                "vendor_regex": r"(?i)\bnode-?red\b",
                                "version_regex": r"(?i)\b(\d+\.\d+(?:\.\d+)*)\b",
                                "require_regex_all": [r"(?i)\bnode-?red\b", r"\d+\.\d+(?:\.\d+)*"],
                            },
                            {
                                "type": "command_exists",
                                "commands": ["node-red"],
                            },
                            {
                                "type": "path_exists",
                                "paths": [
                                    r"%APPDATA%\npm\node-red.cmd",
                                    r"%USERPROFILE%\.npm-global\bin\node-red",
                                ],
                            },
                            {"type": "http_get", "urls": ["http://127.0.0.1:1880/"]},
                        ],
                    },
                    driver={
                        "install": {
                            "type": "manual",
                            "risk": "high",
                            "set_install_state": "registered",
                            "notes": "Profili OS-specifici: install automatico via npm su Windows/macOS/Linux (richiede Node.js + permessi npm global).",
                            "instructions": [
                                "Il driver usera' il profilo OS-specifico (Windows/macOS/Linux) per installare Node-RED via npm.",
                                "Se npm global richiede permessi elevati o custom prefix, configurare npm e rilanciare il driver.",
                            ],
                            "os_profiles": {
                                "windows": {
                                    "type": "command_sequence",
                                    "commands": [
                                        ["npm", "install", "-g", "node-red"],
                                        ["node-red", "--version"],
                                    ],
                                    "notes": "Windows: install automatico Node-RED via npm globale.",
                                },
                                "win": {
                                    "type": "command_sequence",
                                    "commands": [
                                        ["npm", "install", "-g", "node-red"],
                                        ["node-red", "--version"],
                                    ],
                                    "notes": "Windows: install automatico Node-RED via npm globale.",
                                },
                                "macos": {
                                    "type": "command_sequence",
                                    "commands": [
                                        ["npm", "install", "-g", "node-red"],
                                        ["node-red", "--version"],
                                    ],
                                    "notes": "macOS: install automatico Node-RED via npm globale (potrebbero servire permessi/prefix npm).",
                                },
                                "darwin": {
                                    "type": "command_sequence",
                                    "commands": [
                                        ["npm", "install", "-g", "node-red"],
                                        ["node-red", "--version"],
                                    ],
                                    "notes": "macOS: install automatico Node-RED via npm globale (potrebbero servire permessi/prefix npm).",
                                },
                                "linux": {
                                    "type": "command_sequence",
                                    "commands": [
                                        ["npm", "install", "-g", "node-red"],
                                        ["node-red", "--version"],
                                    ],
                                    "notes": "Linux: install automatico Node-RED via npm globale (potrebbero servire permessi/prefix npm).",
                                },
                            },
                        },
                        "enable": {"type": "healthcheck_then_state", "risk": "medium"},
                        "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                    },
                ),
                {"priority": "P1", "pack": "workflow_automation"},
            ),
            (
                _manifest_base(
                    plugin_id="workflow.zapier",
                    name="Zapier Automation Adapter",
                    vendor="Zapier",
                    category="automation",
                    surface="browser",
                    tier="fallback_browser",
                    apps=[{"name": "Zapier", "platforms": ["cloud", "web"]}],
                    capabilities=["network_access", "system_modify"],
                    risk="high",
                    notes="Cloud workflow automation platform; initial integration via browser/API surfaces.",
                    healthcheck={"type": "none"},
                    driver={
                        "install": {
                            "type": "manual",
                            "risk": "medium",
                            "set_install_state": "registered",
                            "instructions": [
                                "Creare account Zapier e generare credenziali/API dove disponibili.",
                                "Usare browser automation/API adapter Core Rth per task approvati.",
                            ],
                        },
                        "enable": {"type": "state_only", "risk": "low", "install_state": "enabled", "enabled": True},
                        "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                    },
                ),
                {"priority": "P1", "pack": "workflow_automation", "status": "surface_unverified"},
            ),
            (
                _manifest_base(
                    plugin_id="workflow.make_com",
                    name="Make.com Automation Adapter",
                    vendor="Make",
                    category="automation",
                    surface="browser",
                    tier="fallback_browser",
                    apps=[{"name": "Make", "platforms": ["cloud", "web"]}],
                    capabilities=["network_access", "system_modify"],
                    risk="high",
                    notes="Make.com workflow builder (ex Integromat); browser/API connector target.",
                    healthcheck={"type": "none"},
                    driver={
                        "install": {
                            "type": "manual",
                            "risk": "medium",
                            "set_install_state": "registered",
                            "instructions": [
                                "Configurare account Make.com e token/API secondo piano disponibile.",
                                "Attivare adapter browser/API in Core Rth e definire no-go Guardian per scenari critici.",
                            ],
                        },
                        "enable": {"type": "state_only", "risk": "low", "install_state": "enabled", "enabled": True},
                        "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                    },
                ),
                {"priority": "P1", "pack": "workflow_automation", "status": "surface_unverified"},
            ),
            (
                _manifest_base(
                    plugin_id="workflow.pipedream",
                    name="Pipedream Workflow Adapter",
                    vendor="Pipedream",
                    category="automation",
                    surface="hybrid",
                    tier="community",
                    apps=[{"name": "Pipedream", "platforms": ["cloud", "web", "linux", "macos", "windows"]}],
                    capabilities=["network_access", "data_export", "process_exec"],
                    risk="high",
                    notes="Event-driven workflow platform; API/CLI surfaces to be normalized per account/workspace.",
                    healthcheck={"type": "none"},
                    driver={
                        "install": {
                            "type": "manual",
                            "risk": "medium",
                            "set_install_state": "registered",
                            "instructions": [
                                "Configurare account Pipedream e token/API/CLI ufficiali del workspace.",
                                "Poi attivare adapter con `rth plugins driver enable workflow.pipedream` dopo healthcheck custom.",
                            ],
                        },
                        "enable": {"type": "state_only", "risk": "low", "install_state": "enabled", "enabled": True},
                        "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                    },
                ),
                {"priority": "P1", "pack": "workflow_automation", "status": "surface_unverified"},
            ),
            (
                _manifest_base(
                    plugin_id="workflow.power_automate",
                    name="Microsoft Power Automate Adapter",
                    vendor="Microsoft",
                    category="automation",
                    surface="browser",
                    tier="fallback_browser",
                    apps=[{"name": "Power Automate", "platforms": ["cloud", "web", "windows"]}],
                    capabilities=["network_access", "system_modify"],
                    risk="high",
                    notes="Enterprise workflow automation platform; initial integration via browser/API surfaces.",
                    healthcheck={"type": "none"},
                    driver={
                        "install": {
                            "type": "manual",
                            "risk": "medium",
                            "set_install_state": "registered",
                            "instructions": [
                                "Configurare tenant/account Power Automate e connettori richiesti.",
                                "Usare adapter browser/API Core Rth con policy Guardian per ambienti enterprise.",
                            ],
                        },
                        "enable": {"type": "state_only", "risk": "low", "install_state": "enabled", "enabled": True},
                        "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                    },
                ),
                {"priority": "P1", "pack": "workflow_automation", "status": "surface_unverified"},
            ),
            (
                _manifest_base(
                    plugin_id="workflow.ifttt",
                    name="IFTTT Automation Adapter",
                    vendor="IFTTT",
                    category="automation",
                    surface="browser",
                    tier="fallback_browser",
                    apps=[{"name": "IFTTT", "platforms": ["cloud", "web"]}],
                    capabilities=["network_access", "system_modify"],
                    risk="high",
                    notes="Consumer workflow automation service; browser/API integration target.",
                    healthcheck={"type": "none"},
                    driver={
                        "install": {
                            "type": "manual",
                            "risk": "medium",
                            "set_install_state": "registered",
                            "instructions": [
                                "Configurare account IFTTT e applet/service keys dove disponibili.",
                                "Attivare adapter browser/API in Core Rth per task approvati.",
                            ],
                        },
                        "enable": {"type": "state_only", "risk": "low", "install_state": "enabled", "enabled": True},
                        "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                    },
                ),
                {"priority": "P1", "pack": "workflow_automation", "status": "surface_unverified"},
            ),
            (
                _manifest_base(
                    plugin_id="workflow.flowise",
                    name="Flowise Workflow Builder Adapter",
                    vendor="FlowiseAI",
                    category="automation",
                    surface="hybrid",
                    tier="community",
                    apps=[{"name": "Flowise", "platforms": ["windows", "linux", "macos", "web"]}],
                    capabilities=["network_access", "process_exec", "filesystem_read"],
                    risk="high",
                    notes="Visual AI workflow builder (Flowise) for local/cloud orchestration scenarios.",
                    healthcheck={
                        "type": "composite",
                        "mode": "any",
                        "checks": [
                            {
                                "type": "command_version",
                                "commands": ["flowise"],
                                "args": ["--version"],
                                "match_any": ["flowise"],
                                "vendor_regex": r"(?i)\bflowise\b",
                                "version_regex": r"(?i)\b(\d+\.\d+(?:\.\d+)*)\b",
                                "require_regex_any": [r"(?i)\bflowise\b", r"\d+\.\d+(?:\.\d+)*"],
                            },
                            {
                                "type": "http_get",
                                "urls": [
                                    "http://127.0.0.1:3000/",
                                    "http://127.0.0.1:3001/",
                                ],
                            },
                        ],
                    },
                    driver={
                        "install": {
                            "type": "command_sequence",
                            "risk": "high",
                            "set_install_state": "registered",
                            "commands": [
                                ["npm", "install", "-g", "flowise"],
                                ["flowise", "--version"],
                            ],
                            "notes": "Install automatico Flowise via npm (verificare prerequisiti Node).",
                        },
                        "enable": {"type": "healthcheck_then_state", "risk": "medium"},
                        "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                    },
                ),
                {"priority": "P1", "pack": "workflow_automation"},
            ),
            (
                _manifest_base(
                    plugin_id="workflow.langflow",
                    name="Langflow Workflow Builder Adapter",
                    vendor="Langflow",
                    category="automation",
                    surface="hybrid",
                    tier="community",
                    apps=[{"name": "Langflow", "platforms": ["windows", "linux", "macos", "web"]}],
                    capabilities=["network_access", "process_exec", "filesystem_read"],
                    risk="high",
                    notes="Visual LLM workflow builder (Langflow) connector target for local/cloud orchestration.",
                    healthcheck={
                        "type": "composite",
                        "mode": "any",
                        "checks": [
                            {
                                "type": "command_version",
                                "commands": ["langflow"],
                                "args": ["--version"],
                                "match_any": ["langflow"],
                                "vendor_regex": r"(?i)\blangflow\b",
                                "version_regex": r"(?i)\b(\d+\.\d+(?:\.\d+)*)\b",
                                "require_regex_any": [r"(?i)\blangflow\b", r"\d+\.\d+(?:\.\d+)*"],
                            },
                            {"type": "http_get", "urls": ["http://127.0.0.1:7860/"]},
                        ],
                    },
                    driver={
                        "install": {
                            "type": "command_sequence",
                            "risk": "high",
                            "set_install_state": "registered",
                            "commands": [
                                ["python", "-m", "pip", "install", "-U", "langflow"],
                                ["langflow", "--version"],
                            ],
                            "notes": "Install automatico Langflow via pip.",
                        },
                        "enable": {"type": "healthcheck_then_state", "risk": "medium"},
                        "disable": {"type": "state_only", "risk": "low", "install_state": "disabled", "enabled": False},
                    },
                ),
                {"priority": "P1", "pack": "workflow_automation"},
            ),
        ])
        # Some broadly useful foundations to make the catalog look real on public release.
        rows.extend([
            (
                _manifest_base(
                    plugin_id="dev.vscode_workspace",
                    name="VS Code Workspace Adapter",
                    vendor="Microsoft",
                    category="development",
                    surface="filesystem",
                    tier="verified",
                    apps=[{"name": "VS Code", "platforms": ["windows", "linux", "macos"]}],
                    capabilities=["filesystem_read", "filesystem_write", "process_exec"],
                    risk="high",
                    notes="Workspace-centric integration via filesystem + command adapters.",
                    healthcheck={"type": "command_exists", "commands": ["code"]},
                ),
                {"priority": "P1", "pack": "dev_pack"},
            ),
            (
                _manifest_base(
                    plugin_id="browser.chromium_ops",
                    name="Chromium Browser Ops Adapter",
                    vendor="Chromium",
                    category="browser",
                    surface="browser",
                    tier="verified",
                    apps=[{"name": "Chrome/Edge", "platforms": ["windows", "linux", "macos", "web"]}],
                    capabilities=["browser", "network_access", "system_modify"] if False else ["network_access", "system_modify"],
                    risk="high",
                    notes="Browser automation fallback for closed tools and web apps.",
                    healthcheck={"type": "command_exists", "commands": ["chrome", "msedge", "chromium"]},
                ),
                {"priority": "P1", "pack": "browser_pack"},
            ),
        ])
        out = []
        for manifest, meta in rows:
            # Ensure schema compatibility (VALID_CAP doesn't include browser capability yet).
            manifest["capabilities_requested"] = [c for c in manifest["capabilities_requested"] if c in VALID_CAP]
            for a in manifest.get("actions", []):
                if a.get("capability") not in VALID_CAP:
                    a["capability"] = "network_access"
            out.append({"manifest": manifest, "meta": meta})
        return out


plugin_registry_public = PluginRegistryPublic()
