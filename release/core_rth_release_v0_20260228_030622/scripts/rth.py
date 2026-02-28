#!/usr/bin/env python3
"""
Core Rth CLI v0 (Phase 1 spine)

Commands:
- scan
- kg
- cortex
- praxis
- guardian
- bench
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import signal
import subprocess
import sys
import time
import tempfile
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable
from urllib import error as urlerror
from urllib import request as urlrequest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _to_jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def _print_payload(payload: Any, out_path: str | None = None) -> None:
    data = _to_jsonable(payload)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if out_path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + "\n", encoding="utf-8")
    print(text)


def _bootstrap_event_bus(load_cortex: bool = False, load_praxis: bool = False) -> None:
    from app.core.event_bus import initialize_event_bus

    asyncio.run(initialize_event_bus())
    if load_cortex:
        from app.core.rth_cortex import get_cortex

        get_cortex()
    if load_praxis:
        from app.core.rth_praxis import get_praxis

        get_praxis()


def _runtime_dir() -> Path:
    candidates = [
        REPO_ROOT / "storage_runtime" / "service",
        REPO_ROOT / "logs" / "service",
        Path(tempfile.gettempdir()) / "rth_core" / "service",
    ]
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return p
        except Exception:
            continue
    # Last fallback (may still fail, but keeps behavior explicit).
    return candidates[-1]


def _api_host_port_key(host: str, port: int) -> str:
    host_safe = "".join(ch if ch.isalnum() else "_" for ch in str(host or "127.0.0.1"))
    return f"{host_safe}_{int(port)}"


def _legacy_api_state_path() -> Path:
    return _runtime_dir() / "core_rth_api_state.json"


def _api_state_path(host: str = "127.0.0.1", port: int = 18030) -> Path:
    return _runtime_dir() / f"core_rth_api_state_{_api_host_port_key(host, port)}.json"


def _api_log_path(host: str = "127.0.0.1", port: int = 18030) -> Path:
    return _runtime_dir() / f"core_rth_api_{_api_host_port_key(host, port)}.log"


def _load_api_state(host: str = "127.0.0.1", port: int = 18030) -> dict[str, Any]:
    path = _api_state_path(host, port)
    if not path.exists():
        # Backward compatibility with legacy single-state file.
        legacy = _legacy_api_state_path()
        if legacy.exists():
            try:
                data = json.loads(legacy.read_text(encoding="utf-8"))
                if int(data.get("port") or 0) == int(port) and str(data.get("host") or "") == str(host):
                    return data
            except Exception:
                pass
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_api_state(state: dict[str, Any], host: str = "127.0.0.1", port: int = 18030) -> None:
    path = _api_state_path(host, port)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Keep a "latest" compatibility pointer for older workflows.
    try:
        _legacy_api_state_path().write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass


def _clear_legacy_api_state_if_matches(host: str, port: int) -> None:
    legacy = _legacy_api_state_path()
    if not legacy.exists():
        return
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
    except Exception:
        return
    try:
        same_port = int(data.get("port") or 0) == int(port)
        same_host = str(data.get("host") or "") == str(host)
    except Exception:
        return
    if same_port and same_host:
        try:
            legacy.unlink(missing_ok=True)
        except Exception:
            pass


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        # Windows can surface invalid/stale PIDs via a low-level SystemError.
        return False


def _http_json(url: str, timeout: float = 2.5) -> dict[str, Any]:
    req = urlrequest.Request(url, headers={"Accept": "application/json"})
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return {
            "status_code": getattr(resp, "status", None),
            "ok": 200 <= int(getattr(resp, "status", 0)) < 300,
            "body": json.loads(raw) if raw.strip() else {},
        }


def _probe_api(base_url: str, timeout: float = 2.5) -> dict[str, Any]:
    out: dict[str, Any] = {"base_url": base_url, "endpoints": {}}
    for name, path in [
        ("live", "/health/live"),
        ("ready", "/health/ready"),
        ("api_health", "/api/v1/health"),
    ]:
        url = base_url.rstrip("/") + path
        try:
            out["endpoints"][name] = _http_json(url, timeout=timeout)
        except urlerror.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = str(e)
            parsed = None
            try:
                parsed = json.loads(body) if body.strip() else None
            except Exception:
                parsed = None
            out["endpoints"][name] = {
                "status_code": getattr(e, "code", None),
                "ok": False,
                "error": str(e),
                "body": parsed if parsed is not None else body[:1000],
            }
        except Exception as e:
            out["endpoints"][name] = {"ok": False, "error": str(e)}
    return out


def _cmd_status(args: argparse.Namespace) -> int:
    _bootstrap_event_bus(load_cortex=True, load_praxis=True)
    from app.core.jarvis import jarvis_core

    payload = jarvis_core.get_status()
    payload.update(jarvis_core.capabilities())
    _print_payload(payload, args.out)
    return 0


def _cmd_scan_run(args: argparse.Namespace) -> int:
    _bootstrap_event_bus(load_cortex=True, load_praxis=True)
    from app.core.fs_scanner import ScanScope, DEFAULT_EXCLUDES, fs_scanner
    from app.core.jarvis import jarvis_core
    from app.core.permissions import permission_gate

    exclude_globs: list[str] | None
    if args.no_default_excludes:
        exclude_globs = list(args.exclude or [])
    else:
        exclude_globs = list(DEFAULT_EXCLUDES)
        if args.exclude:
            exclude_globs.extend(args.exclude)

    scope = ScanScope(
        roots=args.roots,
        exclude_globs=exclude_globs,
        include_globs=args.include,
        max_depth=args.max_depth,
        max_file_size_mb=args.max_file_size_mb,
        hash_files=args.hash_files,
        content_snippets=(args.content_mode == "snippets"),
        content_full=(args.content_mode == "full"),
        snippet_bytes=args.snippet_bytes,
        max_files=args.max_files,
    )
    proposal = jarvis_core.propose_fs_scan(scope, args.reason)
    result: dict[str, Any] = {"proposal": proposal}

    if not args.execute:
        _print_payload(result, args.out)
        return 0

    req_id = proposal.get("request_id")
    if not req_id:
        result["status"] = "error"
        result["error"] = "missing_request_id"
        _print_payload(result, args.out)
        return 1

    if args.approve:
        decision = permission_gate.approve(req_id, decided_by=args.decided_by)
    else:
        decision = permission_gate.deny(req_id, reason="cli_run_without_approval", decided_by=args.decided_by)
    result["decision"] = decision.to_dict()

    if decision.decision.value != "approved":
        result["status"] = "denied"
        _print_payload(result, args.out)
        return 0

    result["scan"] = fs_scanner.execute(scope, req_id)
    result["status"] = "completed"
    _print_payload(result, args.out)
    return 0


def _cmd_scan_status(args: argparse.Namespace) -> int:
    from app.core.jarvis import jarvis_core

    payload = {"last_scan": jarvis_core.get_status().get("last_scan")}
    _print_payload(payload, args.out)
    return 0


def _cmd_kg_status(args: argparse.Namespace) -> int:
    from app.core.jarvis import jarvis_core

    _print_payload(jarvis_core.kg_status(), args.out)
    return 0


def _cmd_kg_query(args: argparse.Namespace) -> int:
    from app.core.jarvis import jarvis_core

    _print_payload(jarvis_core.kg_query(concept=args.concept, max_depth=args.max_depth), args.out)
    return 0


def _cmd_cortex_status(args: argparse.Namespace) -> int:
    _bootstrap_event_bus(load_cortex=True)
    from app.core.rth_cortex import get_cortex

    _print_payload(get_cortex().get_status(), args.out)
    return 0


def _cmd_praxis_status(args: argparse.Namespace) -> int:
    _bootstrap_event_bus(load_praxis=True)
    from app.core.rth_praxis import get_praxis

    _print_payload(get_praxis().get_status(), args.out)
    return 0


def _cmd_praxis_propose(args: argparse.Namespace) -> int:
    from app.core.jarvis import jarvis_core

    _print_payload(
        jarvis_core.propose_evolution(roots=args.roots or None, max_projects=args.max_projects),
        args.out,
    )
    return 0


def _cmd_guardian_policy(args: argparse.Namespace) -> int:
    from app.core.permissions import permission_gate
    op = str(getattr(args, "policy_op", "status") or "status").lower().strip()

    if op == "status":
        _print_payload(permission_gate.policy_status(), args.out)
        return 0

    if op == "get":
        _print_payload(permission_gate.guardian_dsl_get(), args.out)
        return 0

    if op == "validate":
        if args.file:
            payload = permission_gate.guardian_dsl_validate_file(args.file)
        else:
            payload = permission_gate.guardian_dsl_validate_payload(permission_gate.guardian_dsl_get().get("policy", {}))
        _print_payload(payload, args.out)
        return 0 if bool(payload.get("ok")) else 1

    if op == "set":
        if args.set_defaults:
            payload = permission_gate.guardian_dsl_set_default()
            _print_payload(payload, args.out)
            return 0
        if not args.file:
            _print_payload({"status": "error", "detail": "set requires --file or --set-defaults"}, args.out)
            return 1
        p = Path(args.file)
        if not p.exists():
            _print_payload({"status": "error", "detail": f"file not found: {args.file}"}, args.out)
            return 1
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            _print_payload({"status": "error", "detail": f"invalid json: {e}"}, args.out)
            return 1
        try:
            saved = permission_gate.guardian_dsl_set(data)
        except Exception as e:
            _print_payload({"status": "error", "detail": str(e)}, args.out)
            return 1
        _print_payload(saved, args.out)
        return 0

    _print_payload({"status": "error", "detail": f"unknown policy op: {op}"}, args.out)
    return 1
    return 0


def _cmd_guardian_requests(args: argparse.Namespace) -> int:
    from app.core.permissions import permission_gate

    payload = {"requests": permission_gate.list_requests()}
    if args.status:
        payload["requests"] = [r for r in payload["requests"] if str(r.get("status", r.get("decision", ""))) == args.status]
    _print_payload(payload, args.out)
    return 0


def _cmd_guardian_approve(args: argparse.Namespace) -> int:
    from app.core.permissions import permission_gate

    _print_payload(permission_gate.approve(args.request_id, decided_by=args.decided_by).to_dict(), args.out)
    return 0


def _cmd_guardian_deny(args: argparse.Namespace) -> int:
    from app.core.permissions import permission_gate

    _print_payload(
        permission_gate.deny(args.request_id, reason=args.reason, decided_by=args.decided_by).to_dict(),
        args.out,
    )
    return 0


def _cmd_guardian_audit(args: argparse.Namespace) -> int:
    _bootstrap_event_bus(load_cortex=True)
    from app.core.permissions import permission_gate
    from app.core.rth_cortex import get_cortex

    policy = permission_gate.policy_status()
    cortex = get_cortex().get_status()

    root_analytics = list(cortex.get("root_analytics") or [])
    semantic_conflicts = list(cortex.get("root_semantic_conflicts") or [])
    alignment_conflicts = list(cortex.get("root_alignment_conflicts") or [])

    roots_summary = []
    for row in root_analytics:
        audit = dict(row.get("audit") or {})
        roots_summary.append(
            {
                "root": row.get("root"),
                "domain": row.get("domain") or audit.get("domain"),
                "files_seen": row.get("files_seen"),
                "maturity_score": audit.get("maturity_score"),
                "risk_score": audit.get("risk_score"),
                "top_findings": (audit.get("findings") or [])[:6],
                "gaps": (audit.get("gaps") or [])[:6],
                "risks": (audit.get("risks") or [])[:6],
                "scan_flags": row.get("scan_flags") or {},
            }
        )

    severity_rank = {"high": 3, "medium": 2, "low": 1}
    semantic_items = []
    for item in semantic_conflicts:
        findings = list(item.get("semantic_conflicts") or [])
        max_sev = max((severity_rank.get(str(f.get("severity", "low")), 1) for f in findings), default=1)
        semantic_items.append(
            {
                "roots": item.get("roots"),
                "domains": item.get("domains"),
                "conflict_count": len(findings),
                "max_severity": next((k for k, v in severity_rank.items() if v == max_sev), "low"),
                "conflicts": findings[:8],
            }
        )
    semantic_items.sort(key=lambda x: (severity_rank.get(x["max_severity"], 1), x["conflict_count"]), reverse=True)

    top_root_risks = sorted(
        [
            {
                "root": r.get("root"),
                "domain": r.get("domain"),
                "risk_score": (r.get("audit") or {}).get("risk_score"),
                "maturity_score": (r.get("audit") or {}).get("maturity_score"),
            }
            for r in root_analytics
        ],
        key=lambda x: (x.get("risk_score") if isinstance(x.get("risk_score"), (int, float)) else -1),
        reverse=True,
    )

    recommendations = []
    if semantic_items:
        recommendations.append("Formalizzare policy per-root (execution tiers) e templates di consenso obbligatori per integrazioni cross-root.")
    if any((x.get("risk_score") or 0) >= 60 for x in top_root_risks):
        recommendations.append("Attivare dry-run + audit trail tamper-evident sui root con risk_score alto prima di automation cross-root.")
    if any("tests" in (c.get("mismatched_controls") or []) for c in alignment_conflicts):
        recommendations.append("Allineare baseline CI/tests tra root integrati prima di orchestrazione automatica.")
    if not recommendations:
        recommendations.append("Policy posture coerente: mantenere benchmark governance e replay dei consensi come gate di rilascio.")

    payload = {
        "guardian_policy": policy,
        "cortex_summary": {
            "root_analytics_count": cortex.get("root_analytics_count", len(root_analytics)),
            "root_alignment_conflicts_count": len(alignment_conflicts),
            "root_semantic_conflicts_count": len(semantic_items),
            "detected_biases": cortex.get("detected_biases"),
            "resolved_conflicts": cortex.get("resolved_conflicts"),
        },
        "top_root_risks": top_root_risks[: args.limit],
        "root_audits": roots_summary[: args.limit],
        "root_alignment_conflicts": alignment_conflicts[: args.limit],
        "root_semantic_conflicts": semantic_items[: args.limit],
        "release_gate": {
            "semantic_guard_enabled": bool(((policy.get("semantic_guard") or {}).get("enabled"))),
            "owner_approval_required": bool(policy.get("require_owner_approval")),
            "hard_no_go": policy.get("hard_no_go") or [],
        },
        "recommendations": recommendations,
    }
    if args.gate:
        checks: list[dict[str, Any]] = []

        def _gate_check(ok: bool, check_id: str, detail: str, severity: str = "error") -> None:
            checks.append(
                {
                    "id": check_id,
                    "ok": bool(ok),
                    "severity": severity,
                    "detail": detail,
                }
            )

        guardian_dsl_status = ((policy.get("guardian_dsl") or {}) if isinstance(policy, dict) else {}) or {}
        hard_no_go = set(str(x) for x in (policy.get("hard_no_go") or []))

        _gate_check(bool(((policy.get("semantic_guard") or {}).get("enabled"))), "semantic_guard_enabled", "Semantic Guardian hook must be enabled")
        _gate_check(bool(policy.get("require_owner_approval")), "owner_approval_required", "Owner approval must be required")
        _gate_check(bool(guardian_dsl_status.get("enabled", False)), "guardian_dsl_enabled", "Guardian DSL must be enabled")
        _gate_check(str(guardian_dsl_status.get("mode", "enforce")) == "enforce", "guardian_dsl_enforce_mode", "Guardian DSL mode must be 'enforce'")
        _gate_check({"payments", "social_posting"}.issubset(hard_no_go), "hard_no_go_baseline", "payments/social_posting must remain hard NO-GO")

        root_count = int(cortex.get("root_analytics_count", len(root_analytics)) or 0)
        if args.allow_empty_root_audits:
            _gate_check(root_count > 0, "root_audits_present", "No root audits loaded (allowed by flag)", severity="warn")
        else:
            _gate_check(root_count > 0, "root_audits_present", "No root audits loaded; run scan + cortex bootstrap first")

        risk_values = [
            float(x.get("risk_score"))
            for x in top_root_risks
            if isinstance(x.get("risk_score"), (int, float))
        ]
        max_risk_seen = max(risk_values) if risk_values else None
        if max_risk_seen is None:
            _gate_check(bool(args.allow_empty_root_audits), "root_risk_threshold", "No root risk scores available")
        else:
            _gate_check(max_risk_seen <= float(args.max_root_risk), "root_risk_threshold", f"max root risk {max_risk_seen} <= threshold {float(args.max_root_risk)}")

        high_semantic_count = sum(1 for item in semantic_items if str(item.get("max_severity")) == "high")
        _gate_check(
            high_semantic_count <= int(args.max_high_severity_semantic),
            "high_semantic_conflicts_threshold",
            f"high severity semantic conflicts {high_semantic_count} <= threshold {int(args.max_high_severity_semantic)}",
        )

        fail_checks = [c for c in checks if not c["ok"] and c.get("severity", "error") != "warn"]
        warn_checks = [c for c in checks if not c["ok"] and c.get("severity") == "warn"]
        payload["release_gate_evaluation"] = {
            "enabled": True,
            "passed": len(fail_checks) == 0,
            "thresholds": {
                "max_root_risk": float(args.max_root_risk),
                "max_high_severity_semantic": int(args.max_high_severity_semantic),
                "allow_empty_root_audits": bool(args.allow_empty_root_audits),
            },
            "checks": checks,
            "failed_checks": fail_checks,
            "warning_checks": warn_checks,
            "summary": {
                "checks_total": len(checks),
                "failed": len(fail_checks),
                "warnings": len(warn_checks),
            },
        }
    _print_payload(payload, args.out)
    if args.gate and not bool(((payload.get("release_gate_evaluation") or {}).get("passed"))):
        return 2
    return 0


def _cmd_api_start(args: argparse.Namespace) -> int:
    state = _load_api_state(args.host, args.port)
    old_pid = int(state.get("pid") or 0) if state else 0
    stale_state_replaced = False
    if old_pid and _pid_alive(old_pid):
        old_base = state.get("base_url", f"http://{args.host}:{args.port}")
        old_probe = _probe_api(old_base, timeout=1.5)
        if any(bool((old_probe.get("endpoints", {}).get(k) or {}).get("ok")) for k in ("live", "ready", "api_health")):
            payload = {
                "status": "already_running",
                "state": state,
                "state_path": str(_api_state_path(args.host, args.port)),
                "probe": old_probe,
            }
            _print_payload(payload, args.out)
            return 0
        stale_state_replaced = True

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--log-level",
        args.log_level,
    ]

    if args.foreground:
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
        return int(proc.returncode or 0)

    log_path = _api_log_path(args.host, args.port)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fp = open(log_path, "a", encoding="utf-8", errors="replace")

    creationflags = 0
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        kwargs["creationflags"] = creationflags
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        **kwargs,
    )

    # Give it a short boot window for immediate feedback.
    time.sleep(max(0.2, args.wait_sec))
    base_url = f"http://{args.host}:{args.port}"
    probe = _probe_api(base_url, timeout=1.5)
    state = {
        "pid": proc.pid,
        "host": args.host,
        "port": args.port,
        "base_url": base_url,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "command": cmd,
        "log_path": str(log_path),
    }
    _save_api_state(state, args.host, args.port)
    payload = {
        "status": "started",
        "state": state,
        "state_path": str(_api_state_path(args.host, args.port)),
        "probe": probe,
    }
    if stale_state_replaced:
        payload["note"] = "Replaced stale API state for requested host/port (PID alive but probe failed)."
    _print_payload(payload, args.out)
    return 0


def _cmd_api_status(args: argparse.Namespace) -> int:
    state = _load_api_state(args.host, args.port)
    pid = int(state.get("pid") or 0) if state else 0
    base_url = state.get("base_url") if state else None
    if not base_url:
        base_url = f"http://{args.host}:{args.port}"
    payload = {
        "state": state or None,
        "state_path": str(_api_state_path(args.host, args.port)),
        "pid_alive": _pid_alive(pid) if pid else False,
        "probe": _probe_api(base_url, timeout=args.timeout),
    }
    _print_payload(payload, args.out)
    return 0


def _cmd_api_stop(args: argparse.Namespace) -> int:
    state = _load_api_state(args.host, args.port)
    pid = int(state.get("pid") or 0) if state else 0
    if not pid:
        # Fallback: if a stale legacy state exists, report it and optionally clear.
        legacy = _legacy_api_state_path()
        if legacy.exists():
            try:
                legacy_state = json.loads(legacy.read_text(encoding="utf-8"))
            except Exception:
                legacy_state = {}
            payload = {
                "status": "not_running",
                "state": state or None,
                "state_path": str(_api_state_path(args.host, args.port)),
                "legacy_state": legacy_state or None,
                "legacy_state_path": str(legacy),
            }
            _print_payload(payload, args.out)
            return 0
        _print_payload({"status": "not_running", "state": state or None, "state_path": str(_api_state_path(args.host, args.port))}, args.out)
        return 0

    if not _pid_alive(pid):
        _print_payload({"status": "stale_pid", "state": state or None, "state_path": str(_api_state_path(args.host, args.port))}, args.out)
        if args.clear_state:
            try:
                _api_state_path(args.host, args.port).unlink(missing_ok=True)
            except Exception:
                pass
            _clear_legacy_api_state_if_matches(args.host, args.port)
        return 0

    try:
        if os.name == "nt":
            os.kill(pid, signal.SIGTERM)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception as e:
        _print_payload({"status": "error", "error": str(e), "state": state}, args.out)
        return 1

    deadline = time.time() + max(0.5, args.wait_sec)
    stopped = False
    while time.time() < deadline:
        if not _pid_alive(pid):
            stopped = True
            break
        time.sleep(0.2)

    if not stopped and args.force:
        try:
            if os.name == "nt":
                os.kill(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
        time.sleep(0.2)
        stopped = not _pid_alive(pid)

    if stopped and args.clear_state:
        try:
            _api_state_path(args.host, args.port).unlink(missing_ok=True)
        except Exception:
            pass
        _clear_legacy_api_state_if_matches(args.host, args.port)

    payload = {
        "status": "stopped" if stopped else "timeout",
        "pid": pid,
        "state": state,
        "state_path": str(_api_state_path(args.host, args.port)),
        "pid_alive": _pid_alive(pid),
    }
    _print_payload(payload, args.out)
    return 0 if stopped else 1


def _cmd_api_health(args: argparse.Namespace) -> int:
    base_url = args.url or f"http://{args.host}:{args.port}"
    _print_payload(_probe_api(base_url, timeout=args.timeout), args.out)
    return 0


def _run_bench_cmd(parts: Iterable[str]) -> int:
    cmd = [sys.executable, *parts]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    return int(proc.returncode or 0)


def _cmd_bench_prepare(args: argparse.Namespace) -> int:
    parts = ["bench/runner.py", "prepare", "--system", args.system]
    if args.suite:
        parts += ["--suite", args.suite]
    if args.out_dir:
        parts += ["--out", args.out_dir]
    if args.label:
        parts += ["--label", args.label]
    return _run_bench_cmd(parts)


def _cmd_bench_score(args: argparse.Namespace) -> int:
    return _run_bench_cmd(["bench/runner.py", "score", "--run", args.run])


def _cmd_bench_compare(args: argparse.Namespace) -> int:
    return _run_bench_cmd(
        ["bench/runner.py", "compare", "--run-a", args.run_a, "--run-b", args.run_b]
    )


def _plugin_catalog_filtered(args: argparse.Namespace) -> list[dict[str, Any]]:
    from app.core.plugin_registry_public import plugin_registry_public

    rows = list((plugin_registry_public.catalog().get("items") or []))
    cat = str(getattr(args, "category", "") or "").strip().lower()
    pack = str(getattr(args, "pack", "") or "").strip().lower()
    tier = str(getattr(args, "tier", "") or "").strip().lower()
    install_state = str(getattr(args, "install_state", "") or "").strip().lower()
    enabled_only = bool(getattr(args, "enabled_only", False))
    p0_only = bool(getattr(args, "p0_only", False))

    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        meta = row.get("registry_meta") if isinstance(row.get("registry_meta"), dict) else {}
        if cat and str(row.get("category", "")).lower() != cat:
            continue
        if pack and str(meta.get("pack", "")).lower() != pack:
            continue
        if tier and str(row.get("compatibility_tier", "")).lower() != tier:
            continue
        if install_state and str(row.get("install_state", "")).lower() != install_state:
            continue
        if enabled_only and not bool(row.get("enabled")):
            continue
        if p0_only and str(meta.get("priority", "")).upper() != "P0":
            continue
        out.append(row)
    return out


def _cmd_plugins_status(args: argparse.Namespace) -> int:
    from app.core.plugin_registry_public import plugin_registry_public

    _print_payload(plugin_registry_public.status(), args.out)
    return 0


def _cmd_plugins_catalog(args: argparse.Namespace) -> int:
    rows = _plugin_catalog_filtered(args)
    payload = {
        "status": "ok",
        "count": len(rows),
        "filters": {
            "category": args.category or None,
            "pack": args.pack or None,
            "tier": args.tier or None,
            "install_state": args.install_state or None,
            "enabled_only": bool(args.enabled_only),
            "p0_only": bool(args.p0_only),
        },
        "items": rows if args.full else [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "vendor": r.get("vendor"),
                "category": r.get("category"),
                "tier": r.get("compatibility_tier"),
                "install_state": r.get("install_state"),
                "enabled": r.get("enabled"),
                "pack": ((r.get("registry_meta") or {}).get("pack") if isinstance(r.get("registry_meta"), dict) else None),
                "priority": ((r.get("registry_meta") or {}).get("priority") if isinstance(r.get("registry_meta"), dict) else None),
                "last_healthcheck": r.get("last_healthcheck"),
            }
            for r in rows
        ],
    }
    _print_payload(payload, args.out)
    return 0


def _cmd_plugins_matrix(args: argparse.Namespace) -> int:
    from app.core.plugin_registry_public import plugin_registry_public

    _print_payload(plugin_registry_public.compatibility_matrix(), args.out)
    return 0


def _cmd_plugins_schema(args: argparse.Namespace) -> int:
    from app.core.plugin_registry_public import plugin_registry_public

    _print_payload(plugin_registry_public.schema_document(), args.out)
    return 0


def _cmd_plugins_healthcheck(args: argparse.Namespace) -> int:
    from app.core.plugin_registry_public import plugin_registry_public

    payload = plugin_registry_public.healthcheck_plugin(
        plugin_id=args.plugin_id,
        timeout_sec=args.timeout_sec,
        reason=args.reason,
        confirm_owner=not args.proposal_only,
        decided_by=args.decided_by,
    )
    _print_payload(payload, args.out)
    if payload.get("status") in {"invalid", "not_found", "denied"}:
        return 1
    return 0


def _cmd_plugins_healthcheck_batch(args: argparse.Namespace) -> int:
    from app.core.plugin_registry_public import plugin_registry_public

    payload = plugin_registry_public.healthcheck_batch(
        plugin_ids=args.plugin_id or None,
        priority_only=bool(args.priority_only),
        category=args.category or "",
        pack=args.pack or "",
        tier=args.tier or "",
        install_state=args.install_state or "",
        enabled_only=bool(args.enabled_only),
        include_not_configured=bool(args.include_not_configured),
        limit=args.limit,
        timeout_sec=args.timeout_sec,
        reason=args.reason,
        confirm_owner=not args.proposal_only,
        decided_by=args.decided_by,
    )
    _print_payload(payload, args.out)
    return 0


def _cmd_plugins_state_set(args: argparse.Namespace) -> int:
    from app.core.plugin_registry_public import plugin_registry_public

    enabled: bool | None = None
    if args.enabled is True:
        enabled = True
    elif args.enabled is False:
        enabled = False
    payload = plugin_registry_public.set_plugin_state(
        plugin_id=args.plugin_id,
        enabled=enabled,
        install_state=args.install_state,
        reason=args.reason,
        confirm_owner=not args.proposal_only,
        decided_by=args.decided_by,
    )
    _print_payload(payload, args.out)
    return 0 if payload.get("status") in {"ok", "proposal_only"} else 1


def _cmd_plugins_driver(args: argparse.Namespace) -> int:
    from app.core.plugin_registry_public import plugin_registry_public

    payload = plugin_registry_public.driver_action(
        plugin_id=args.plugin_id,
        action=args.driver_action,
        timeout_sec=args.timeout_sec,
        reason=args.reason,
        confirm_owner=not args.proposal_only,
        decided_by=args.decided_by,
    )
    _print_payload(payload, args.out)
    return 0 if payload.get("status") in {"ok", "proposal_only"} else 1


def _cmd_plugins_validate(args: argparse.Namespace) -> int:
    from app.core.plugin_registry_public import plugin_registry_public

    p = Path(args.file)
    if not p.exists():
        _print_payload({"status": "error", "detail": f"file not found: {args.file}"}, args.out)
        return 1
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        _print_payload({"status": "error", "detail": f"invalid json: {e}"}, args.out)
        return 1
    payload = plugin_registry_public.validate_manifest(data)
    _print_payload(payload, args.out)
    return 0 if bool(payload.get("ok")) else 1


def _cmd_plugins_register(args: argparse.Namespace) -> int:
    from app.core.plugin_registry_public import plugin_registry_public

    p = Path(args.file)
    if not p.exists():
        _print_payload({"status": "error", "detail": f"file not found: {args.file}"}, args.out)
        return 1
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        _print_payload({"status": "error", "detail": f"invalid json: {e}"}, args.out)
        return 1
    payload = plugin_registry_public.register_manifest(
        payload=data,
        reason=args.reason,
        confirm_owner=not args.proposal_only,
        decided_by=args.decided_by,
    )
    _print_payload(payload, args.out)
    return 0 if payload.get("status") in {"ok", "proposal_only"} else 1


def _cmd_plugins_delete(args: argparse.Namespace) -> int:
    from app.core.plugin_registry_public import plugin_registry_public

    payload = plugin_registry_public.delete_manifest(
        plugin_id=args.plugin_id,
        reason=args.reason,
        confirm_owner=not args.proposal_only,
        decided_by=args.decided_by,
    )
    _print_payload(payload, args.out)
    return 0 if payload.get("status") in {"ok", "proposal_only"} else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Core Rth CLI v0")
    p.set_defaults(func=lambda _args: p.print_help() or 0)

    sp = p.add_subparsers(dest="cmd")

    p_status = sp.add_parser("status", help="Core Rth status snapshot")
    p_status.add_argument("--out", help="Write JSON output to file")
    p_status.set_defaults(func=_cmd_status)

    p_api = sp.add_parser("api", help="API service commands (local uvicorn)")
    api_sp = p_api.add_subparsers(dest="api_cmd")
    p_api.set_defaults(func=lambda _args: p_api.print_help() or 0)

    p_api_start = api_sp.add_parser("start", help="Start Core Rth API (background by default)")
    p_api_start.add_argument("--host", default="127.0.0.1")
    p_api_start.add_argument("--port", type=int, default=18030)
    p_api_start.add_argument("--log-level", default="info")
    p_api_start.add_argument("--wait-sec", type=float, default=1.0)
    p_api_start.add_argument("--foreground", action="store_true")
    p_api_start.add_argument("--out")
    p_api_start.set_defaults(func=_cmd_api_start)

    p_api_status = api_sp.add_parser("status", help="Show API process/probe status")
    p_api_status.add_argument("--host", default="127.0.0.1")
    p_api_status.add_argument("--port", type=int, default=18030)
    p_api_status.add_argument("--timeout", type=float, default=1.5)
    p_api_status.add_argument("--out")
    p_api_status.set_defaults(func=_cmd_api_status)

    p_api_stop = api_sp.add_parser("stop", help="Stop API process from PID state")
    p_api_stop.add_argument("--host", default="127.0.0.1")
    p_api_stop.add_argument("--port", type=int, default=18030)
    p_api_stop.add_argument("--wait-sec", type=float, default=5.0)
    p_api_stop.add_argument("--force", action="store_true")
    p_api_stop.add_argument("--no-clear-state", dest="clear_state", action="store_false")
    p_api_stop.add_argument("--out")
    p_api_stop.set_defaults(func=_cmd_api_stop, clear_state=True)

    p_api_health = api_sp.add_parser("health", help="Probe API health endpoints")
    p_api_health.add_argument("--url", default="")
    p_api_health.add_argument("--host", default="127.0.0.1")
    p_api_health.add_argument("--port", type=int, default=18030)
    p_api_health.add_argument("--timeout", type=float, default=1.5)
    p_api_health.add_argument("--out")
    p_api_health.set_defaults(func=_cmd_api_health)

    p_scan = sp.add_parser("scan", help="Filesystem scan commands")
    scan_sp = p_scan.add_subparsers(dest="scan_cmd")
    p_scan.set_defaults(func=lambda _args: p_scan.print_help() or 0)

    p_scan_run = scan_sp.add_parser("run", help="Propose+approve+execute a scan")
    p_scan_run.add_argument("roots", nargs="+", help="Roots to scan")
    p_scan_run.add_argument("--reason", default="CLI scan run")
    p_scan_run.add_argument("--max-depth", type=int)
    p_scan_run.add_argument("--max-files", type=int)
    p_scan_run.add_argument("--max-file-size-mb", type=int, default=50)
    p_scan_run.add_argument("--include", action="append", help="Glob include (repeatable)")
    p_scan_run.add_argument("--exclude", action="append", help="Glob exclude (repeatable)")
    p_scan_run.add_argument("--no-default-excludes", action="store_true")
    p_scan_run.add_argument("--hash-files", action="store_true")
    p_scan_run.add_argument("--content-mode", choices=["none", "snippets", "full"], default="none")
    p_scan_run.add_argument("--snippet-bytes", type=int, default=256)
    p_scan_run.add_argument("--decided-by", default="owner")
    p_scan_run.add_argument("--no-approve", dest="approve", action="store_false")
    p_scan_run.add_argument("--no-execute", dest="execute", action="store_false")
    p_scan_run.add_argument("--out", help="Write JSON output to file")
    p_scan_run.set_defaults(func=_cmd_scan_run, approve=True, execute=True)

    p_scan_status = scan_sp.add_parser("status", help="Show last scan summary")
    p_scan_status.add_argument("--out")
    p_scan_status.set_defaults(func=_cmd_scan_status)

    p_kg = sp.add_parser("kg", help="Knowledge graph commands")
    kg_sp = p_kg.add_subparsers(dest="kg_cmd")
    p_kg.set_defaults(func=lambda _args: p_kg.print_help() or 0)

    p_kg_status = kg_sp.add_parser("status", help="Knowledge graph status")
    p_kg_status.add_argument("--out")
    p_kg_status.set_defaults(func=_cmd_kg_status)

    p_kg_query = kg_sp.add_parser("query", help="Query related concepts")
    p_kg_query.add_argument("concept")
    p_kg_query.add_argument("--max-depth", type=int, default=2)
    p_kg_query.add_argument("--out")
    p_kg_query.set_defaults(func=_cmd_kg_query)

    p_cortex = sp.add_parser("cortex", help="Cortex commands")
    cortex_sp = p_cortex.add_subparsers(dest="cortex_cmd")
    p_cortex.set_defaults(func=lambda _args: p_cortex.print_help() or 0)
    p_cortex_status = cortex_sp.add_parser("status", help="Cortex status/root analytics")
    p_cortex_status.add_argument("--out")
    p_cortex_status.set_defaults(func=_cmd_cortex_status)

    p_praxis = sp.add_parser("praxis", help="Praxis/evolution commands")
    praxis_sp = p_praxis.add_subparsers(dest="praxis_cmd")
    p_praxis.set_defaults(func=lambda _args: p_praxis.print_help() or 0)

    p_praxis_status = praxis_sp.add_parser("status", help="Praxis module status")
    p_praxis_status.add_argument("--out")
    p_praxis_status.set_defaults(func=_cmd_praxis_status)

    p_praxis_prop = praxis_sp.add_parser("propose", help="Project evolution proposals (practical Praxis)")
    p_praxis_prop.add_argument("--roots", nargs="*", default=None)
    p_praxis_prop.add_argument("--max-projects", type=int, default=200)
    p_praxis_prop.add_argument("--out")
    p_praxis_prop.set_defaults(func=_cmd_praxis_propose)

    p_guard = sp.add_parser("guardian", help="Guardian/permission gate commands")
    guard_sp = p_guard.add_subparsers(dest="guardian_cmd")
    p_guard.set_defaults(func=lambda _args: p_guard.print_help() or 0)

    p_guard_policy = guard_sp.add_parser("policy", help="Guardian policy status")
    p_guard_policy.add_argument(
        "policy_op",
        nargs="?",
        default="status",
        choices=["status", "get", "set", "validate"],
        help="status (default), get/set/validate Guardian DSL policy",
    )
    p_guard_policy.add_argument("--file", help="JSON policy file path for set/validate")
    p_guard_policy.add_argument("--set-defaults", action="store_true", help="Write default Guardian DSL policy (for 'set')")
    p_guard_policy.add_argument("--out")
    p_guard_policy.set_defaults(func=_cmd_guardian_policy)

    p_guard_audit = guard_sp.add_parser("audit", help="Guardian + Cortex root-aware governance audit")
    p_guard_audit.add_argument("--limit", type=int, default=10)
    p_guard_audit.add_argument("--gate", action="store_true", help="Evaluate release gate pass/fail and exit non-zero on fail")
    p_guard_audit.add_argument("--max-root-risk", type=float, default=80.0, help="Release gate threshold for highest root risk_score")
    p_guard_audit.add_argument(
        "--max-high-severity-semantic",
        type=int,
        default=0,
        help="Release gate threshold for high-severity semantic conflict pairs",
    )
    p_guard_audit.add_argument(
        "--allow-empty-root-audits",
        action="store_true",
        help="Do not fail gate when no root audits are loaded (still reported as warning)",
    )
    p_guard_audit.add_argument("--out")
    p_guard_audit.set_defaults(func=_cmd_guardian_audit)

    p_guard_reqs = guard_sp.add_parser("requests", help="List permission requests")
    p_guard_reqs.add_argument("--status", help="Filter by status/decision")
    p_guard_reqs.add_argument("--out")
    p_guard_reqs.set_defaults(func=_cmd_guardian_requests)

    p_guard_approve = guard_sp.add_parser("approve", help="Approve a request id")
    p_guard_approve.add_argument("request_id")
    p_guard_approve.add_argument("--decided-by", default="owner")
    p_guard_approve.add_argument("--out")
    p_guard_approve.set_defaults(func=_cmd_guardian_approve)

    p_guard_deny = guard_sp.add_parser("deny", help="Deny a request id")
    p_guard_deny.add_argument("request_id")
    p_guard_deny.add_argument("--reason", default="denied")
    p_guard_deny.add_argument("--decided-by", default="owner")
    p_guard_deny.add_argument("--out")
    p_guard_deny.set_defaults(func=_cmd_guardian_deny)

    p_plugins = sp.add_parser("plugins", help="Public plugin registry / drivers / healthchecks")
    plugins_sp = p_plugins.add_subparsers(dest="plugins_cmd")
    p_plugins.set_defaults(func=lambda _args: p_plugins.print_help() or 0)

    p_pl_status = plugins_sp.add_parser("status", help="Plugin registry status")
    p_pl_status.add_argument("--out")
    p_pl_status.set_defaults(func=_cmd_plugins_status)

    p_pl_catalog = plugins_sp.add_parser("catalog", help="List plugin catalog (filterable)")
    p_pl_catalog.add_argument("--category", default="")
    p_pl_catalog.add_argument("--pack", default="")
    p_pl_catalog.add_argument("--tier", default="")
    p_pl_catalog.add_argument("--install-state", default="")
    p_pl_catalog.add_argument("--enabled-only", action="store_true")
    p_pl_catalog.add_argument("--p0-only", action="store_true")
    p_pl_catalog.add_argument("--full", action="store_true", help="Emit full manifests")
    p_pl_catalog.add_argument("--out")
    p_pl_catalog.set_defaults(func=_cmd_plugins_catalog)

    p_pl_matrix = plugins_sp.add_parser("matrix", help="Compatibility matrix")
    p_pl_matrix.add_argument("--out")
    p_pl_matrix.set_defaults(func=_cmd_plugins_matrix)

    p_pl_schema = plugins_sp.add_parser("schema", help="Plugin manifest schema")
    p_pl_schema.add_argument("--out")
    p_pl_schema.set_defaults(func=_cmd_plugins_schema)

    p_pl_hc = plugins_sp.add_parser("healthcheck", help="Run plugin healthcheck (Guardian proposal-first)")
    p_pl_hc.add_argument("plugin_id")
    p_pl_hc.add_argument("--timeout-sec", type=float, default=2.5)
    p_pl_hc.add_argument("--reason", default="CLI plugin healthcheck")
    p_pl_hc.add_argument("--decided-by", default="owner")
    p_pl_hc.add_argument("--proposal-only", action="store_true")
    p_pl_hc.add_argument("--out")
    p_pl_hc.set_defaults(func=_cmd_plugins_healthcheck)

    p_pl_hcb = plugins_sp.add_parser("healthcheck-batch", help="Run batch healthchecks with filters")
    p_pl_hcb.add_argument("--plugin-id", action="append", help="Repeatable explicit plugin id filter")
    p_pl_hcb.add_argument("--priority-only", action="store_true")
    p_pl_hcb.add_argument("--category", default="")
    p_pl_hcb.add_argument("--pack", default="")
    p_pl_hcb.add_argument("--tier", default="")
    p_pl_hcb.add_argument("--install-state", default="")
    p_pl_hcb.add_argument("--enabled-only", action="store_true")
    p_pl_hcb.add_argument("--include-not-configured", action="store_true")
    p_pl_hcb.add_argument("--limit", type=int, default=20)
    p_pl_hcb.add_argument("--timeout-sec", type=float, default=1.5)
    p_pl_hcb.add_argument("--reason", default="CLI plugin healthcheck batch")
    p_pl_hcb.add_argument("--decided-by", default="owner")
    p_pl_hcb.add_argument("--proposal-only", action="store_true")
    p_pl_hcb.add_argument("--out")
    p_pl_hcb.set_defaults(func=_cmd_plugins_healthcheck_batch)

    p_pl_state = plugins_sp.add_parser("state", help="Set plugin install/enabled state (manual override)")
    p_pl_state.add_argument("plugin_id")
    p_pl_state.add_argument("--install-state", default=None)
    p_pl_state.add_argument("--enable", dest="enabled", action="store_true")
    p_pl_state.add_argument("--disable", dest="enabled", action="store_false")
    p_pl_state.add_argument("--reason", default="CLI plugin state set")
    p_pl_state.add_argument("--decided-by", default="owner")
    p_pl_state.add_argument("--proposal-only", action="store_true")
    p_pl_state.add_argument("--out")
    p_pl_state.set_defaults(func=_cmd_plugins_state_set, enabled=None)

    p_pl_driver = plugins_sp.add_parser("driver", help="Run plugin driver action (install/enable/disable)")
    p_pl_driver.add_argument("driver_action", choices=["install", "enable", "disable"])
    p_pl_driver.add_argument("plugin_id")
    p_pl_driver.add_argument("--timeout-sec", type=float, default=6.0)
    p_pl_driver.add_argument("--reason", default="CLI plugin driver action")
    p_pl_driver.add_argument("--decided-by", default="owner")
    p_pl_driver.add_argument("--proposal-only", action="store_true")
    p_pl_driver.add_argument("--out")
    p_pl_driver.set_defaults(func=_cmd_plugins_driver)

    p_pl_validate = plugins_sp.add_parser("validate", help="Validate manifest JSON file")
    p_pl_validate.add_argument("file")
    p_pl_validate.add_argument("--out")
    p_pl_validate.set_defaults(func=_cmd_plugins_validate)

    p_pl_register = plugins_sp.add_parser("register", help="Register manifest JSON file")
    p_pl_register.add_argument("file")
    p_pl_register.add_argument("--reason", default="CLI plugin manifest register")
    p_pl_register.add_argument("--decided-by", default="owner")
    p_pl_register.add_argument("--proposal-only", action="store_true")
    p_pl_register.add_argument("--out")
    p_pl_register.set_defaults(func=_cmd_plugins_register)

    p_pl_delete = plugins_sp.add_parser("delete", help="Delete registered plugin manifest by id")
    p_pl_delete.add_argument("plugin_id")
    p_pl_delete.add_argument("--reason", default="CLI plugin manifest delete")
    p_pl_delete.add_argument("--decided-by", default="owner")
    p_pl_delete.add_argument("--proposal-only", action="store_true")
    p_pl_delete.add_argument("--out")
    p_pl_delete.set_defaults(func=_cmd_plugins_delete)

    p_bench = sp.add_parser("bench", help="Benchmark wrapper")
    bench_sp = p_bench.add_subparsers(dest="bench_cmd")
    p_bench.set_defaults(func=lambda _args: p_bench.print_help() or 0)

    p_bench_prepare = bench_sp.add_parser("prepare", help="Prepare benchmark run")
    p_bench_prepare.add_argument("--system", required=True, choices=["core_rth", "openclaw", "other"])
    p_bench_prepare.add_argument("--suite")
    p_bench_prepare.add_argument("--out-dir")
    p_bench_prepare.add_argument("--label", default="")
    p_bench_prepare.set_defaults(func=_cmd_bench_prepare)

    p_bench_score = bench_sp.add_parser("score", help="Score benchmark run")
    p_bench_score.add_argument("--run", required=True)
    p_bench_score.set_defaults(func=_cmd_bench_score)

    p_bench_cmp = bench_sp.add_parser("compare", help="Compare benchmark runs")
    p_bench_cmp.add_argument("--run-a", required=True)
    p_bench_cmp.add_argument("--run-b", required=True)
    p_bench_cmp.set_defaults(func=_cmd_bench_compare)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
