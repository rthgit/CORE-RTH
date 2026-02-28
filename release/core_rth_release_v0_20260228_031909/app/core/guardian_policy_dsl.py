"""
Guardian Policy DSL v0

A small JSON rule engine for additional Guardian enforcement beyond hardcoded checks.
Designed to be:
- local-first
- inspectable
- easy to validate and version
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import re
import tempfile

from .config import settings

logger = logging.getLogger(__name__)

RISK_ORDER = {"low": 1, "medium": 2, "high": 3, "critical": 4}


class GuardianPolicyDSL:
    def __init__(self):
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_mtime: Optional[float] = None

    def status(self) -> Dict[str, Any]:
        policy = self.load()
        path = self._policy_path()
        rules = list(policy.get("rules") or [])
        enabled_rules = [r for r in rules if isinstance(r, dict) and bool(r.get("enabled", True))]
        return {
            "enabled": bool(policy.get("enabled", True)),
            "version": policy.get("version", 1),
            "path": str(path) if path else None,
            "exists": bool(path and path.exists()),
            "rules_total": len(rules),
            "rules_enabled": len(enabled_rules),
            "mode": str(policy.get("mode", "enforce")),
        }

    def default_policy(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "enabled": True,
            "mode": "enforce",  # enforce | audit_only
            "rules": [
                {
                    "id": "deny_critical_network_access",
                    "enabled": True,
                    "when": {
                        "capabilities_any": ["network_access"],
                        "risk_at_least": "critical",
                    },
                    "effect": {
                        "decision": "deny",
                        "reason": "Blocked by Guardian DSL: critical network access requires explicit policy exception",
                    },
                },
                {
                    "id": "deny_critical_filesystem_write",
                    "enabled": True,
                    "when": {
                        "capabilities_any": ["filesystem_write"],
                        "risk_at_least": "critical",
                    },
                    "effect": {
                        "decision": "deny",
                        "reason": "Blocked by Guardian DSL: critical filesystem writes require explicit policy exception",
                    },
                },
                {
                    "id": "deny_interactive_mouse_clicks_without_ui_safe_reason",
                    "enabled": True,
                    "when": {
                        "capabilities_any": ["system_modify"],
                        "actions_any": ["mouse_action"],
                        "scope_field_any": {"action": ["click", "double_click", "right_click"]},
                        "reason_tokens_none": ["safe", "dry-run", "test-controlled", "owner-live"],
                    },
                    "effect": {
                        "decision": "deny",
                        "reason": "Blocked by Guardian DSL: interactive mouse clicks require explicit safe/test reason marker",
                    },
                },
                {
                    "id": "deny_strict_root_process_exec_with_auditability_gap",
                    "enabled": True,
                    "when": {
                        "capabilities_any": ["process_exec"],
                        "governance_profiles_any": ["strict_execute_gate", "strict_execute_gate_plus_dry_run"],
                        "semantic_conflict_types_any": ["auditability_asymmetry"],
                        "exec_tokens_none": ["status", "safe", "dry-run", "log", "setup-auth-context", "pytest"],
                    },
                    "effect": {
                        "decision": "deny",
                        "reason": "Blocked by Guardian DSL: strict root with auditability asymmetry allows only safe/dry-run/status executions",
                    },
                },
                {
                    "id": "deny_strict_root_filesystem_write_without_snapshot_or_dryrun",
                    "enabled": True,
                    "when": {
                        "capabilities_any": ["filesystem_write"],
                        "governance_profiles_any": ["strict_execute_gate", "strict_execute_gate_plus_dry_run"],
                        "semantic_conflict_types_any": ["auditability_asymmetry", "verification_depth_gap"],
                        "reason_tokens_none": ["safe", "dry-run", "snapshot", "audit", "export"],
                    },
                    "effect": {
                        "decision": "deny",
                        "reason": "Blocked by Guardian DSL: strict root filesystem writes require snapshot/audit or explicit dry-run marker",
                    },
                },
                {
                    "id": "audit_system_modify_high_risk",
                    "enabled": True,
                    "when": {
                        "capabilities_any": ["system_modify"],
                        "risk_at_least": "high",
                    },
                    "effect": {
                        "decision": "annotate",
                        "note": "High-risk system modifications should have replayable audit trail and rollback note",
                    },
                },
                {
                    "id": "audit_filesystem_write_high_risk",
                    "enabled": True,
                    "when": {
                        "capabilities_any": ["filesystem_write"],
                        "risk_at_least": "high",
                    },
                    "effect": {
                        "decision": "annotate",
                        "note": "High-risk filesystem writes should include target scope, backup/snapshot plan, and rollback note",
                    },
                },
            ],
        }

    def load(self, force_reload: bool = False) -> Dict[str, Any]:
        path = self._policy_path()
        if not path:
            return self.default_policy()

        if not force_reload and self._cache is not None and path.exists():
            try:
                mtime = path.stat().st_mtime
                if self._cache_mtime == mtime:
                    return self._cache
            except Exception:
                pass

        if not path.exists():
            policy = self.default_policy()
            self._cache = policy
            self._cache_mtime = None
            return policy

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            valid = self.validate_payload(payload)
            if not valid["ok"]:
                logger.warning("Guardian DSL invalid on disk; using defaults")
                policy = self.default_policy()
            else:
                policy = payload
            self._cache = policy
            try:
                self._cache_mtime = path.stat().st_mtime
            except Exception:
                self._cache_mtime = None
            return policy
        except Exception as e:
            logger.warning(f"Failed to load Guardian DSL: {e}")
            policy = self.default_policy()
            self._cache = policy
            self._cache_mtime = None
            return policy

    def save(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        valid = self.validate_payload(payload)
        if not valid["ok"]:
            raise ValueError("Invalid Guardian DSL payload")
        path = self._policy_path()
        if not path:
            raise PermissionError("No writable Guardian DSL path available")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._cache = payload
        try:
            self._cache_mtime = path.stat().st_mtime
        except Exception:
            self._cache_mtime = None
        return {"status": "saved", "path": str(path), "validation": valid}

    def validate_payload(self, payload: Any) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []
        if not isinstance(payload, dict):
            return {"ok": False, "errors": ["payload must be an object"], "warnings": []}

        version = payload.get("version", 1)
        if version != 1:
            errors.append("version must be 1")

        mode = str(payload.get("mode", "enforce"))
        if mode not in {"enforce", "audit_only"}:
            errors.append("mode must be 'enforce' or 'audit_only'")

        rules = payload.get("rules")
        if not isinstance(rules, list):
            errors.append("rules must be an array")
            rules = []

        seen_ids = set()
        for idx, rule in enumerate(rules):
            prefix = f"rules[{idx}]"
            if not isinstance(rule, dict):
                errors.append(f"{prefix} must be an object")
                continue
            rid = str(rule.get("id", "")).strip()
            if not rid:
                errors.append(f"{prefix}.id is required")
            elif rid in seen_ids:
                errors.append(f"{prefix}.id duplicate: {rid}")
            seen_ids.add(rid)

            when = rule.get("when")
            effect = rule.get("effect")
            if not isinstance(when, dict):
                errors.append(f"{prefix}.when must be an object")
            if not isinstance(effect, dict):
                errors.append(f"{prefix}.effect must be an object")
                continue

            decision = str(effect.get("decision", "")).strip()
            if decision not in {"deny", "annotate", "allow"}:
                errors.append(f"{prefix}.effect.decision must be one of deny|annotate|allow")

            if decision == "deny" and not str(effect.get("reason", "")).strip():
                errors.append(f"{prefix}.effect.reason required for deny")

            if isinstance(when, dict):
                risk_at_least = when.get("risk_at_least")
                if risk_at_least is not None and str(risk_at_least).lower() not in RISK_ORDER:
                    errors.append(f"{prefix}.when.risk_at_least invalid")

                for key in [
                    "capabilities_any",
                    "actions_any",
                    "governance_profiles_any",
                    "semantic_conflict_types_any",
                    "exec_tokens_any",
                    "exec_tokens_none",
                    "reason_tokens_any",
                    "reason_tokens_none",
                ]:
                    if key in when and not isinstance(when.get(key), list):
                        errors.append(f"{prefix}.when.{key} must be an array")

                if "scope_field_any" in when and not isinstance(when.get("scope_field_any"), dict):
                    errors.append(f"{prefix}.when.scope_field_any must be an object")

            if str(effect.get("decision")) == "allow":
                warnings.append(f"{prefix} uses allow (use sparingly; hardcoded policy still applies first)")

        return {"ok": not errors, "errors": errors, "warnings": warnings}

    def validate_file(self, path: str) -> Dict[str, Any]:
        p = Path(path)
        if not p.exists():
            return {"ok": False, "errors": [f"file not found: {path}"], "warnings": []}
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            return {"ok": False, "errors": [f"invalid json: {e}"], "warnings": []}
        out = self.validate_payload(payload)
        out["path"] = str(p)
        return out

    def evaluate(
        self,
        *,
        capability: str,
        action: str,
        risk: str,
        scope: Optional[Dict[str, Any]] = None,
        guardian_ctx: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        policy = self.load()
        if not bool(policy.get("enabled", True)):
            return {"enabled": False, "mode": policy.get("mode", "enforce"), "matched_rules": [], "decision": None}

        scope = scope or {}
        guardian_ctx = guardian_ctx or {}
        mode = str(policy.get("mode", "enforce"))
        matched_rules: List[Dict[str, Any]] = []
        deny_reason: Optional[str] = None
        notes: List[str] = []

        for rule in policy.get("rules", []):
            if not isinstance(rule, dict) or not rule.get("enabled", True):
                continue
            if not self._rule_matches(rule.get("when") or {}, capability, action, risk, scope, guardian_ctx):
                continue
            rid = str(rule.get("id") or "")
            effect = rule.get("effect") if isinstance(rule.get("effect"), dict) else {}
            decision = str(effect.get("decision") or "annotate")
            matched_rules.append(
                {
                    "id": rid,
                    "decision": decision,
                    "reason": effect.get("reason"),
                    "note": effect.get("note"),
                }
            )
            if decision == "deny" and deny_reason is None:
                deny_reason = str(effect.get("reason") or f"Blocked by Guardian DSL rule {rid}")
            elif decision == "annotate" and effect.get("note"):
                notes.append(str(effect.get("note")))

        effective_deny = deny_reason if mode == "enforce" else None
        return {
            "enabled": True,
            "mode": mode,
            "matched_rules": matched_rules,
            "decision": "deny" if effective_deny else None,
            "deny_reason": effective_deny,
            "notes": notes,
        }

    def _rule_matches(
        self,
        when: Dict[str, Any],
        capability: str,
        action: str,
        risk: str,
        scope: Dict[str, Any],
        guardian_ctx: Dict[str, Any],
    ) -> bool:
        capability = str(capability or "").lower()
        action = str(action or "").lower()
        risk = str(risk or "").lower()

        if not isinstance(when, dict):
            return False

        if "capabilities_any" in when:
            vals = {str(x).lower() for x in (when.get("capabilities_any") or [])}
            if vals and capability not in vals:
                return False

        if "actions_any" in when:
            vals = {str(x).lower() for x in (when.get("actions_any") or [])}
            if vals and action not in vals:
                return False

        risk_at_least = str(when.get("risk_at_least") or "").lower()
        if risk_at_least:
            if RISK_ORDER.get(risk, 0) < RISK_ORDER.get(risk_at_least, 0):
                return False

        exec_tokens = " ".join(self._scope_exec_tokens(scope, action)).lower()
        reason_text = str(scope.get("reason") or "").lower()
        if "reason_tokens_any" in when:
            vals = [str(x).lower() for x in (when.get("reason_tokens_any") or [])]
            if vals and not any(v in reason_text for v in vals):
                return False
        if "reason_tokens_none" in when:
            vals = [str(x).lower() for x in (when.get("reason_tokens_none") or [])]
            if vals and any(v in reason_text for v in vals):
                return False
        if "exec_tokens_any" in when:
            vals = [str(x).lower() for x in (when.get("exec_tokens_any") or [])]
            if vals and not any(v in exec_tokens for v in vals):
                return False
        if "exec_tokens_none" in when:
            vals = [str(x).lower() for x in (when.get("exec_tokens_none") or [])]
            if vals and any(v in exec_tokens for v in vals):
                return False

        if "scope_field_any" in when:
            sf = when.get("scope_field_any") or {}
            if not isinstance(sf, dict):
                return False
            for key, allowed in sf.items():
                allowed_set = {str(x).lower() for x in (allowed or [])}
                val = str(scope.get(str(key), "")).lower()
                if allowed_set and val not in allowed_set:
                    return False

        if "governance_profiles_any" in when:
            vals = {str(x).lower() for x in (when.get("governance_profiles_any") or [])}
            present = {str(x).lower() for x in (guardian_ctx.get("governance_profiles") or [])}
            if vals and not (vals & present):
                return False

        if "semantic_conflict_types_any" in when:
            vals = {str(x).lower() for x in (when.get("semantic_conflict_types_any") or [])}
            present = {str(x).lower() for x in (guardian_ctx.get("semantic_conflict_types") or [])}
            if vals and not (vals & present):
                return False

        return True

    def _scope_exec_tokens(self, scope: Dict[str, Any], action: str) -> List[str]:
        tokens: List[str] = [str(action or "")]
        if not isinstance(scope, dict):
            return tokens
        for key in ("app_path", "root", "workspace", "reason", "path", "target_path", "output_path"):
            val = scope.get(key)
            if isinstance(val, str):
                tokens.append(val)
        for key in ("roots", "strategic_roots", "paths"):
            val = scope.get(key)
            if isinstance(val, list):
                tokens.extend([str(x) for x in val if x is not None])
        for key in ("command", "args"):
            val = scope.get(key)
            if isinstance(val, list):
                tokens.extend([str(x) for x in val if x is not None])
        return tokens

    def _policy_path(self) -> Optional[Path]:
        if getattr(settings, "RTH_DISKLESS", False):
            return None
        candidates = [
            Path("storage") / "guardian",
            Path("storage_runtime") / "guardian",
            Path(tempfile.gettempdir()) / "rth_core" / "guardian",
        ]
        for base in candidates:
            try:
                base.mkdir(parents=True, exist_ok=True)
                probe = base / ".write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return base / "guardian_policy_dsl.json"
            except Exception:
                continue
        return None


guardian_policy_dsl = GuardianPolicyDSL()
