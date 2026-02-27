from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import os
import tempfile
import urllib.request
import urllib.error

from .permissions import permission_gate, Capability, RiskLevel
from .secret_store import secret_store

logger = logging.getLogger(__name__)

TASK_CLASSES = [
    "chat_general", "coding", "planning", "research",
    "summarization", "vision", "verification", "tool_calling",
]
COST_RANK = {"free": 0, "low": 1, "medium": 2, "high": 3, "premium": 4}
LAT_RANK = {"fast": 1, "balanced": 2, "slow": 3}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _s(v: Any) -> str:
    return str(v or "").strip()


def _mask(secret: str) -> str:
    s = _s(secret)
    if not s:
        return ""
    if len(s) <= 8:
        return "*" * len(s)
    return f"{s[:3]}{'*' * max(4, len(s)-7)}{s[-4:]}"


def _uniq(xs: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for x in xs:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


class ModelControlPlane:
    def __init__(self):
        self._state_path_cached: Optional[Path] = None
        self._state_path_meta: Dict[str, Any] = {}
        self._refresh_state_path()
        self.state = self._default_state()
        self._load()

    def status(self) -> Dict[str, Any]:
        prov = self.state.get("providers", {})
        enabled = [p for p in prov.values() if isinstance(p, dict) and p.get("enabled", True)]
        return {
            "module": "model_control_plane",
            "version": 1,
            "state_path": str(self._state_path()) if self._state_path() else None,
            "state_path_source": self._state_path_meta.get("source"),
            "providers_total": len(prov),
            "providers_enabled": len(enabled),
            "catalog_models": self.get_catalog()["count"],
            "routing_policy_version": self.get_routing_policy()["policy"].get("version", 1),
            "secrets_storage_mode": f"secret_store:{secret_store.status().get('mode')}",
            "updated_at": self.state.get("updated_at"),
        }

    def list_providers(self) -> Dict[str, Any]:
        items = [self._sanitize_provider(p) for p in self._providers().values()]
        items.sort(key=lambda x: (not bool(x.get("enabled", True)), x.get("provider_id", "")))
        return {"status": "ok", "count": len(items), "items": items, "presets": self.presets()}

    def upsert_provider(self, payload: Dict[str, Any], reason: str, confirm_owner: bool, decided_by: str) -> Dict[str, Any]:
        src_payload = dict(payload or {})
        api_key_field_present = "api_key" in src_payload
        p, val = self._normalize_provider(payload)
        if not val["ok"]:
            return {"status": "invalid", "validation": val}
        req = permission_gate.propose(
            capability=Capability.FILESYSTEM_WRITE,
            action="models_provider_upsert",
            scope={
                "provider_id": p["provider_id"],
                "provider_type": p["provider_type"],
                "base_url": p.get("base_url"),
                "local_endpoint": bool(p.get("local_endpoint")),
                "model_count": len(p.get("models", [])),
                "target_path": str(self._state_path()) if self._state_path() else None,
            },
            reason=reason,
            risk=RiskLevel.HIGH,
        )
        out: Dict[str, Any] = {"proposal": req.to_dict(), "validation": val}
        if not confirm_owner:
            out["status"] = "proposal_only"
            return out
        dec = permission_gate.approve(req.request_id, decided_by=decided_by)
        out["decision"] = dec.to_dict()
        if dec.decision.value != "approved":
            out["status"] = "denied"
            return out
        prev = self._providers().get(p["provider_id"]) if isinstance(self._providers().get(p["provider_id"]), dict) else None
        secret_name = self._provider_api_key_secret_name(p["provider_id"])
        raw_key = _s(p.pop("api_key", ""))
        if raw_key:
            sres = secret_store.set(secret_name, raw_key, actor=decided_by, reason=f"models_provider_upsert:{p['provider_id']}")
            p["api_key_ref"] = secret_name
            out["api_key_secret"] = {"status": sres.get("status"), "name": secret_name, "backend": sres.get("backend")}
        elif api_key_field_present:
            p.pop("api_key_ref", None)
            if prev and _s(prev.get("api_key_ref")):
                secret_store.delete(_s(prev.get("api_key_ref")), actor=decided_by, reason=f"models_provider_upsert_clear:{p['provider_id']}")
        elif prev:
            if _s(prev.get("api_key_ref")):
                p["api_key_ref"] = _s(prev.get("api_key_ref"))
            elif _s(prev.get("api_key")):
                # legacy inline key fallback (older state versions)
                p["api_key"] = _s(prev.get("api_key"))
        self._providers()[p["provider_id"]] = p
        self.state["updated_at"] = _now()
        self._save()
        out["status"] = "ok"
        out["provider"] = self._sanitize_provider(p)
        return out

    def delete_provider(self, provider_id: str, reason: str, confirm_owner: bool, decided_by: str) -> Dict[str, Any]:
        pid = _s(provider_id).lower()
        cur = self._providers().get(pid)
        if not cur:
            return {"status": "not_found", "provider_id": pid}
        req = permission_gate.propose(
            capability=Capability.FILESYSTEM_WRITE,
            action="models_provider_delete",
            scope={"provider_id": pid, "target_path": str(self._state_path()) if self._state_path() else None},
            reason=reason,
            risk=RiskLevel.HIGH,
        )
        out: Dict[str, Any] = {"proposal": req.to_dict()}
        if not confirm_owner:
            out["status"] = "proposal_only"
            return out
        dec = permission_gate.approve(req.request_id, decided_by=decided_by)
        out["decision"] = dec.to_dict()
        if dec.decision.value != "approved":
            out["status"] = "denied"
            return out
        removed = self._providers().pop(pid, None) or cur
        key_ref = _s((removed or {}).get("api_key_ref"))
        if key_ref:
            secret_store.delete(key_ref, actor=decided_by, reason=f"models_provider_delete:{pid}")
        self._scrub_routes()
        self.state["updated_at"] = _now()
        self._save()
        out["status"] = "ok"
        out["removed"] = self._sanitize_provider(removed)
        return out

    def test_provider(self, provider_id: str = "", payload: Optional[Dict[str, Any]] = None, timeout_sec: float = 2.5) -> Dict[str, Any]:
        if payload is not None:
            p, val = self._normalize_provider(payload)
            if not val["ok"]:
                return {"status": "invalid", "validation": val}
            source = "payload"
        else:
            p = self._providers().get(_s(provider_id).lower())
            if not p:
                return {"status": "not_found", "provider_id": provider_id}
            source = "stored"
        ptype = _s(p.get("provider_type")).lower()
        base = _s(p.get("base_url"))
        urls = []
        if ptype == "ollama":
            urls = [f"{base.rstrip('/')}/api/tags"]
        elif ptype == "llama_cpp":
            urls = [f"{base.rstrip('/')}/models", f"{base.rstrip('/')}/v1/models", base]
        elif ptype == "groq":
            urls = [f"{base.rstrip('/')}/models", base]
        elif base:
            urls = [f"{base.rstrip('/')}/models", base]
        attempts = []
        discovered: List[str] = []
        ok = False
        # Some providers/CDNs (e.g. Groq behind Cloudflare) may reject empty/default urllib user-agents.
        headers = {
            "Accept": "application/json",
            "User-Agent": "RTH-Core/0.1 (+ModelControlPlane)",
        }
        key = self._provider_api_key(p)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        for url in urls:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=float(timeout_sec)) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                    body = json.loads(raw) if raw.strip().startswith(("{", "[")) else {}
                    discovered = self._probe_models(body)
                    attempts.append({"url": url, "ok": True, "status_code": int(getattr(resp, "status", 200)), "discovered_models": discovered})
                    ok = True
                    break
            except urllib.error.HTTPError as e:
                attempts.append({"url": url, "ok": False, "status_code": getattr(e, "code", None), "error": str(e)})
            except Exception as e:
                attempts.append({"url": url, "ok": False, "error": str(e)})
        return {"status": "ok" if ok else "error", "source": source, "provider": self._sanitize_provider(p), "attempts": attempts, "discovered_models": discovered}

    def get_catalog(self) -> Dict[str, Any]:
        items: List[Dict[str, Any]] = []
        for p in self._providers().values():
            if not isinstance(p, dict) or not bool(p.get("enabled", True)):
                continue
            for m in p.get("models", []) or []:
                if not isinstance(m, dict) or not bool(m.get("enabled", True)):
                    continue
                ref = f"{p['provider_id']}:{m['model_id']}"
                item = {
                    "ref": ref,
                    "provider_id": p["provider_id"],
                    "provider_label": p.get("label", p["provider_id"]),
                    "provider_type": p.get("provider_type"),
                    "local_endpoint": bool(p.get("local_endpoint")),
                    "base_url": p.get("base_url"),
                    **m,
                }
                item["cost_tier"] = item.get("cost_tier") if item.get("cost_tier") in COST_RANK else ("free" if item["local_endpoint"] else "medium")
                item["latency_tier"] = item.get("latency_tier") if item.get("latency_tier") in LAT_RANK else "balanced"
                item["task_classes"] = [t for t in (item.get("task_classes") or ["chat_general"]) if t in TASK_CLASSES] or ["chat_general"]
                items.append(item)
        items.sort(key=lambda x: (not x["local_endpoint"], COST_RANK.get(x["cost_tier"], 9), x["ref"]))
        return {"status": "ok", "count": len(items), "items": items, "task_classes": TASK_CLASSES}

    def get_routing_policy(self) -> Dict[str, Any]:
        self.state["routing_policy"] = self._norm_policy(self.state.get("routing_policy") or {})
        return {"status": "ok", "policy": self.state["routing_policy"], "presets": self.presets()}

    def set_routing_policy(self, payload: Dict[str, Any], reason: str, confirm_owner: bool, decided_by: str) -> Dict[str, Any]:
        policy = self._norm_policy(payload or {})
        req = permission_gate.propose(
            capability=Capability.FILESYSTEM_WRITE,
            action="models_routing_policy_set",
            scope={"task_routes": list((policy.get("task_routes") or {}).keys()), "target_path": str(self._state_path()) if self._state_path() else None},
            reason=reason,
            risk=RiskLevel.HIGH,
        )
        out: Dict[str, Any] = {"proposal": req.to_dict(), "policy": policy}
        if not confirm_owner:
            out["status"] = "proposal_only"
            return out
        dec = permission_gate.approve(req.request_id, decided_by=decided_by)
        out["decision"] = dec.to_dict()
        if dec.decision.value != "approved":
            out["status"] = "denied"
            return out
        self.state["routing_policy"] = policy
        self.state["updated_at"] = _now()
        self._save()
        out["status"] = "ok"
        return out

    def apply_preset(self, preset_id: str, reason: str, confirm_owner: bool, decided_by: str) -> Dict[str, Any]:
        preset = _s(preset_id)
        policy = self._preset_policy(preset)
        if not policy:
            return {"status": "invalid_preset", "preset_id": preset}
        out = self.set_routing_policy(policy, f"{reason}: {preset}", confirm_owner, decided_by)
        out["preset_id"] = preset
        return out

    def route_explain(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        task = _s(payload.get("task_class")) or "chat_general"
        if task not in TASK_CLASSES:
            task = "chat_general"
        policy = self.get_routing_policy()["policy"]
        row = dict((policy.get("task_routes") or {}).get(task) or {})
        privacy = _s(payload.get("privacy_mode") or row.get("privacy_mode") or "allow_cloud")
        max_cost = _s(payload.get("max_cost_tier") or row.get("max_cost_tier") or "premium")
        require_vision = bool(payload.get("require_vision", False))
        require_tools = bool(payload.get("require_tools", False))
        diff = _s(payload.get("difficulty") or "normal")
        rlvl = _s(payload.get("reasoning_level") or row.get("reasoning_level") or "balanced")
        prompt = _s(payload.get("prompt") or payload.get("message"))
        tok = int(payload.get("token_estimate") or max(64, int(len(prompt.split()) * 1.5) + 32 if prompt else 256))

        all_models = list(self.get_catalog()["items"])
        candidates, rejected = [], []
        for m in all_models:
            ok, why = self._route_ok(m, task, privacy, max_cost, require_vision, require_tools)
            (candidates if ok else rejected).append(m if ok else {"ref": m["ref"], "reason": why})
        preferred = [x for x in [_s(row.get("primary"))] + [str(v) for v in (row.get("fallbacks") or [])] if x]
        selected = None
        mode = "adaptive_cost_aware"
        for ref in preferred:
            selected = next((m for m in candidates if m["ref"] == ref), None)
            if selected:
                mode = "policy_preferred"
                break
        if not selected and candidates:
            candidates.sort(key=lambda m: self._route_sort_key(m, task, diff, rlvl, privacy))
            selected = candidates[0]
        est = self._estimate_units(selected, tok) if selected else None
        traces = []
        if mode == "policy_preferred":
            traces.append("Selected from routing matrix primary/fallback chain.")
        if diff in {"hard", "expert"} and selected and selected.get("cost_tier") in {"free", "low"}:
            traces.append("Hard task on cheap model: premium escalation may improve quality.")
        return {
            "status": "ok" if selected else "no_match",
            "task_class": task,
            "selected": selected,
            "fallbacks": [m for m in candidates if not selected or m["ref"] != selected["ref"]][:8],
            "route_policy": row,
            "constraints": {"privacy_mode": privacy, "max_cost_tier": max_cost, "difficulty": diff, "reasoning_level": rlvl, "require_vision": require_vision, "require_tools": require_tools},
            "selection_mode": mode,
            "budget_estimate": {"token_estimate": tok, "unit_cost_estimate": est, "policy_budget_defaults": (policy.get("budget_defaults") or {})},
            "trace": {"catalog_count": len(all_models), "candidates_count": len(candidates), "preferred_chain": preferred, "rejected_samples": rejected[:12], "reasons": traces},
            "timestamp": _now(),
        }

    def chat_simulate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        route = self.route_explain(payload)
        sel = route.get("selected") or {}
        label = sel.get("label") or sel.get("ref") or "no-model"
        msg = "Nessun modello disponibile. Configura provider/modelli." if route["status"] != "ok" else f"[Simulazione] Instradato a `{label}` con modalità `{route['selection_mode']}`. Endpoint v0 non esegue ancora la LLM reale."
        return {"status": "ok", "mode": "simulation_only", "assistant_preview": msg, "route": route, "timestamp": _now()}

    def chat_execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        route = self.route_explain(payload)
        if route.get("status") != "ok":
            return {
                "status": "no_match",
                "mode": "live_execution",
                "assistant_preview": "Nessun modello disponibile per i vincoli richiesti.",
                "route": route,
                "timestamp": _now(),
            }
        allow_fallbacks = bool(payload.get("allow_fallbacks", True))
        candidates: List[Dict[str, Any]] = []
        if isinstance(route.get("selected"), dict):
            candidates.append(route["selected"])
        if allow_fallbacks:
            candidates.extend([m for m in (route.get("fallbacks") or []) if isinstance(m, dict)])
        attempts: List[Dict[str, Any]] = []
        confirm_owner = bool(payload.get("confirm_owner", True))
        decided_by = _s(payload.get("decided_by") or "owner")
        for model in candidates[:6]:
            prov_id = _s(model.get("provider_id"))
            provider = self._providers().get(prov_id)
            if not isinstance(provider, dict):
                attempts.append({"ref": model.get("ref"), "ok": False, "error": "provider_not_found"})
                continue
            req = permission_gate.propose(
                capability=Capability.NETWORK_ACCESS,
                action="models_chat_execute",
                scope={
                    "provider_id": prov_id,
                    "provider_type": provider.get("provider_type"),
                    "model_id": model.get("model_id"),
                    "base_url": provider.get("base_url"),
                    "local_endpoint": bool(provider.get("local_endpoint")),
                    "task_class": route.get("task_class"),
                },
                reason=_s(payload.get("reason") or f"Execute live chat on {prov_id}:{_s(model.get('model_id'))}") or "Execute live model chat",
                risk=RiskLevel.LOW if bool(provider.get("local_endpoint")) else RiskLevel.MEDIUM,
            )
            if not confirm_owner:
                return {
                    "status": "proposal_only",
                    "mode": "live_execution",
                    "route": route,
                    "selected_attempt": model,
                    "proposal": req.to_dict(),
                    "timestamp": _now(),
                }
            dec = permission_gate.approve(req.request_id, decided_by=decided_by)
            if dec.decision.value != "approved":
                attempts.append({"ref": model.get("ref"), "ok": False, "error": "permission_denied", "decision": dec.to_dict()})
                continue
            call = self._execute_model_chat(provider, model, payload)
            attempts.append({"ref": model.get("ref"), **{k: v for k, v in call.items() if k not in {"assistant_message"}}})
            if call.get("ok"):
                return {
                    "status": "ok",
                    "mode": "live_execution",
                    "assistant_message": call.get("assistant_message", ""),
                    "assistant_preview": (call.get("assistant_message", "") or "")[:500],
                    "route": route,
                    "selected_model": model,
                    "provider": self._sanitize_provider(provider),
                    "execution": call,
                    "attempts": attempts,
                    "timestamp": _now(),
                }
        return {
            "status": "error",
            "mode": "live_execution",
            "assistant_preview": "Esecuzione live fallita su tutti i modelli candidati.",
            "route": route,
            "attempts": attempts,
            "timestamp": _now(),
        }

    def village_plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        roles = [str(x).strip() for x in (payload.get("roles") or []) if str(x).strip()] or ["researcher", "coder", "critic", "verifier", "strategist", "synthesizer"]
        prompt = _s(payload.get("prompt"))
        privacy = _s(payload.get("privacy_mode") or "allow_cloud")
        budget_cap = float(payload.get("budget_cap") or 10.0)
        role_map = {"researcher": "research", "coder": "coding", "critic": "verification", "verifier": "verification", "strategist": "planning", "synthesizer": "summarization"}
        rows, total = [], 0.0
        for role in roles:
            task = role_map.get(role, "chat_general")
            route = self.route_explain({"task_class": task, "prompt": prompt, "privacy_mode": privacy, "difficulty": "hard" if role in {"critic", "verifier", "strategist"} else "normal"})
            cost = float(((route.get("budget_estimate") or {}).get("unit_cost_estimate")) or 0.0)
            total += cost
            rows.append({"role": role, "task_class": task, "route_status": route.get("status"), "selected": route.get("selected"), "fallbacks": (route.get("fallbacks") or [])[:3], "cost_estimate_units": round(cost, 3), "route_trace": route.get("trace")})
        return {"status": "ok", "mode": "planning_only", "roles_count": len(rows), "roles": rows, "totals": {"estimated_cost_units": round(total, 3), "budget_cap": budget_cap, "budget_ok": total <= budget_cap}, "timestamp": _now()}

    def village_run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = _s(payload.get("prompt"))
        if not prompt:
            return {"status": "invalid", "error": "prompt_required"}
        mode = _s(payload.get("mode") or "brainstorm") or "brainstorm"
        privacy = _s(payload.get("privacy_mode") or "allow_cloud") or "allow_cloud"
        confirm_owner = bool(payload.get("confirm_owner", True))
        decided_by = _s(payload.get("decided_by") or "owner")
        allow_budget_overrun = bool(payload.get("allow_budget_overrun", True))
        role_max_tokens = max(120, min(int(payload.get("role_max_tokens") or 700), 2000))
        synthesis_max_tokens = max(180, min(int(payload.get("synthesis_max_tokens") or 1000), 3000))
        timeout_sec = max(5.0, min(float(payload.get("timeout_sec") or 120.0), 600.0))
        per_role_timeout = max(5.0, min(float(payload.get("per_role_timeout_sec") or min(90.0, timeout_sec)), 180.0))
        max_roles = max(1, min(int(payload.get("max_roles") or 8), 12))

        plan = self.village_plan(payload)
        budget = dict(plan.get("totals") or {})
        budget_ok = bool(budget.get("budget_ok"))
        if (not budget_ok) and (not allow_budget_overrun):
            return {
                "status": "budget_exceeded",
                "mode": "live_village",
                "plan": plan,
                "budget_policy": {"allow_budget_overrun": False},
                "timestamp": _now(),
            }

        role_rows = [r for r in (plan.get("roles") or []) if isinstance(r, dict)][:max_roles]
        synthesis_requested = any(_s(r.get("role")).lower() == "synthesizer" for r in role_rows) or bool(payload.get("force_synthesis", True))
        work_rows = [r for r in role_rows if _s(r.get("role")).lower() != "synthesizer"]
        if not work_rows:
            work_rows = role_rows[:]

        results: List[Dict[str, Any]] = []
        for row in work_rows:
            role = _s(row.get("role")) or "specialist"
            task_class = _s(row.get("task_class") or "chat_general") or "chat_general"
            role_prompt = self._village_role_instruction(role, mode)
            run = self.chat_execute(
                {
                    "message": prompt,
                    "task_class": task_class,
                    "privacy_mode": privacy,
                    "difficulty": "hard" if role in {"critic", "verifier", "strategist"} else "normal",
                    "system_prompt": role_prompt,
                    "max_tokens": role_max_tokens,
                    "timeout_sec": per_role_timeout,
                    "allow_fallbacks": True,
                    "confirm_owner": confirm_owner,
                    "decided_by": decided_by,
                    "reason": _s(payload.get("reason") or f"AI Village role execution: {role}") or f"AI Village role execution: {role}",
                }
            )
            results.append(
                {
                    "role": role,
                    "task_class": task_class,
                    "plan_route": {"selected": row.get("selected"), "fallbacks": row.get("fallbacks"), "route_status": row.get("route_status")},
                    "status": run.get("status"),
                    "assistant_message": run.get("assistant_message", ""),
                    "assistant_preview": _s(run.get("assistant_message") or run.get("assistant_preview"))[:600],
                    "selected_model": run.get("selected_model") or ((run.get("route") or {}).get("selected") if isinstance(run.get("route"), dict) else None),
                    "attempts": run.get("attempts") or [],
                    "error": run.get("error"),
                    "timestamp": run.get("timestamp"),
                }
            )

        ok_roles = [r for r in results if r.get("status") == "ok" and _s(r.get("assistant_message"))]
        failed_roles = [r for r in results if r not in ok_roles]

        synthesis: Dict[str, Any] = {"status": "skipped", "reason": "not_requested" if not synthesis_requested else "no_role_outputs"}
        if synthesis_requested and ok_roles:
            synthesis_user = self._village_synthesis_prompt(prompt, mode, ok_roles)
            synthesis_run = self.chat_execute(
                {
                    "message": "Synthesize AI Village outputs",
                    "task_class": "summarization",
                    "privacy_mode": privacy,
                    "difficulty": "expert",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are the AI Village synthesizer for Core Rth. "
                                "Merge specialist outputs, preserve disagreements, surface risks, and end with a concrete action plan."
                            ),
                        },
                        {"role": "user", "content": synthesis_user},
                    ],
                    "max_tokens": synthesis_max_tokens,
                    "timeout_sec": min(timeout_sec, 180.0),
                    "allow_fallbacks": True,
                    "confirm_owner": confirm_owner,
                    "decided_by": decided_by,
                    "reason": _s(payload.get("reason") or "AI Village synthesis execution"),
                }
            )
            synthesis = {
                "status": synthesis_run.get("status"),
                "assistant_message": synthesis_run.get("assistant_message", ""),
                "assistant_preview": _s(synthesis_run.get("assistant_message") or synthesis_run.get("assistant_preview"))[:900],
                "selected_model": synthesis_run.get("selected_model") or ((synthesis_run.get("route") or {}).get("selected") if isinstance(synthesis_run.get("route"), dict) else None),
                "attempts": synthesis_run.get("attempts") or [],
                "timestamp": synthesis_run.get("timestamp"),
            }

        if synthesis.get("status") != "ok" and ok_roles:
            # Deterministic fallback summary if synthesis model is unavailable.
            merged = []
            for r in ok_roles[:8]:
                merged.append(f"[{r['role']}] {(_s(r.get('assistant_message')) or _s(r.get('assistant_preview')))[:600]}")
            synthesis["fallback_compilation"] = "\n\n".join(merged)

        return {
            "status": "ok" if ok_roles else "error",
            "mode": "live_village",
            "village_mode": mode,
            "prompt": prompt,
            "plan": plan,
            "budget_policy": {
                "allow_budget_overrun": allow_budget_overrun,
                "budget_ok": budget_ok,
                "estimated_cost_units": budget.get("estimated_cost_units"),
                "budget_cap": budget.get("budget_cap"),
            },
            "roles_executed": len(results),
            "roles_ok": len(ok_roles),
            "roles_failed": len(failed_roles),
            "role_results": results,
            "synthesis": synthesis,
            "timestamp": _now(),
        }

    def reload_state(self, reselect_path: bool = False) -> Dict[str, Any]:
        if reselect_path:
            self._refresh_state_path()
        self.state = self._default_state()
        loaded = self._load()
        return {
            "status": "ok",
            "reloaded": True,
            "loaded_from_disk": bool(loaded),
            "state_path": str(self._state_path()) if self._state_path() else None,
            "state_path_source": self._state_path_meta.get("source"),
            "providers_total": len(self._providers()),
            "catalog_models": self.get_catalog()["count"],
            "updated_at": self.state.get("updated_at"),
            "timestamp": _now(),
        }

    def presets(self) -> List[Dict[str, Any]]:
        return [
            {"preset_id": "premium", "label": "Premium"},
            {"preset_id": "golden", "label": "Golden"},
            {"preset_id": "local", "label": "Local"},
            {"preset_id": "low_cost", "label": "Low Cost"},
            {"preset_id": "hybrid_balanced", "label": "Hybrid Balanced"},
            {"preset_id": "groq_low_cost", "label": "Groq Low Cost"},
            {"preset_id": "groq_reasoning", "label": "Groq Reasoning"},
            {"preset_id": "groq_multimodal", "label": "Groq Multimodal"},
        ]

    # internals
    def _state_path(self) -> Optional[Path]:
        return self._state_path_cached

    def _refresh_state_path(self) -> None:
        self._state_path_cached, self._state_path_meta = self._resolve_state_path()

    def _resolve_state_path(self) -> tuple[Optional[Path], Dict[str, Any]]:
        env_names = ["RTH_MODEL_CONTROL_PLANE_BASE", "RTH_MODELS_BASE"]
        candidates: List[tuple[Path, str]] = []
        for env_name in env_names:
            raw = os.getenv(env_name, "").strip()
            if not raw:
                continue
            expanded = Path(os.path.expandvars(os.path.expanduser(raw)))
            if expanded.suffix.lower() == ".json":
                candidates.append((expanded, f"env:{env_name}"))
            else:
                candidates.append((expanded / "model_control_plane.json", f"env:{env_name}"))
            break
        if not candidates:
            candidates = [
                (Path("storage") / "models" / "model_control_plane.json", "auto:storage"),
                (Path("storage_runtime") / "models" / "model_control_plane.json", "auto:storage_runtime"),
                (Path(tempfile.gettempdir()) / "rth_core" / "models" / "model_control_plane.json", "auto:temp"),
            ]
        for path, source in candidates:
            try:
                base = path.parent
                base.mkdir(parents=True, exist_ok=True)
                p = base / ".write_probe"
                p.write_text("ok", encoding="utf-8")
                p.unlink(missing_ok=True)
                return path, {"source": source, "base": str(base)}
            except Exception:
                continue
        return None, {"source": "unavailable"}

    def _default_state(self) -> Dict[str, Any]:
        return {"version": 1, "updated_at": _now(), "providers": {}, "routing_policy": self._norm_policy({})}

    def _providers(self) -> Dict[str, Dict[str, Any]]:
        if not isinstance(self.state.get("providers"), dict):
            self.state["providers"] = {}
        return self.state["providers"]

    def _execute_model_chat(self, provider: Dict[str, Any], model: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        ptype = _s(provider.get("provider_type")).lower()
        base = _s(provider.get("base_url"))
        api_key = self._provider_api_key(provider)
        model_id = _s(model.get("model_id"))
        if not model_id:
            return {"ok": False, "error": "missing_model_id"}
        messages = self._chat_messages_from_payload(payload)
        timeout_sec = max(1.0, min(float(payload.get("timeout_sec") or 60.0), 300.0))
        max_tokens = int(payload.get("max_tokens") or payload.get("max_completion_tokens") or 800)
        temperature = float(payload.get("temperature") or 0.2)
        if ptype == "ollama":
            return self._invoke_ollama_chat(base, model_id, messages, timeout_sec=timeout_sec, temperature=temperature)
        if ptype in {"groq", "openai", "openrouter", "openai_compat", "llama_cpp", "lmstudio", "vllm"}:
            return self._invoke_openai_compat_chat(
                base=base,
                model_id=model_id,
                messages=messages,
                timeout_sec=timeout_sec,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                provider_type=ptype,
            )
        return {"ok": False, "error": f"unsupported_provider_type:{ptype}", "provider_type": ptype}

    def _chat_messages_from_payload(self, payload: Dict[str, Any]) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        system_prompt = _s(payload.get("system_prompt"))
        if system_prompt:
            out.append({"role": "system", "content": system_prompt})
        raw_messages = payload.get("messages")
        if isinstance(raw_messages, list):
            for row in raw_messages[:40]:
                if not isinstance(row, dict):
                    continue
                role = _s(row.get("role") or "user").lower()
                if role not in {"system", "user", "assistant", "tool"}:
                    role = "user"
                content = row.get("content")
                if isinstance(content, list):
                    parts = []
                    for block in content[:20]:
                        if isinstance(block, dict) and _s(block.get("type")) in {"text", "input_text", "output_text"}:
                            parts.append(_s(block.get("text") or block.get("content")))
                    content = "\n".join([x for x in parts if x])
                text = _s(content)
                if text:
                    out.append({"role": role, "content": text})
        if not out or out[-1].get("role") != "user":
            user_msg = _s(payload.get("message") or payload.get("prompt"))
            if user_msg:
                out.append({"role": "user", "content": user_msg})
        if not out:
            out.append({"role": "user", "content": "Hello"})
        return out

    def _invoke_openai_compat_chat(
        self,
        *,
        base: str,
        model_id: str,
        messages: List[Dict[str, str]],
        timeout_sec: float,
        api_key: str,
        temperature: float,
        max_tokens: int,
        provider_type: str,
    ) -> Dict[str, Any]:
        if not base:
            return {"ok": False, "error": "missing_base_url"}
        url = base.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"
        req_body: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens > 0:
            req_body["max_tokens"] = max_tokens
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "RTH-Core/0.1 (+ModelControlPlaneChat)",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            req = urllib.request.Request(url, data=json.dumps(req_body).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                body = json.loads(raw) if raw.strip() else {}
                assistant = self._extract_openai_compat_message(body)
                return {
                    "ok": True,
                    "provider_type": provider_type,
                    "url": url,
                    "status_code": int(getattr(resp, "status", 200)),
                    "assistant_message": assistant,
                    "usage": (body.get("usage") if isinstance(body, dict) else None),
                    "response_id": _s(body.get("id")) if isinstance(body, dict) else "",
                    "model_response": _s(body.get("model")) if isinstance(body, dict) else "",
                    "raw_preview": raw[:800],
                }
        except urllib.error.HTTPError as e:
            body_preview = ""
            try:
                body_preview = e.read().decode("utf-8", errors="replace")[:1200]
            except Exception:
                body_preview = ""
            return {"ok": False, "provider_type": provider_type, "url": url, "status_code": getattr(e, "code", None), "error": str(e), "error_body_preview": body_preview}
        except Exception as e:
            return {"ok": False, "provider_type": provider_type, "url": url, "error": str(e)}

    def _extract_openai_compat_message(self, body: Any) -> str:
        if not isinstance(body, dict):
            return ""
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0] if isinstance(choices[0], dict) else {}
        msg = first.get("message") if isinstance(first, dict) else {}
        if not isinstance(msg, dict):
            return ""
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for row in content[:50]:
                if not isinstance(row, dict):
                    continue
                text = _s(row.get("text") or row.get("content"))
                if text:
                    parts.append(text)
            return "\n".join(parts)
        return _s(content)

    def _invoke_ollama_chat(self, base: str, model_id: str, messages: List[Dict[str, str]], *, timeout_sec: float, temperature: float) -> Dict[str, Any]:
        if not base:
            return {"ok": False, "error": "missing_base_url"}
        url = f"{base.rstrip('/')}/api/chat"
        req_body = {"model": model_id, "messages": messages, "stream": False, "options": {"temperature": temperature}}
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "RTH-Core/0.1 (+ModelControlPlaneChat)",
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(req_body).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                body = json.loads(raw) if raw.strip() else {}
                msg = body.get("message") if isinstance(body, dict) else {}
                assistant = _s(msg.get("content")) if isinstance(msg, dict) else ""
                return {
                    "ok": True,
                    "provider_type": "ollama",
                    "url": url,
                    "status_code": int(getattr(resp, "status", 200)),
                    "assistant_message": assistant,
                    "usage": {
                        "prompt_eval_count": body.get("prompt_eval_count"),
                        "eval_count": body.get("eval_count"),
                    } if isinstance(body, dict) else None,
                    "model_response": _s(body.get("model")) if isinstance(body, dict) else "",
                    "raw_preview": raw[:800],
                }
        except urllib.error.HTTPError as e:
            body_preview = ""
            try:
                body_preview = e.read().decode("utf-8", errors="replace")[:1200]
            except Exception:
                body_preview = ""
            return {"ok": False, "provider_type": "ollama", "url": url, "status_code": getattr(e, "code", None), "error": str(e), "error_body_preview": body_preview}
        except Exception as e:
            return {"ok": False, "provider_type": "ollama", "url": url, "error": str(e)}

    def _load(self) -> bool:
        path = self._state_path()
        if not path or not path.exists():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self.state.update(payload)
                self.state["routing_policy"] = self._norm_policy(self.state.get("routing_policy") or {})
                return True
        except Exception as e:
            logger.warning(f"Model control plane load failed: {e}")
        return False

    def _save(self) -> None:
        path = self._state_path()
        if not path:
            return
        try:
            path.write_text(json.dumps(self.state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception as e:
            logger.warning(f"Model control plane save failed: {e}")

    def _sanitize_provider(self, p: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(p or {})
        key = self._provider_api_key(d)
        d.pop("api_key", None)
        d["api_key_ref"] = _s(d.get("api_key_ref"))
        d["has_api_key"] = bool(key)
        d["api_key_masked"] = _mask(key) if key else (secret_store.masked(d.get("api_key_ref")) if d.get("api_key_ref") else "")
        return d

    def _normalize_provider(self, payload: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        errs, warns = [], []
        p = dict(payload or {})
        pid = _s(p.get("provider_id") or p.get("id")).lower().replace(" ", "_")
        if not pid:
            errs.append("provider_id required")
        ptype = _s(p.get("provider_type") or "openai").lower()
        local = bool(p.get("local_endpoint", ptype in {"ollama", "lmstudio", "vllm", "openai_compat", "llama_cpp"}))
        base = _s(p.get("base_url"))
        if not base and ptype == "ollama":
            base = "http://127.0.0.1:11434"
        if not base and ptype == "lmstudio":
            base = "http://127.0.0.1:1234/v1"
        if not base and ptype == "vllm":
            base = "http://127.0.0.1:8001/v1"
        if not base and ptype == "llama_cpp":
            base = "http://127.0.0.1:8080/v1"
        if not base and ptype == "groq":
            base = "https://api.groq.com/openai/v1"
        api_key = _s(p.get("api_key"))
        raw_models = p.get("models") or []
        if isinstance(raw_models, str):
            raw_models = [x.strip() for x in raw_models.replace(",", "\n").splitlines() if x.strip()]
        models = []
        for i, row in enumerate(raw_models):
            if isinstance(row, str):
                models.append(self._default_model(_s(row), local))
            elif isinstance(row, dict):
                mid = _s(row.get("model_id") or row.get("id") or row.get("name"))
                if not mid:
                    errs.append(f"models[{i}].model_id required")
                    continue
                m = self._default_model(mid, local)
                for k in ("label", "cost_tier", "latency_tier", "notes"):
                    if k in row:
                        m[k] = row[k]
                m["enabled"] = bool(row.get("enabled", True))
                m["strengths"] = _uniq([str(x).strip().lower() for x in (row.get("strengths") or m["strengths"]) if str(x).strip()])
                m["task_classes"] = [t for t in _uniq([str(x).strip() for x in (row.get("task_classes") or m["task_classes"]) if str(x).strip()]) if t in TASK_CLASSES] or ["chat_general"]
                m["supports_vision"] = bool(row.get("supports_vision", m.get("supports_vision", False)))
                m["supports_tools"] = bool(row.get("supports_tools", m.get("supports_tools", True)))
                m["supports_reasoning"] = bool(row.get("supports_reasoning", m.get("supports_reasoning", True)))
                m["context_tokens"] = int(row.get("context_tokens") or 0)
                m["tags"] = _uniq([str(x).strip().lower() for x in (row.get("tags") or []) if str(x).strip()])
                models.append(m)
            else:
                errs.append(f"models[{i}] invalid")
        if ptype == "groq":
            for m in models:
                low = str(m.get("model_id", "")).lower()
                if str(m.get("cost_tier")) == "medium":
                    m["cost_tier"] = "low" if any(k in low for k in ["20b", "mini", "scout", "whisper", "tts"]) else "medium"
                tags = set(str(x) for x in (m.get("tags") or []))
                tags.add("groq")
                if any(k in low for k in ["whisper"]):
                    tags.add("stt")
                    m["supports_tools"] = False
                if any(k in low for k in ["orpheus", "tts"]):
                    tags.add("tts")
                    m["supports_tools"] = False
                if any(k in low for k in ["vision", "scout"]):
                    m["supports_vision"] = True
                if any(k in low for k in ["reason", "oss", "qwen", "kimi"]):
                    m["supports_reasoning"] = True
                task_classes = set(str(x) for x in (m.get("task_classes") or []))
                if m.get("supports_reasoning"):
                    task_classes.update({"planning", "research", "verification"})
                if m.get("supports_tools", True):
                    task_classes.add("tool_calling")
                if m.get("supports_vision"):
                    task_classes.add("vision")
                if any(k in low for k in ["coder", "code", "qwen"]):
                    task_classes.add("coding")
                if any(k in low for k in ["whisper", "tts", "orpheus"]):
                    # audio/STT/TTS endpoints are not general chat routes in current router v0
                    task_classes = set([t for t in task_classes if t in {"chat_general", "summarization"}])
                m["task_classes"] = [t for t in _uniq(task_classes) if t in TASK_CLASSES] or ["chat_general"]
                m["tags"] = _uniq(sorted(tags))
        if not models:
            warns.append("no models configured")
        return ({
            "provider_id": pid, "label": _s(p.get("label")) or pid, "provider_type": ptype, "enabled": bool(p.get("enabled", True)),
            "local_endpoint": local, "base_url": base, "api_key": api_key, "notes": _s(p.get("notes")), "models": models, "updated_at": _now()
        }, {"ok": not errs, "errors": errs, "warnings": warns})

    def _provider_api_key_secret_name(self, provider_id: str) -> str:
        return f"models/providers/{_s(provider_id).lower()}/api_key"

    def _provider_api_key(self, provider: Dict[str, Any]) -> str:
        p = provider if isinstance(provider, dict) else {}
        inline = _s(p.get("api_key"))
        if inline:
            return inline
        ref = _s(p.get("api_key_ref"))
        if ref:
            return secret_store.get(ref, default="")
        pid = _s(p.get("provider_id"))
        if pid:
            return secret_store.get(self._provider_api_key_secret_name(pid), default="")
        return ""

    def _default_model(self, model_id: str, local: bool) -> Dict[str, Any]:
        low = model_id.lower()
        strengths = []
        if any(k in low for k in ["code", "coder"]):
            strengths.append("coding")
        if any(k in low for k in ["reason", "thinking", "o3", "o1", "r1"]):
            strengths.append("reasoning")
        if any(k in low for k in ["vision", "omni", "vl"]):
            strengths.append("vision")
        if not strengths:
            strengths.append("general")
        tasks = ["chat_general", "summarization"]
        if "coding" in strengths:
            tasks += ["coding", "tool_calling", "verification"]
        if "reasoning" in strengths:
            tasks += ["planning", "research", "verification"]
        if "vision" in strengths:
            tasks += ["vision"]
        cost = "free" if local else ("low" if any(k in low for k in ["mini", "flash"]) else "medium")
        if not local and any(k in low for k in ["gpt-5", "opus", "ultra", "pro"]):
            cost = "premium"
        return {"model_id": model_id, "label": model_id, "enabled": True, "cost_tier": cost, "latency_tier": "balanced", "strengths": _uniq(strengths), "task_classes": [t for t in _uniq(tasks) if t in TASK_CLASSES], "supports_vision": "vision" in strengths, "supports_tools": True, "supports_reasoning": True, "context_tokens": 0, "tags": [], "notes": ""}

    def _probe_models(self, body: Any) -> List[str]:
        out = []
        if isinstance(body, dict):
            for row in body.get("data", []) or []:
                if isinstance(row, dict) and _s(row.get("id")):
                    out.append(_s(row.get("id")))
            for row in body.get("models", []) or []:
                if isinstance(row, str):
                    out.append(_s(row))
                elif isinstance(row, dict):
                    out.append(_s(row.get("name") or row.get("id")))
        return [x for x in _uniq([x for x in out if x]) if x]

    def _norm_policy(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        p = dict(payload or {})
        base = {
            "version": 1,
            "updated_at": _now(),
            "active_preset": _s(p.get("active_preset") or "hybrid_balanced"),
            "task_routes": {},
            "budget_defaults": {"single_task_unit_cap": 2.0, "village_unit_cap": 10.0},
            "village_profiles": {"brainstorm": ["researcher", "coder", "critic", "synthesizer"]},
        }
        tr = p.get("task_routes") if isinstance(p.get("task_routes"), dict) else {}
        for task in TASK_CLASSES:
            row = tr.get(task) if isinstance(tr.get(task), dict) else {}
            base["task_routes"][task] = {
                "primary": _s(row.get("primary")) or None,
                "fallbacks": _uniq([str(x).strip() for x in (row.get("fallbacks") or []) if str(x).strip()]),
                "privacy_mode": _s(row.get("privacy_mode") or "allow_cloud"),
                "reasoning_level": _s(row.get("reasoning_level") or "balanced"),
                "max_cost_tier": _s(row.get("max_cost_tier") or "premium") if _s(row.get("max_cost_tier") or "premium") in COST_RANK else "premium",
                "max_latency_tier": _s(row.get("max_latency_tier") or "slow") if _s(row.get("max_latency_tier") or "slow") in LAT_RANK else "slow",
            }
        bd = p.get("budget_defaults") if isinstance(p.get("budget_defaults"), dict) else {}
        for k in ("single_task_unit_cap", "village_unit_cap"):
            try:
                base["budget_defaults"][k] = float(bd.get(k, base["budget_defaults"][k]))
            except Exception:
                pass
        vp = p.get("village_profiles") if isinstance(p.get("village_profiles"), dict) else {}
        for k, v in vp.items():
            if isinstance(v, list):
                base["village_profiles"][str(k)] = _uniq([str(x).strip() for x in v if str(x).strip()])
        return base

    def _preset_policy(self, preset: str) -> Optional[Dict[str, Any]]:
        preset = _s(preset).lower()
        if preset not in {"premium", "golden", "local", "low_cost", "hybrid_balanced", "groq_low_cost", "groq_reasoning", "groq_multimodal"}:
            return None
        pol = self._norm_policy({"active_preset": preset})
        cat = list(self.get_catalog()["items"])
        for task in TASK_CLASSES:
            cands = [m for m in cat if task in (m.get("task_classes") or [])]
            if preset == "local":
                cands = [m for m in cands if m.get("local_endpoint")]
            cands.sort(key=lambda m: self._preset_sort_key(m, task, preset))
            if cands:
                pol["task_routes"][task]["primary"] = cands[0]["ref"]
                pol["task_routes"][task]["fallbacks"] = [m["ref"] for m in cands[1:4]]
            if preset == "local":
                privacy_mode = "local_only"
            elif preset == "hybrid_balanced":
                privacy_mode = "local_preferred"
            else:
                privacy_mode = "allow_cloud"
            if preset in {"low_cost", "groq_low_cost"}:
                max_cost = "low"
            elif preset in {"golden", "hybrid_balanced", "groq_reasoning", "groq_multimodal"}:
                max_cost = "high"
            else:
                max_cost = "premium"
            if preset in {"groq_reasoning"} and task in {"planning", "research", "verification", "tool_calling"}:
                reasoning_level = "deep"
            elif task in {"planning", "research", "verification"} and preset in {"premium", "golden"}:
                reasoning_level = "deep"
            elif preset in {"low_cost", "groq_low_cost"}:
                reasoning_level = "cheap"
            else:
                reasoning_level = "balanced"
            pol["task_routes"][task]["privacy_mode"] = privacy_mode
            pol["task_routes"][task]["max_cost_tier"] = max_cost
            pol["task_routes"][task]["reasoning_level"] = reasoning_level
            if preset == "groq_multimodal" and task == "vision":
                pol["task_routes"][task]["max_latency_tier"] = "slow"
            if preset == "groq_low_cost":
                pol["task_routes"][task]["max_latency_tier"] = "balanced"
        return pol

    def _preset_sort_key(self, m: Dict[str, Any], task: str, preset: str):
        cost = COST_RANK.get(str(m.get("cost_tier")), 9)
        lat = LAT_RANK.get(str(m.get("latency_tier")), 9)
        strengths = set(str(x) for x in (m.get("strengths") or []))
        tags = set(str(x) for x in (m.get("tags") or []))
        local = bool(m.get("local_endpoint"))
        is_groq = str(m.get("provider_type") or "").lower() == "groq" or "groq" in tags
        task_fit = 0
        if task == "coding" and "coding" in strengths:
            task_fit -= 2
        if task in {"planning", "research", "verification"} and "reasoning" in strengths:
            task_fit -= 2
        if task == "vision" and m.get("supports_vision"):
            task_fit -= 3
        if preset == "groq_low_cost":
            return (0 if is_groq else 1, cost, lat, 0 if local else 1, task_fit)
        if preset == "groq_reasoning":
            reason_pen = 0 if ("reasoning" in strengths or bool(m.get("supports_reasoning"))) else 1
            tools_pen = 0 if bool(m.get("supports_tools", True)) else 1
            return (0 if is_groq else 1, reason_pen, cost, task_fit, tools_pen, lat)
        if preset == "groq_multimodal":
            vision_pen = 0 if bool(m.get("supports_vision")) else 1
            speech_bonus = -1 if any(t in tags for t in {"stt", "tts"}) else 0
            return (0 if is_groq else 1, vision_pen, cost + speech_bonus, task_fit, lat)
        if preset == "premium":
            return (0 if not local else 1, -cost, task_fit, lat)
        if preset == "golden":
            return (0 if not local else 1, abs(cost - COST_RANK["high"]), task_fit, lat)
        if preset == "low_cost":
            return (cost, lat, 0 if local else 1, task_fit)
        if preset == "hybrid_balanced":
            return (0 if local else 1, cost, task_fit, lat)
        return (0 if local else 1, cost, task_fit, lat)

    def _route_ok(self, m: Dict[str, Any], task: str, privacy: str, max_cost: str, require_vision: bool, require_tools: bool):
        if privacy in {"local_only", "local_preferred"} and privacy == "local_only" and not m.get("local_endpoint"):
            return False, "privacy_local_only"
        if COST_RANK.get(str(m.get("cost_tier")), 9) > COST_RANK.get(max_cost, 9):
            return False, "cost_tier_exceeds"
        if require_vision and not m.get("supports_vision"):
            return False, "vision_required"
        if require_tools and not m.get("supports_tools", True):
            return False, "tools_required"
        task_classes = (m.get("task_classes") or ["chat_general"])
        if task not in task_classes and not (task != "chat_general" and "chat_general" in task_classes):
            return False, "task_class_mismatch"
        return True, ""

    def _route_sort_key(self, m: Dict[str, Any], task: str, diff: str, rlvl: str, privacy: str):
        cost = COST_RANK.get(str(m.get("cost_tier")), 9)
        lat = LAT_RANK.get(str(m.get("latency_tier")), 9)
        strengths = set(str(x) for x in (m.get("strengths") or []))
        local_bonus = -1 if (privacy == "local_preferred" and m.get("local_endpoint")) else 0
        fit = 0
        if task == "coding" and "coding" in strengths: fit -= 2
        if task in {"planning", "research", "verification"} and "reasoning" in strengths: fit -= 2
        if task == "vision" and m.get("supports_vision"): fit -= 3
        if rlvl == "deep" and "reasoning" not in strengths: fit += 2
        if diff in {"hard", "expert"} and "reasoning" not in strengths: fit += 2
        if rlvl == "cheap": fit += cost
        return (cost + local_bonus, fit, lat, m.get("ref"))

    def _estimate_units(self, m: Optional[Dict[str, Any]], tokens: int) -> Optional[float]:
        if not m:
            return None
        rate = {"free": 0.0, "low": 0.05, "medium": 0.2, "high": 0.6, "premium": 1.2}.get(str(m.get("cost_tier")), 0.2)
        return round((tokens / 1000.0) * rate, 4)

    def _village_role_instruction(self, role: str, mode: str) -> str:
        r = _s(role).lower()
        base = {
            "researcher": "Act as a researcher. Gather facts, assumptions, and missing data. Be explicit about uncertainty.",
            "coder": "Act as an implementation engineer. Produce practical architecture/implementation steps, tradeoffs, and migration path.",
            "critic": "Act as a critic. Attack weak assumptions, hidden risks, and likely failure modes. Be rigorous, not vague.",
            "verifier": "Act as a verifier. Propose tests, validation criteria, and objective pass/fail checks.",
            "strategist": "Act as a strategist. Prioritize options by impact, effort, risk, and sequencing.",
            "synthesizer": "Act as a synthesizer. Merge viewpoints and resolve conflicts into a concrete plan.",
        }.get(r, f"Act as specialist role '{role}'. Provide role-specific insights and concrete recommendations.")
        mode_hint = {
            "brainstorm": "Generate multiple non-trivial alternatives before converging.",
            "decision": "Focus on decision quality, tradeoffs, and recommendation.",
            "execution": "Focus on actionable implementation steps and immediate next actions.",
        }.get(_s(mode).lower(), "Balance ideation and execution.")
        return f"{base} {mode_hint} Use concise bullet points and concrete reasoning."

    def _village_synthesis_prompt(self, prompt: str, mode: str, ok_roles: List[Dict[str, Any]]) -> str:
        chunks: List[str] = [
            f"Objective:\n{prompt}",
            f"Village mode: {mode}",
            "Specialist outputs:",
        ]
        for row in ok_roles[:10]:
            role = _s(row.get("role")) or "specialist"
            text = _s(row.get("assistant_message") or row.get("assistant_preview"))
            text = text[:2400]
            model_ref = _s(((row.get("selected_model") or {}).get("ref")) if isinstance(row.get("selected_model"), dict) else "")
            chunks.append(f"\n[{role}] model={model_ref or 'n/a'}\n{text}")
        chunks.append(
            "\nProduce:\n"
            "1) consolidated answer\n"
            "2) disagreements/conflicts\n"
            "3) risk list\n"
            "4) prioritized next actions\n"
            "5) what to test/measure next"
        )
        return "\n".join(chunks)

    def _scrub_routes(self) -> None:
        valid = {m["ref"] for m in self.get_catalog()["items"]}
        pol = self.state.get("routing_policy")
        if not isinstance(pol, dict):
            return
        changed = False
        for row in (pol.get("task_routes") or {}).values():
            if not isinstance(row, dict):
                continue
            if row.get("primary") and row["primary"] not in valid:
                row["primary"] = None
                changed = True
            fb = [x for x in (row.get("fallbacks") or []) if x in valid]
            if fb != (row.get("fallbacks") or []):
                row["fallbacks"] = fb
                changed = True
        if changed:
            self._save()


model_control_plane = ModelControlPlane()
