"""
Permission gate and policy for high-risk actions.
"""
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import json
import uuid
from pathlib import Path
import logging
import tempfile
import re
from .config import settings
from .guardian_policy_dsl import guardian_policy_dsl

logger = logging.getLogger(__name__)

HARD_NO_GO_CAPABILITIES = {"payments", "social_posting"}
OWNER_DECIDERS = {"owner", "policy"}
INTERNAL_PROCESS_EXEC_POLICY_ACTIONS = {
    "plugins_registry_healthcheck_exec",
    "plugins_registry_driver_install",
    "plugins_registry_driver_enable",
    "plugins_registry_driver_disable",
}

class Capability(Enum):
    FILESYSTEM_SCAN = "filesystem_scan"
    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    PROCESS_EXEC = "process_exec"
    NETWORK_ACCESS = "network_access"
    SYSTEM_MODIFY = "system_modify"
    SOCIAL_POSTING = "social_posting"
    PAYMENTS = "payments"
    DATA_EXPORT = "data_export"
    SWARM_ANALYSIS = "swarm_analysis"
    PLUGIN_RUNTIME = "plugin_runtime"

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Decision(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"

@dataclass
class PermissionRequest:
    request_id: str
    capability: Capability
    action: str
    scope: Dict[str, Any]
    reason: str
    risk: RiskLevel
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=24))
    decision: Decision = Decision.PENDING
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    denial_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "capability": self.capability.value,
            "action": self.action,
            "scope": self.scope,
            "reason": self.reason,
            "risk": self.risk.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "decision": self.decision.value,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "denial_reason": self.denial_reason,
        }

class PermissionGate:
    """
    Central permission gate. Nothing executes without explicit approval.
    """
    def __init__(self):
        self.requests: Dict[str, PermissionRequest] = {}
        self.hard_no_go = {Capability(x) for x in HARD_NO_GO_CAPABILITIES}
        self.no_go = set(self.hard_no_go)
        self.require_owner_approval = bool(getattr(settings, "RTH_REQUIRE_OWNER_APPROVAL", True))
        self.default_ttl_hours = max(1, int(getattr(settings, "RTH_PROPOSAL_TTL_HOURS", 24)))
        self.allowed_process_exec_actions = {
            str(x).strip().lower()
            for x in (getattr(settings, "RTH_PROCESS_EXEC_ALLOWED_ACTIONS", []) or [])
            if str(x).strip()
        }
        self.guardian_dsl = guardian_policy_dsl
        self._load_state()

    def set_no_go(self, capabilities: List[Capability]):
        self.no_go = set(capabilities) | set(self.hard_no_go)
        self._save_state()

    def propose(self, capability: Capability, action: str, scope: Dict[str, Any], reason: str, risk: RiskLevel) -> PermissionRequest:
        request = PermissionRequest(
            request_id=f"perm_{uuid.uuid4().hex[:8]}",
            capability=capability,
            action=action,
            scope=scope,
            reason=reason,
            risk=risk,
            expires_at=self._compute_expiry(risk),
        )
        # Attach Guardian/Cortex-derived execution policy context (if available) to the request scope.
        try:
            guardian_ctx = self._guardian_policy_context(capability=capability, action=action, scope=scope, risk=risk)
            if guardian_ctx:
                request.scope = dict(request.scope or {})
                request.scope["_guardian_policy"] = guardian_ctx
            elif capability in {Capability.PROCESS_EXEC, Capability.SYSTEM_MODIFY, Capability.FILESYSTEM_WRITE}:
                request.scope = dict(request.scope or {})
                request.scope["_guardian_policy"] = {
                    "source": "cortex_root_semantic_conflicts",
                    "status": "no_match",
                    "evaluated_at": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.debug(f"Guardian policy context unavailable: {e}")
        block_reason = self._proposal_block_reason(
            capability=capability,
            action=action,
            risk=risk,
            scope=request.scope,
            request_reason=reason,
        )
        if block_reason:
            request.decision = Decision.DENIED
            request.denial_reason = block_reason
            request.decided_at = datetime.now()
            request.decided_by = "policy"
        self.requests[request.request_id] = request
        self._save_state()
        return request

    def approve(self, request_id: str, decided_by: str = "owner") -> PermissionRequest:
        request = self.requests.get(request_id)
        if not request:
            raise ValueError("request_id not found")
        decided_by = str(decided_by or "").strip().lower() or "owner"
        if self.require_owner_approval and decided_by not in OWNER_DECIDERS:
            request.decision = Decision.DENIED
            request.denial_reason = "Only owner can approve requests under current policy"
            request.decided_at = datetime.now()
            request.decided_by = decided_by
            self._save_state()
            return request
        block_reason = self._proposal_block_reason(
            capability=request.capability,
            action=request.action,
            risk=request.risk,
            scope=request.scope,
            request_reason=request.reason,
        )
        if block_reason:
            request.decision = Decision.DENIED
            request.denial_reason = block_reason
            request.decided_at = datetime.now()
            request.decided_by = decided_by
            self._save_state()
            return request
        request.decision = Decision.APPROVED
        request.decided_at = datetime.now()
        request.decided_by = decided_by
        self._save_state()
        return request

    def deny(self, request_id: str, reason: str = "denied", decided_by: str = "owner") -> PermissionRequest:
        request = self.requests.get(request_id)
        if not request:
            raise ValueError("request_id not found")
        request.decision = Decision.DENIED
        request.denial_reason = reason
        request.decided_at = datetime.now()
        request.decided_by = decided_by
        self._save_state()
        return request

    def check(self, request_id: str) -> bool:
        request = self.requests.get(request_id)
        if not request:
            return False
        if request.decision != Decision.APPROVED:
            return False
        if datetime.now() > request.expires_at:
            request.decision = Decision.EXPIRED
            self._save_state()
            return False
        return True

    def list_requests(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.requests.values()]

    def policy_status(self) -> Dict[str, Any]:
        return {
            "hard_no_go": sorted([c.value for c in self.hard_no_go]),
            "no_go": sorted([c.value for c in self.no_go]),
            "require_owner_approval": self.require_owner_approval,
            "default_ttl_hours": self.default_ttl_hours,
            "allowed_process_exec_actions": sorted(self.allowed_process_exec_actions),
            "semantic_guard": {
                "enabled": True,
                "source": "cortex_root_semantic_conflicts",
                "covered_capabilities": [
                    Capability.PROCESS_EXEC.value,
                    Capability.SYSTEM_MODIFY.value,
                    Capability.FILESYSTEM_WRITE.value,
                ],
                "process_exec_strict_profiles": [
                    "strict_execute_gate",
                    "strict_execute_gate_plus_dry_run",
                ],
            },
            "guardian_dsl": self.guardian_dsl.status(),
            "guardian_severity": self.guardian_severity_status(),
        }

    def _guardian_lang(self, lang: str = "it") -> str:
        return "en" if str(lang or "").strip().lower().startswith("en") else "it"

    def _guardian_localization_maps(self, lang: str = "it") -> Dict[str, Any]:
        lc = self._guardian_lang(lang)
        if lc == "en":
            return {
                "capability": {
                    "filesystem_scan": "Filesystem scan",
                    "filesystem_read": "Filesystem read",
                    "filesystem_write": "Filesystem write",
                    "process_exec": "Process execution",
                    "network_access": "Network access",
                    "system_modify": "System modify",
                    "social_posting": "Social posting",
                    "payments": "Payments",
                    "data_export": "Data export",
                    "swarm_analysis": "Swarm analysis",
                    "plugin_runtime": "Plugin runtime",
                },
                "risk": {
                    "low": "Low",
                    "medium": "Medium",
                    "high": "High",
                    "critical": "Critical",
                },
                "decision": {
                    "pending": "Pending",
                    "approved": "Approved",
                    "denied": "Denied",
                    "expired": "Expired",
                },
                "summary": {
                    "title": "Guardian policy status",
                    "requests_title": "Guardian requests",
                    "owner_approval_required": "Owner approval required",
                    "semantic_guard_enabled": "Semantic guard enabled",
                },
            }
        return {
            "capability": {
                "filesystem_scan": "Scansione filesystem",
                "filesystem_read": "Lettura filesystem",
                "filesystem_write": "Scrittura filesystem",
                "process_exec": "Esecuzione processi",
                "network_access": "Accesso rete",
                "system_modify": "Modifica sistema",
                "social_posting": "Pubblicazione social",
                "payments": "Pagamenti",
                "data_export": "Esportazione dati",
                "swarm_analysis": "Analisi swarm",
                "plugin_runtime": "Runtime plugin",
            },
            "risk": {
                "low": "Basso",
                "medium": "Medio",
                "high": "Alto",
                "critical": "Critico",
            },
            "decision": {
                "pending": "In attesa",
                "approved": "Approvata",
                "denied": "Negata",
                "expired": "Scaduta",
            },
            "summary": {
                "title": "Stato policy Guardian",
                "requests_title": "Richieste Guardian",
                "owner_approval_required": "Approvazione owner richiesta",
                "semantic_guard_enabled": "Guardia semantica attiva",
            },
        }

    def _guardian_localize_message(self, text: Optional[str], lang: str = "it") -> Optional[str]:
        if text is None:
            return None
        raw = str(text)
        lc = self._guardian_lang(lang)
        if lc == "en":
            return raw
        translated = raw
        replacements = [
            ("Only owner can approve requests under current policy", "Solo l'owner puo approvare richieste con la policy corrente"),
            ("Blocked by Guardian semantic policy:", "Bloccato dalla policy semantica Guardian:"),
            ("risky launcher/action on strict security root", "launcher/azione rischiosa su root security strict"),
            ("request_id not found", "request_id non trovato"),
            ("denied", "negato"),
        ]
        for src, dst in replacements:
            translated = translated.replace(src, dst)
        return translated

    def list_requests_localized(self, lang: str = "it") -> Dict[str, Any]:
        lc = self._guardian_lang(lang)
        maps = self._guardian_localization_maps(lc)
        items: List[Dict[str, Any]] = []
        raw_items = self.list_requests()
        for r in raw_items:
            item = dict(r)
            item["localized"] = {
                "capability_label": maps["capability"].get(str(item.get("capability", "")), str(item.get("capability", ""))),
                "risk_label": maps["risk"].get(str(item.get("risk", "")), str(item.get("risk", ""))),
                "decision_label": maps["decision"].get(str(item.get("decision", "")), str(item.get("decision", ""))),
                "denial_reason": self._guardian_localize_message(item.get("denial_reason"), lc),
            }
            items.append(item)
        return {
            "lang": lc,
            "summary": {
                "title": maps["summary"]["requests_title"],
                "total": len(items),
                "pending": sum(1 for x in items if x.get("decision") == "pending"),
                "approved": sum(1 for x in items if x.get("decision") == "approved"),
                "denied": sum(1 for x in items if x.get("decision") == "denied"),
                "expired": sum(1 for x in items if x.get("decision") == "expired"),
            },
            "requests": items,
        }

    def policy_status_localized(self, lang: str = "it") -> Dict[str, Any]:
        lc = self._guardian_lang(lang)
        maps = self._guardian_localization_maps(lc)
        data = self.policy_status()
        data["guardian_severity"] = self.guardian_severity_status(lang=lc)
        data["localized"] = {
            "lang": lc,
            "title": maps["summary"]["title"],
            "owner_approval_required_label": maps["summary"]["owner_approval_required"],
            "semantic_guard_enabled_label": maps["summary"]["semantic_guard_enabled"],
            "no_go_labels": [maps["capability"].get(x, x) for x in (data.get("no_go") or [])],
            "hard_no_go_labels": [maps["capability"].get(x, x) for x in (data.get("hard_no_go") or [])],
            "covered_capabilities_labels": [
                maps["capability"].get(x, x)
                for x in ((data.get("semantic_guard") or {}).get("covered_capabilities") or [])
            ],
        }
        return data

    def guardian_dsl_get(self) -> Dict[str, Any]:
        return {
            "status": self.guardian_dsl.status(),
            "policy": self.guardian_dsl.load(),
        }

    def guardian_dsl_validate_file(self, path: str) -> Dict[str, Any]:
        return self.guardian_dsl.validate_file(path)

    def guardian_dsl_validate_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.guardian_dsl.validate_payload(payload)

    def guardian_dsl_set(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = self.guardian_dsl.save(payload)
        return {
            **result,
            "status_detail": self.guardian_dsl.status(),
        }

    def guardian_dsl_set_default(self) -> Dict[str, Any]:
        payload = self.guardian_dsl.default_policy()
        return self.guardian_dsl_set(payload)

    def guardian_severity_profiles(self, lang: str = "it") -> List[Dict[str, Any]]:
        lang_norm = str(lang or "it").strip().lower()
        en = lang_norm.startswith("en")
        return [
            {
                "severity": "lenient",
                "label": "Lenient" if en else "Lenient",
                "description": (
                    "Keeps critical blocks, reduces blocks on strict roots and interactive UI clicks."
                    if en else
                    "Mantiene i blocchi critici, riduce i blocchi su root strict e click UI interattivi."
                ),
            },
            {
                "severity": "balanced",
                "label": "Balanced",
                "description": (
                    "Recommended default: critical blocks + semantic governance + high-risk audit."
                    if en else
                    "Default consigliato: blocchi critici + governance semantica + audit high-risk."
                ),
            },
            {
                "severity": "strict",
                "label": "Strict",
                "description": (
                    "Increases deny rules on high-risk network/filesystem/system_modify when safety markers are missing."
                    if en else
                    "Aumenta i deny su network/filesystem/system_modify high-risk se mancano marker di sicurezza."
                ),
            },
            {
                "severity": "paranoid",
                "label": "Paranoid",
                "description": (
                    "Maximum mode: aggressive blocks on medium+ network access and high-risk modifications without markers."
                    if en else
                    "Modalita' massima: blocchi aggressivi su network medium+ e modifiche high-risk senza marker."
                ),
            },
        ]

    def guardian_severity_status(self, lang: str = "it") -> Dict[str, Any]:
        policy = self.guardian_dsl.load()
        meta = policy.get("meta") if isinstance(policy.get("meta"), dict) else {}
        severity = str(meta.get("severity_profile") or "").strip().lower()
        if severity not in {"lenient", "balanced", "strict", "paranoid"}:
            severity = self._infer_guardian_severity(policy)
        rules = [r for r in (policy.get("rules") or []) if isinstance(r, dict)]
        enabled_rules = [r for r in rules if bool(r.get("enabled", True))]
        return {
            "current": severity,
            "profiles": self.guardian_severity_profiles(lang=lang),
            "mode": str(policy.get("mode", "enforce")),
            "rules_total": len(rules),
            "rules_enabled": len(enabled_rules),
            "rule_ids_enabled": [str(r.get("id")) for r in enabled_rules if str(r.get("id", "")).strip()],
            "meta": meta,
        }

    def guardian_severity_apply(
        self,
        severity: str,
        reason: str = "Update guardian severity profile",
        confirm_owner: bool = True,
        decided_by: str = "owner",
        lang: str = "it",
    ) -> Dict[str, Any]:
        severity_norm = str(severity or "").strip().lower()
        valid = {"lenient", "balanced", "strict", "paranoid"}
        if severity_norm not in valid:
            return {
                "status": "invalid",
                "detail": (
                    f"Unknown severity '{severity}'. Valid: {sorted(valid)}"
                    if str(lang or "").lower().startswith("en")
                    else f"Severita sconosciuta '{severity}'. Valori validi: {sorted(valid)}"
                ),
                "available": self.guardian_severity_profiles(lang=lang),
            }

        payload = self._guardian_policy_for_severity(severity_norm)
        proposal_reason = str(reason or "").strip() or "Update guardian severity profile"
        if not any(tok in proposal_reason.lower() for tok in ("audit", "safe", "dry-run")):
            # Prevent self-lockout when strict/paranoid profiles require change-control markers on filesystem writes.
            proposal_reason = f"{proposal_reason} [audit]"

        req = self.propose(
            capability=Capability.FILESYSTEM_WRITE,
            action="guardian_severity_apply",
            scope={
                "severity": severity_norm,
                "target_path": self.guardian_dsl.status().get("path"),
                "rules_total": len(list(payload.get("rules") or [])),
            },
            reason=proposal_reason,
            risk=RiskLevel.HIGH,
        )
        out: Dict[str, Any] = {
            "status": "proposal_only" if not confirm_owner else "pending",
            "severity": severity_norm,
            "proposal": req.to_dict(),
            "preview": {
                "mode": payload.get("mode", "enforce"),
                "rules_total": len(list(payload.get("rules") or [])),
                "rules_enabled": len([r for r in (payload.get("rules") or []) if isinstance(r, dict) and bool(r.get("enabled", True))]),
                "rule_ids_enabled": [str(r.get("id")) for r in (payload.get("rules") or []) if isinstance(r, dict) and bool(r.get("enabled", True))],
            },
        }
        if not confirm_owner:
            return out

        decision = self.approve(req.request_id, decided_by=decided_by)
        out["decision"] = decision.to_dict()
        if decision.decision.value != "approved":
            out["status"] = "denied"
            return out
        saved = self.guardian_dsl_set(payload)
        out["status"] = "ok"
        out["saved"] = saved
        out["severity_status"] = self.guardian_severity_status(lang=lang)
        out["localized"] = {
            "lang": "en" if str(lang or "").lower().startswith("en") else "it",
            "message": (
                f"Guardian severity set to {severity_norm}."
                if str(lang or "").lower().startswith("en")
                else f"Severita Guardian impostata su {severity_norm}."
            ),
        }
        return out

    def _infer_guardian_severity(self, policy: Dict[str, Any]) -> str:
        rules = [r for r in (policy.get("rules") or []) if isinstance(r, dict)]
        ids_enabled = {str(r.get("id")) for r in rules if bool(r.get("enabled", True))}
        if "deny_medium_network_access_paranoid" in ids_enabled:
            return "paranoid"
        if "deny_high_network_access_without_safe_marker" in ids_enabled:
            return "strict"
        if "deny_interactive_mouse_clicks_without_ui_safe_reason" not in ids_enabled:
            return "lenient"
        return "balanced"

    def _guardian_policy_for_severity(self, severity: str) -> Dict[str, Any]:
        payload = self.guardian_dsl.default_policy()
        payload["enabled"] = True
        payload["mode"] = "enforce"
        payload["meta"] = {
            "severity_profile": severity,
            "updated_at": datetime.now().isoformat(),
            "source": "guardian_severity_apply",
        }
        rules = [r for r in (payload.get("rules") or []) if isinstance(r, dict)]
        by_id = {str(r.get("id")): r for r in rules if str(r.get("id", "")).strip()}

        def _set_enabled(rule_id: str, enabled: bool) -> None:
            rule = by_id.get(rule_id)
            if rule:
                rule["enabled"] = bool(enabled)

        if severity == "lenient":
            _set_enabled("deny_interactive_mouse_clicks_without_ui_safe_reason", False)
            _set_enabled("deny_strict_root_process_exec_with_auditability_gap", False)
            _set_enabled("deny_strict_root_filesystem_write_without_snapshot_or_dryrun", False)
            return payload

        if severity in {"strict", "paranoid"}:
            rules.extend([
                {
                    "id": "deny_high_network_access_without_safe_marker",
                    "enabled": True,
                    "when": {
                        "capabilities_any": ["network_access"],
                        "risk_at_least": "high",
                        "reason_tokens_none": ["safe", "dry-run", "audit", "mirror", "healthcheck"],
                    },
                    "effect": {
                        "decision": "deny",
                        "reason": "Blocked by Guardian DSL (strict): high-risk network access requires safe/audit marker",
                    },
                },
                {
                    "id": "deny_high_system_modify_without_safe_marker",
                    "enabled": True,
                    "when": {
                        "capabilities_any": ["system_modify"],
                        "risk_at_least": "high",
                        "reason_tokens_none": ["safe", "dry-run", "test-controlled", "owner-live", "position"],
                    },
                    "effect": {
                        "decision": "deny",
                        "reason": "Blocked by Guardian DSL (strict): high-risk system modifications require safe/test marker",
                    },
                },
                {
                    "id": "deny_high_filesystem_write_without_change_control_marker",
                    "enabled": True,
                    "when": {
                        "capabilities_any": ["filesystem_write"],
                        "risk_at_least": "high",
                        "reason_tokens_none": ["safe", "dry-run", "snapshot", "audit", "rollback", "export"],
                    },
                    "effect": {
                        "decision": "deny",
                        "reason": "Blocked by Guardian DSL (strict): high-risk filesystem writes require snapshot/audit/rollback marker",
                    },
                },
            ])

        if severity == "paranoid":
            rules.extend([
                {
                    "id": "deny_medium_network_access_paranoid",
                    "enabled": True,
                    "when": {
                        "capabilities_any": ["network_access"],
                        "risk_at_least": "medium",
                        "reason_tokens_none": ["safe", "audit", "dry-run", "healthcheck"],
                    },
                    "effect": {
                        "decision": "deny",
                        "reason": "Blocked by Guardian DSL (paranoid): medium+ network access denied without explicit safe marker",
                    },
                },
                {
                    "id": "deny_paranoid_process_exec_high_without_replay_marker",
                    "enabled": True,
                    "when": {
                        "capabilities_any": ["process_exec"],
                        "risk_at_least": "high",
                        "reason_tokens_none": ["safe", "dry-run", "status", "replay", "audit"],
                    },
                    "effect": {
                        "decision": "deny",
                        "reason": "Blocked by Guardian DSL (paranoid): high-risk process execution requires replay/audit/safe marker",
                    },
                },
            ])

        payload["rules"] = rules
        return payload

    def _state_path(self) -> Optional[Path]:
        if getattr(settings, "RTH_DISKLESS", False):
            return None
        candidates = [
            Path("storage") / "consent",
            Path("storage_runtime") / "consent",
            Path(tempfile.gettempdir()) / "rth_core" / "consent",
        ]
        for base in candidates:
            try:
                base.mkdir(parents=True, exist_ok=True)
                probe = base / ".write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return base / "requests.json"
            except Exception:
                continue
        return None

    def _save_state(self):
        path = self._state_path()
        if not path:
            return
        payload = {
            "no_go": [c.value for c in self.no_go],
            "requests": [r.to_dict() for r in self.requests.values()]
        }
        try:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except PermissionError as e:
            logger.warning(f"Failed to save permission state: {e}")

    def _load_state(self):
        path = self._state_path()
        if not path or not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            loaded = {Capability(c) for c in payload.get("no_go", []) if c in Capability._value2member_map_}
            self.no_go = loaded | set(self.hard_no_go)
            for item in payload.get("requests", []):
                request = PermissionRequest(
                    request_id=item["request_id"],
                    capability=Capability(item["capability"]),
                    action=item["action"],
                    scope=item.get("scope", {}),
                    reason=item.get("reason", ""),
                    risk=RiskLevel(item.get("risk", "low")),
                    created_at=datetime.fromisoformat(item["created_at"]),
                    expires_at=datetime.fromisoformat(item["expires_at"]),
                    decision=Decision(item.get("decision", "pending")),
                    decided_by=item.get("decided_by"),
                    decided_at=datetime.fromisoformat(item["decided_at"]) if item.get("decided_at") else None,
                    denial_reason=item.get("denial_reason")
                )
                self.requests[request.request_id] = request
        except Exception as e:
            logger.warning(f"Failed to load permission state: {e}")

    def _compute_expiry(self, risk: RiskLevel) -> datetime:
        now = datetime.now()
        if risk == RiskLevel.CRITICAL:
            return now + timedelta(hours=1)
        if risk == RiskLevel.HIGH:
            return now + timedelta(hours=min(8, self.default_ttl_hours))
        if risk == RiskLevel.MEDIUM:
            return now + timedelta(hours=self.default_ttl_hours)
        return now + timedelta(hours=min(72, self.default_ttl_hours * 2))

    def _proposal_block_reason(
        self,
        capability: Capability,
        action: str,
        risk: RiskLevel,
        scope: Optional[Dict[str, Any]] = None,
        request_reason: str = "",
    ) -> Optional[str]:
        if capability in self.no_go:
            return "Capability is marked as NO-GO"
        normalized_action = str(action or "").strip().lower()
        scope = scope or {}
        if capability == Capability.PROCESS_EXEC:
            if risk == RiskLevel.CRITICAL:
                return "Critical process execution requests are blocked by policy"
            if (
                self.allowed_process_exec_actions
                and normalized_action not in self.allowed_process_exec_actions
                and normalized_action not in INTERNAL_PROCESS_EXEC_POLICY_ACTIONS
            ):
                return f"process_exec action '{normalized_action}' is not in allowlist"
            semantic_block = self._semantic_process_exec_block(scope=scope, action=normalized_action)
            if semantic_block:
                return semantic_block
        dsl_block = self._dsl_block_reason(
            capability=capability,
            action=normalized_action,
            risk=risk,
            scope=scope,
            request_reason=request_reason,
        )
        if dsl_block:
            return dsl_block
        return None

    def _dsl_block_reason(
        self,
        capability: Capability,
        action: str,
        risk: RiskLevel,
        scope: Optional[Dict[str, Any]],
        request_reason: str = "",
    ) -> Optional[str]:
        scope = scope or {}
        if not isinstance(scope, dict):
            return None
        dsl_scope = dict(scope)
        if request_reason and not dsl_scope.get("reason"):
            dsl_scope["reason"] = str(request_reason)
        guardian_ctx = (scope.get("_guardian_policy") if isinstance(scope.get("_guardian_policy"), dict) else {}) or {}
        try:
            dsl_eval = self.guardian_dsl.evaluate(
                capability=capability.value,
                action=str(action or ""),
                risk=risk.value,
                scope=dsl_scope,
                guardian_ctx=guardian_ctx,
            )
        except Exception as e:
            logger.debug(f"Guardian DSL evaluation failed: {e}")
            return None

        # Attach evaluation snapshot to request scope for auditability.
        gp = dict(guardian_ctx)
        gp["_dsl"] = {
            "enabled": dsl_eval.get("enabled", False),
            "mode": dsl_eval.get("mode"),
            "decision": dsl_eval.get("decision"),
            "deny_reason": dsl_eval.get("deny_reason"),
            "matched_rules": [r.get("id") for r in (dsl_eval.get("matched_rules") or []) if isinstance(r, dict)],
            "notes": dsl_eval.get("notes") or [],
            "evaluated_at": datetime.now().isoformat(),
        }
        scope["_guardian_policy"] = gp

        if dsl_eval.get("decision") == "deny":
            return str(dsl_eval.get("deny_reason") or "Blocked by Guardian DSL")
        return None

    def _semantic_process_exec_block(self, scope: Dict[str, Any], action: str) -> Optional[str]:
        """
        Guardian hook: use Cortex semantic root conflicts to auto-block unsafe process execution
        on roots that require stricter contracts (e.g., security orchestrators).
        """
        ctx = (scope or {}).get("_guardian_policy")
        if not isinstance(ctx, dict):
            try:
                ctx = self._guardian_policy_context(
                    capability=Capability.PROCESS_EXEC,
                    action=action,
                    scope=scope or {},
                    risk=RiskLevel.HIGH,
                ) or {}
            except Exception:
                ctx = {}
        target_roots = [str(x) for x in (ctx.get("target_roots") or []) if x]
        if not target_roots:
            return None

        execution_text = " ".join(self._scope_exec_tokens(scope=scope, action=action)).lower()
        risky_markers = ("redteam", "web-live", "swarm-live", "swarm-full", "cascade")
        safe_markers = ("safe", "status", "setup-auth-context", "log", "compileall", "pytest", "dry-run")
        has_risky = any(m in execution_text for m in risky_markers)
        has_safe = any(m in execution_text for m in safe_markers)

        strict_profiles = set(str(x) for x in (ctx.get("governance_profiles") or []) if x)
        if "strict_execute_gate_plus_dry_run" in strict_profiles:
            if has_risky:
                return "Blocked by Guardian semantic policy: risky launcher/action on strict security root"
            if not has_safe:
                return (
                    "Blocked by Guardian semantic policy: strict security root requires safe/dry-run/status-style "
                    "execution proposal before approval"
                )
        elif "strict_execute_gate" in strict_profiles and has_risky:
            return "Blocked by Guardian semantic policy: risky launcher/action on strict root"
        return None

    def _scope_exec_tokens(self, scope: Dict[str, Any], action: str) -> List[str]:
        tokens: List[str] = [str(action or "")]
        if not isinstance(scope, dict):
            return tokens
        for key in ("app_path", "root", "workspace", "reason", "path", "target_path", "output_path"):
            val = scope.get(key)
            if isinstance(val, str):
                tokens.append(val)
        cmd = scope.get("command")
        if isinstance(cmd, list):
            tokens.extend([str(x) for x in cmd if x is not None])
        args = scope.get("args")
        if isinstance(args, list):
            tokens.extend([str(x) for x in args if x is not None])
        for key in ("roots", "strategic_roots", "paths"):
            vals = scope.get(key)
            if isinstance(vals, list):
                tokens.extend([str(x) for x in vals if x is not None])
        return tokens

    def _guardian_policy_context(
        self,
        capability: Capability,
        action: str,
        scope: Dict[str, Any],
        risk: RiskLevel,
    ) -> Optional[Dict[str, Any]]:
        # Only enrich execution-like requests; scans are governed elsewhere.
        if capability not in {Capability.PROCESS_EXEC, Capability.SYSTEM_MODIFY, Capability.FILESYSTEM_WRITE}:
            return None
        cortex = self._safe_get_cortex()
        if cortex is None:
            return None
        try:
            status = cortex.get_status()
        except Exception:
            return None
        if not isinstance(status, dict):
            return None

        roots = self._resolve_scope_roots_from_cortex(scope=scope, cortex_status=status)
        if not roots:
            return None

        root_rows = status.get("root_analytics") if isinstance(status.get("root_analytics"), list) else []
        semantic_conflicts = status.get("root_semantic_conflicts") if isinstance(status.get("root_semantic_conflicts"), list) else []
        root_contracts: Dict[str, Dict[str, Any]] = {}
        root_domains: Dict[str, str] = {}
        for item in semantic_conflicts:
            if not isinstance(item, dict):
                continue
            pair_roots = item.get("roots") if isinstance(item.get("roots"), list) else []
            contracts = item.get("contracts") if isinstance(item.get("contracts"), dict) else {}
            contract_a = contracts.get("a") if isinstance(contracts.get("a"), dict) else {}
            contract_b = contracts.get("b") if isinstance(contracts.get("b"), dict) else {}
            if len(pair_roots) >= 2 and isinstance(pair_roots[0], str):
                root_contracts[self._norm_path(pair_roots[0])] = contract_a
                root_domains[self._norm_path(pair_roots[0])] = str(contract_a.get("domain") or "")
            if len(pair_roots) >= 2 and isinstance(pair_roots[1], str):
                root_contracts[self._norm_path(pair_roots[1])] = contract_b
                root_domains[self._norm_path(pair_roots[1])] = str(contract_b.get("domain") or "")

        for row in root_rows:
            if not isinstance(row, dict):
                continue
            r = row.get("root")
            if not isinstance(r, str):
                continue
            nr = self._norm_path(r)
            root_domains.setdefault(nr, str(row.get("domain") or ""))
            if nr not in root_contracts:
                root_contracts[nr] = {
                    "domain": row.get("domain"),
                    "governance_profile": "strict_execute_gate" if row.get("scan_flags", {}).get("has_launcher") else "normal_execute_gate",
                    "flags": row.get("scan_flags") or {},
                }

        matched_contracts = []
        governance_profiles = set()
        domains = set()
        matched_roots = []
        for r in roots:
            nr = self._norm_path(r)
            matched_roots.append(r)
            c = root_contracts.get(nr) or {}
            if c:
                matched_contracts.append(c)
                gp = c.get("governance_profile")
                if isinstance(gp, str) and gp:
                    governance_profiles.add(gp)
                dom = c.get("domain") or root_domains.get(nr)
                if isinstance(dom, str) and dom:
                    domains.add(dom)

        conflict_types = set()
        conflict_recommended = []
        for item in semantic_conflicts:
            if not isinstance(item, dict):
                continue
            pair_roots = [self._norm_path(x) for x in (item.get("roots") or []) if isinstance(x, str)]
            if not pair_roots:
                continue
            if not any(self._norm_path(r) in pair_roots for r in roots):
                continue
            for f in (item.get("semantic_conflicts") or []):
                if not isinstance(f, dict):
                    continue
                t = f.get("type")
                if isinstance(t, str):
                    conflict_types.add(t)
                rc = f.get("recommended_contract")
                if isinstance(rc, str) and rc not in conflict_recommended:
                    conflict_recommended.append(rc)

        return {
            "source": "cortex_root_semantic_conflicts",
            "capability": capability.value,
            "action": str(action or ""),
            "risk": risk.value,
            "target_roots": matched_roots,
            "domains": sorted(domains),
            "governance_profiles": sorted(governance_profiles),
            "semantic_conflict_types": sorted(conflict_types),
            "recommended_contracts": conflict_recommended[:8],
            "evaluated_at": datetime.now().isoformat(),
        }

    def _resolve_scope_roots_from_cortex(self, scope: Dict[str, Any], cortex_status: Dict[str, Any]) -> List[str]:
        rows = cortex_status.get("root_analytics") if isinstance(cortex_status.get("root_analytics"), list) else []
        known_roots = [str(r.get("root")) for r in rows if isinstance(r, dict) and isinstance(r.get("root"), str)]
        known_norm = [(r, self._norm_path(r)) for r in known_roots]
        out: List[str] = []

        def _best_known_root(candidate: str) -> Optional[str]:
            cn = self._norm_path(candidate)
            best_match = None
            best_len = -1
            for original, nr in known_norm:
                if (cn == nr or cn.startswith(nr + "/") or cn.startswith(nr)) and len(nr) > best_len:
                    best_match = original
                    best_len = len(nr)
            return best_match

        explicit_root = scope.get("root")
        if isinstance(explicit_root, str) and explicit_root.strip():
            root = explicit_root.strip()
            mapped = _best_known_root(root) or root
            if mapped not in out:
                out.append(mapped)

        candidates: List[str] = []
        for key in ("app_path",):
            v = scope.get(key)
            if isinstance(v, str) and v.strip():
                candidates.append(v.strip())
        for key in ("path", "target_path", "output_path"):
            v = scope.get(key)
            if isinstance(v, str) and v.strip():
                candidates.append(v.strip())
        for key in ("roots", "strategic_roots", "paths"):
            vals = scope.get(key)
            if isinstance(vals, list):
                candidates.extend([str(x).strip() for x in vals if isinstance(x, str) and str(x).strip()])
        cmd = scope.get("command")
        if isinstance(cmd, list):
            candidates.extend([str(x).strip() for x in cmd if isinstance(x, str)])

        for c in candidates:
            best_match = _best_known_root(c)
            if best_match and best_match not in out:
                out.append(best_match)
        return out

    def _safe_get_cortex(self):
        try:
            from .rth_cortex import get_cortex
            return get_cortex()
        except Exception:
            return None

    def _norm_path(self, value: str) -> str:
        norm = str(value or "").strip().lower().replace("\\", "/")
        return re.sub(r"/+", "/", norm)

permission_gate = PermissionGate()
