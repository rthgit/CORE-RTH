#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from urllib import error as urlerror
from urllib import request as urlrequest


ROOT = Path(__file__).resolve().parents[1]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _http_json(method: str, url: str, body: dict[str, Any] | None = None, timeout: float = 20.0) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urlrequest.Request(url, data=data, headers=headers, method=method)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw.strip() else {}
            return {"ok": True, "status_code": getattr(resp, "status", None), "body": parsed}
    except urlerror.HTTPError as e:
        body_txt = ""
        try:
            body_txt = e.read().decode("utf-8", errors="replace")
        except Exception:
            body_txt = str(e)
        try:
            parsed = json.loads(body_txt) if body_txt.strip() else {}
        except Exception:
            parsed = {"raw": body_txt[:1200]}
        return {"ok": False, "status_code": getattr(e, "code", None), "error": str(e), "body": parsed}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _run(cmd: list[str], timeout: float = 120.0, cwd: Path | None = None) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=str(cwd or ROOT), capture_output=True, text=True, timeout=timeout)
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        parsed: Any
        try:
            parsed = json.loads(out) if out else {}
        except Exception:
            parsed = None
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "cmd": cmd,
            "stdout": out[:8000],
            "stderr": err[:4000],
            "json": parsed,
        }
    except Exception as e:
        return {"ok": False, "cmd": cmd, "error": str(e)}


def _add_check(report: dict[str, Any], check_id: str, status: str, summary: str, data: dict[str, Any] | None = None, severity: str = "error") -> None:
    report["checks"].append(
        {
            "id": check_id,
            "status": status,  # pass|warn|fail
            "severity": severity,
            "summary": summary,
            "data": data or {},
        }
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Core Rth Release Gate RC1 (one-click)")
    p.add_argument("--api-base", default="http://127.0.0.1:18030")
    p.add_argument("--start-api-if-needed", action="store_true")
    p.add_argument("--api-port", type=int, default=18030)
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--skip-pytest", action="store_true")
    p.add_argument("--strict-live-channels", action="store_true", help="Fail if channels live final check reports warnings/not configured")
    p.add_argument("--allow-live-channel-send", action="store_true", help="Allow outbound send tests in channel live final check")
    p.add_argument("--telegram-chat-id", default="")
    p.add_argument("--whatsapp-to", default="")
    p.add_argument("--mail-poll-once", action="store_true")
    p.add_argument("--out", default="")
    return p


def main() -> int:
    args = build_parser().parse_args()
    base = args.api_base.rstrip("/")
    report: dict[str, Any] = {
        "module": "release_gate_rc1",
        "timestamp": _now(),
        "api_base": base,
        "checks": [],
        "artifacts": {},
        "summary": {},
    }

    # API health / startup
    api_health = _http_json("GET", base + "/api/v1/health", timeout=args.timeout)
    if (not api_health.get("ok")) and args.start_api_if_needed:
        started = _run([sys.executable, "scripts/rth.py", "api", "start", "--port", str(args.api_port)], timeout=45)
        report["artifacts"]["api_start_attempt"] = started
        api_health = _http_json("GET", base + "/api/v1/health", timeout=max(args.timeout, 5.0))
    if api_health.get("ok"):
        _add_check(report, "api_health", "pass", "API health endpoint OK", api_health)
    else:
        _add_check(report, "api_health", "fail", "API health endpoint unreachable", api_health)

    # Core status checks
    for cid, path in [
        ("models_status", "/api/v1/models/status"),
        ("secrets_status", "/api/v1/secrets/status"),
        ("plugins_status", "/api/v1/plugins/status"),
        ("guardian_severity", "/api/v1/jarvis/guardian/severity"),
        ("telegram_status", "/api/v1/jarvis/telegram/status"),
        ("whatsapp_status", "/api/v1/jarvis/whatsapp/status"),
        ("mail_status", "/api/v1/jarvis/mail/status"),
    ]:
        res = _http_json("GET", base + path, timeout=args.timeout)
        if res.get("ok"):
            _add_check(report, cid, "pass", f"{cid} endpoint OK", res, severity="warn" if cid.endswith("_status") and cid in {"telegram_status", "whatsapp_status", "mail_status"} else "error")
        else:
            _add_check(report, cid, "fail", f"{cid} endpoint failed", res)

    providers = _http_json("GET", base + "/api/v1/models/providers", timeout=args.timeout)
    if providers.get("ok"):
        items = (providers.get("body") or {}).get("items") or []
        groq_enabled = [x for x in items if isinstance(x, dict) and str(x.get("provider_type") or "").lower() == "groq" and bool(x.get("enabled"))]
        if groq_enabled:
            _add_check(report, "groq_provider_ready", "pass", f"Groq provider enabled ({len(groq_enabled)})", {"ok": True, "count": len(groq_enabled), "items": groq_enabled[:3]})
        else:
            _add_check(report, "groq_provider_ready", "warn", "No enabled Groq provider configured", providers, severity="warn")
    else:
        _add_check(report, "groq_provider_ready", "warn", "Unable to verify Groq provider state", providers, severity="warn")

    # llama.cpp local fallback status
    llama = _run([sys.executable, "scripts/run_llama_cpp_server.py", "status"], timeout=20)
    if llama.get("ok") and ((llama.get("json") or {}).get("status") == "ok"):
        _add_check(report, "llama_cpp_status", "pass", "llama.cpp local fallback running", llama)
    else:
        _add_check(report, "llama_cpp_status", "warn", "llama.cpp local fallback not running", llama, severity="warn")

    # Guardian gate (allow empty root audits for RC1 local packaging gate)
    guard_gate = _run(
        [sys.executable, "scripts/rth.py", "guardian", "audit", "--gate", "--allow-empty-root-audits", "--limit", "5"],
        timeout=45,
    )
    if guard_gate.get("ok"):
        _add_check(report, "guardian_release_gate", "pass", "Guardian release gate passed", guard_gate)
    else:
        _add_check(report, "guardian_release_gate", "fail", "Guardian release gate failed", guard_gate)

    # Plugin batch healthcheck P0
    batch = _http_json(
        "POST",
        base + "/api/v1/plugins/healthcheck/batch",
        {
            "priority_only": True,
            "enabled_only": True,
            "include_not_configured": False,
            "limit": 20,
            "timeout_sec": 1.5,
            "reason": "RC1 gate plugin batch healthcheck (enabled only)",
            "confirm_owner": True,
            "decided_by": "owner",
        },
        timeout=max(args.timeout, 60.0),
    )
    if batch.get("ok") and ((batch.get("body") or {}).get("status") == "ok"):
        counts = ((batch.get("body") or {}).get("counts") or {})
        errors = int(counts.get("error", 0))
        denied = int(counts.get("denied", 0))
        proposal_only = int(counts.get("proposal_only", 0))
        other = int(counts.get("other", 0))
        problem_total = errors + denied + proposal_only + other
        status = "warn" if problem_total > 0 else "pass"
        _add_check(report, "plugins_healthcheck_batch_p0", status, f"Enabled P0 plugin batch healthcheck completed (problems={problem_total}, errors={errors})", batch, severity="warn")
    else:
        _add_check(report, "plugins_healthcheck_batch_p0", "fail", "P0 plugin batch healthcheck failed", batch)

    # Replay endpoints (no creds, no network)
    replay_calls = [
        ("replay_telegram", "/api/v1/jarvis/telegram/replay", {"text": "/status", "chat_id": "999000111", "username": "owner_test", "auto_reply": True}),
        ("replay_whatsapp", "/api/v1/jarvis/whatsapp/replay", {"text": "/status", "from_number": "15550001111", "auto_reply": True}),
        ("replay_mail", "/api/v1/jarvis/mail/replay", {"payload": {"cmd": "status", "secret": "rth-replay-secret"}, "from_addr": "owner@example.local", "shared_secret": "rth-replay-secret", "allow_remote_approve": False}),
    ]
    for cid, path, payload in replay_calls:
        res = _http_json("POST", base + path, payload, timeout=max(args.timeout, 60.0))
        if res.get("ok"):
            _add_check(report, cid, "pass", f"{cid} OK", res)
        else:
            _add_check(report, cid, "fail", f"{cid} failed", res)

    # pytest replay+secrets fixtures
    if args.skip_pytest:
        _add_check(report, "pytest_replay_endpoints", "warn", "pytest skipped by flag", {}, severity="warn")
    else:
        py = _run([sys.executable, "-m", "pytest", "-q", "scripts/test_replay_endpoints.py", "-p", "no:cacheprovider"], timeout=180)
        if py.get("ok"):
            _add_check(report, "pytest_replay_endpoints", "pass", "pytest replay/secrets suite passed", py)
        else:
            _add_check(report, "pytest_replay_endpoints", "fail", "pytest replay/secrets suite failed", py)

    # Channel live final check (warnings allowed unless strict)
    ch_cmd = [sys.executable, "scripts/channels_live_final_check.py", "--api-base", base]
    if args.allow_live_channel_send:
        ch_cmd.append("--allow-send")
    if args.strict_live_channels:
        ch_cmd.append("--require-all-configured")
    if args.telegram_chat_id:
        ch_cmd.extend(["--telegram-chat-id", args.telegram_chat_id])
    if args.whatsapp_to:
        ch_cmd.extend(["--whatsapp-to", args.whatsapp_to])
    if args.mail_poll_once:
        ch_cmd.append("--mail-poll-once")
    ch = _run(ch_cmd, timeout=180)
    ch_json = ch.get("json") if isinstance(ch.get("json"), dict) else None
    ch_status = "warn"
    if ch.get("ok"):
        if ch_json and str(ch_json.get("status")) == "pass":
            ch_status = "pass"
        else:
            ch_status = "warn"
    else:
        ch_status = "fail" if args.strict_live_channels else "warn"
    _add_check(report, "channels_live_final_check", ch_status, "Channel live final check executed", ch, severity="warn" if not args.strict_live_channels else "error")
    if ch_json and ch_json.get("report"):
        report["artifacts"]["channels_live_report"] = ch_json["report"]

    # Packaging / release bundle build
    pack = _run([sys.executable, "scripts/build_release_bundle.py"], timeout=300)
    if pack.get("ok"):
        _add_check(report, "release_bundle_build", "pass", "Release bundle build OK", pack)
        stdout = pack.get("stdout", "")
        for line in stdout.splitlines():
            if "Release bundle created:" in line:
                report["artifacts"]["release_bundle_dir"] = line.split("Release bundle created:", 1)[1].strip()
                break
    else:
        _add_check(report, "release_bundle_build", "fail", "Release bundle build failed", pack)

    # Onboarding zero-friction smoke (uses existing runtime)
    onboard = _run([sys.executable, "scripts/onboard_zero_friction.py", "--api-base", base], timeout=120)
    if onboard.get("ok"):
        _add_check(report, "onboard_zero_friction", "pass", "Onboarding zero-friction check passed", onboard)
    else:
        # non-fatal only if API missing; but API should be present by now, so mark fail
        _add_check(report, "onboard_zero_friction", "fail", "Onboarding zero-friction check failed", onboard)

    # Aggregate.
    failed = [c for c in report["checks"] if c["status"] == "fail"]
    warned = [c for c in report["checks"] if c["status"] == "warn"]
    passed = [c for c in report["checks"] if c["status"] == "pass"]
    report["summary"] = {
        "overall": "pass" if not failed else "fail",
        "passed": len(passed),
        "warnings": len(warned),
        "failed": len(failed),
        "failed_ids": [c["id"] for c in failed],
        "warning_ids": [c["id"] for c in warned],
        "strict_live_channels": bool(args.strict_live_channels),
    }

    out_path = Path(args.out) if args.out else (Path(tempfile.gettempdir()) / "rth_core" / "reports" / f"release_gate_rc1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["summary"]["overall"], "summary": report["summary"], "report": str(out_path), "artifacts": report.get("artifacts", {})}, ensure_ascii=False))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())

