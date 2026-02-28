#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from urllib import error as urlerror
from urllib import request as urlrequest


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_http(method: str, url: str, body: dict[str, Any] | None = None, timeout: float = 20.0) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
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
        raw = ""
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            raw = str(e)
        parsed: Any
        try:
            parsed = json.loads(raw) if raw.strip() else {}
        except Exception:
            parsed = {"raw": raw[:1000]}
        return {"ok": False, "status_code": getattr(e, "code", None), "error": str(e), "body": parsed}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _out_path(args: argparse.Namespace) -> Path:
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    base = Path(tempfile.gettempdir()) / "rth_core" / "reports"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"channels_live_final_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"


def _check_telegram(base: str, args: argparse.Namespace) -> dict[str, Any]:
    status = _json_http("GET", base + "/api/v1/jarvis/telegram/status", timeout=args.timeout)
    out: dict[str, Any] = {"status_probe": status}
    configured = bool(((status.get("body") or {}).get("configured")))
    out["configured"] = configured
    if not configured:
        out["status"] = "warning"
        out["summary"] = "Telegram non configurato (token mancante): test live skipped"
        return out
    get_me = _json_http("GET", base + "/api/v1/jarvis/telegram/get-me", timeout=args.timeout)
    out["get_me"] = get_me
    if not get_me.get("ok") or ((get_me.get("body") or {}).get("status") not in {None, "ok"}):
        out["status"] = "fail"
        out["summary"] = "Telegram getMe fallito"
        return out
    if args.telegram_chat_id and args.allow_send:
        send = _json_http(
            "POST",
            base + "/api/v1/jarvis/telegram/send",
            {"chat_id": args.telegram_chat_id, "text": args.telegram_test_text, "timeout_sec": args.timeout},
            timeout=max(args.timeout, 30.0),
        )
        out["send_test"] = send
        if not send.get("ok") or ((send.get("body") or {}).get("status") != "ok"):
            out["status"] = "fail"
            out["summary"] = "Telegram send test fallito"
            return out
        out["status"] = "pass"
        out["summary"] = "Telegram live OK (getMe + send test)"
        return out
    out["status"] = "pass"
    out["summary"] = "Telegram configured + getMe OK (send test skipped)"
    return out


def _check_mail(base: str, args: argparse.Namespace) -> dict[str, Any]:
    status = _json_http("GET", base + "/api/v1/jarvis/mail/status", timeout=args.timeout)
    out: dict[str, Any] = {"status_probe": status}
    configured = bool(((status.get("body") or {}).get("configured")))
    out["configured"] = configured
    if not configured:
        out["status"] = "warning"
        out["summary"] = "Mail non configurato: test live skipped"
        return out
    if args.mail_poll_once:
        poll = _json_http(
            "POST",
            base + "/api/v1/jarvis/mail/poll-once",
            {"limit": int(args.mail_poll_limit)},
            timeout=max(args.timeout, 45.0),
        )
        out["poll_once"] = poll
        ok = poll.get("ok") and ((poll.get("body") or {}).get("status") in {"ok", "not_configured"})
        if not ok:
            out["status"] = "fail"
            out["summary"] = "Mail poll_once fallito"
            return out
        out["status"] = "pass"
        out["summary"] = "Mail configured + poll_once OK"
        return out
    out["status"] = "pass"
    out["summary"] = "Mail configured (poll_once skipped)"
    return out


def _check_whatsapp(base: str, args: argparse.Namespace) -> dict[str, Any]:
    status = _json_http("GET", base + "/api/v1/jarvis/whatsapp/status", timeout=args.timeout)
    body = status.get("body") or {}
    out: dict[str, Any] = {"status_probe": status}
    configured = bool(body.get("meta_configured") or body.get("twilio_configured"))
    provider = body.get("provider")
    out["configured"] = configured
    out["provider"] = provider
    if not configured:
        out["status"] = "warning"
        out["summary"] = "WhatsApp non configurato: test live skipped"
        return out
    # Meta webhook verify smoke if provider=meta and verify token exists
    if provider == "meta_cloud" and args.meta_verify_token:
        verify = _json_http(
            "GET",
            base + f"/api/v1/jarvis/whatsapp/meta/webhook?hub.mode=subscribe&hub.verify_token={args.meta_verify_token}&hub.challenge=RC1TEST",
            timeout=args.timeout,
        )
        out["meta_verify"] = verify
    if args.whatsapp_to and args.allow_send:
        send = _json_http(
            "POST",
            base + "/api/v1/jarvis/whatsapp/send",
            {"to": args.whatsapp_to, "text": args.whatsapp_test_text, "timeout_sec": args.timeout},
            timeout=max(args.timeout, 45.0),
        )
        out["send_test"] = send
        if not send.get("ok") or ((send.get("body") or {}).get("status") != "ok"):
            out["status"] = "fail"
            out["summary"] = "WhatsApp send test fallito"
            return out
        out["status"] = "pass"
        out["summary"] = "WhatsApp live OK (send test)"
        return out
    out["status"] = "pass"
    out["summary"] = "WhatsApp configured (send test skipped)"
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Core Rth channel live final checks (Telegram/Mail/WhatsApp)")
    p.add_argument("--api-base", default="http://127.0.0.1:18030")
    p.add_argument("--timeout", type=float, default=12.0)
    p.add_argument("--allow-send", action="store_true", help="Allow live outbound send tests (Telegram/WhatsApp)")
    p.add_argument("--require-all-configured", action="store_true", help="Fail if any channel is not configured")
    p.add_argument("--mail-poll-once", action="store_true", help="Run one live IMAP poll if mail is configured")
    p.add_argument("--mail-poll-limit", type=int, default=5)
    p.add_argument("--telegram-chat-id", default="", help="Optional Telegram chat_id for live send test")
    p.add_argument("--telegram-test-text", default="[RTH RC1] Telegram live test OK")
    p.add_argument("--whatsapp-to", default="", help="Optional WhatsApp destination for live send test")
    p.add_argument("--whatsapp-test-text", default="[RTH RC1] WhatsApp live test OK")
    p.add_argument("--meta-verify-token", default="", help="Optional Meta webhook verify token for GET verify smoke")
    p.add_argument("--out", default="")
    return p


def main() -> int:
    args = build_parser().parse_args()
    base = args.api_base.rstrip("/")
    report = {
        "module": "channels_live_final_check",
        "timestamp": _now(),
        "api_base": base,
        "mode": {
            "allow_send": bool(args.allow_send),
            "require_all_configured": bool(args.require_all_configured),
            "mail_poll_once": bool(args.mail_poll_once),
        },
        "expected_dedicated_secrets": {
            "telegram": ["channels/telegram/bot_token", "channels/telegram/webhook_secret"],
            "mail": ["channels/mail/imap_user", "channels/mail/imap_password", "channels/mail/shared_secret", "channels/mail/smtp_user", "channels/mail/smtp_password"],
            "whatsapp_meta": ["channels/whatsapp/meta/access_token", "channels/whatsapp/meta/verify_token"],
            "whatsapp_twilio": ["channels/whatsapp/twilio/account_sid", "channels/whatsapp/twilio/auth_token"],
        },
        "channels": {},
        "summary": {},
    }

    # API probe first.
    api_health = _json_http("GET", base + "/api/v1/health", timeout=args.timeout)
    report["api_health"] = api_health
    if not api_health.get("ok"):
        report["summary"] = {"passed": 0, "warnings": 0, "failed": 1, "overall": "fail", "reason": "api_unreachable"}
        out = _out_path(args)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"status": "fail", "report": str(out), "reason": "api_unreachable"}, ensure_ascii=False))
        return 2

    report["channels"]["telegram"] = _check_telegram(base, args)
    report["channels"]["mail"] = _check_mail(base, args)
    report["channels"]["whatsapp"] = _check_whatsapp(base, args)

    counts = {"pass": 0, "warning": 0, "fail": 0}
    for ch in report["channels"].values():
        st = str(ch.get("status") or "warning")
        if st not in counts:
            counts["warning"] += 1
        else:
            counts[st] += 1

    if args.require_all_configured:
        for name, ch in report["channels"].items():
            if not ch.get("configured"):
                counts["fail"] += 1
                report.setdefault("notes", []).append(f"{name}: not configured but require_all_configured=true")

    overall = "pass" if counts["fail"] == 0 else "fail"
    report["summary"] = {"passed": counts["pass"], "warnings": counts["warning"], "failed": counts["fail"], "overall": overall}

    out = _out_path(args)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": overall, "summary": report["summary"], "report": str(out)}, ensure_ascii=False))
    return 0 if overall == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())

