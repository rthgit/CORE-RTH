#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from urllib import error as urlerror
from urllib import request as urlrequest


ROOT = Path(__file__).resolve().parents[1]
ENV_QUICKSTART = ROOT / ".env.rth.quickstart.local"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _json_http(method: str, url: str, body: dict[str, Any] | None = None, timeout: float = 12.0) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urlrequest.Request(url, headers=headers, data=data, method=method)
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw.strip() else {}
            return {"ok": True, "status_code": getattr(resp, "status", None), "body": parsed}
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
        return {"ok": False, "status_code": getattr(e, "code", None), "error": str(e), "body": parsed if parsed is not None else body[:1000]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _run_json(cmd: list[str], cwd: Path, timeout: float = 60.0) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        out = (proc.stdout or "").strip()
        parsed: Any
        try:
            parsed = json.loads(out) if out else {}
        except Exception:
            parsed = {"stdout": out[:4000], "stderr": (proc.stderr or "")[:2000]}
        return {"ok": proc.returncode == 0, "returncode": proc.returncode, "cmd": cmd, "body": parsed, "stderr": (proc.stderr or "")[:2000]}
    except Exception as e:
        return {"ok": False, "cmd": cmd, "error": str(e)}


def _load_quickstart_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Core Rth zero-friction onboarding check/bootstrap")
    p.add_argument("--api-base", default="http://127.0.0.1:18030")
    p.add_argument("--start-api-if-needed", action="store_true")
    p.add_argument("--start-llama-if-needed", action="store_true")
    p.add_argument("--port", type=int, default=18030)
    p.add_argument("--timeout", type=float, default=12.0)
    p.add_argument("--out", default="")
    return p


def main() -> int:
    args = build_parser().parse_args()
    base = args.api_base.rstrip("/")
    report: dict[str, Any] = {
        "module": "onboard_zero_friction",
        "timestamp": _now(),
        "repo_root": str(ROOT),
        "api_base": base,
        "checks": {},
        "actions": [],
        "next_steps": [],
        "summary": {},
    }

    qenv = _load_quickstart_env(ENV_QUICKSTART)
    report["checks"]["quickstart_env"] = {
        "exists": ENV_QUICKSTART.exists(),
        "path": str(ENV_QUICKSTART),
        "has_groq_key": bool(qenv.get("GROQ_API_KEY")),
        "has_llama_model_path": bool(qenv.get("RTH_LLAMA_CPP_MODEL_PATH")),
        "llama_model_path": qenv.get("RTH_LLAMA_CPP_MODEL_PATH", ""),
    }
    if qenv.get("RTH_LLAMA_CPP_MODEL_PATH"):
        p = Path(os.path.expandvars(qenv["RTH_LLAMA_CPP_MODEL_PATH"]))
        report["checks"]["mini_gguf"] = {"path": str(p), "exists": p.exists(), "size_bytes": (p.stat().st_size if p.exists() else None)}
    else:
        report["checks"]["mini_gguf"] = {"path": "", "exists": False}

    llama = _run_json([sys.executable, "scripts/run_llama_cpp_server.py", "status"], ROOT, timeout=20)
    report["checks"]["llama_cpp_status"] = llama
    llama_ok = bool(llama.get("ok")) and str((llama.get("body") or {}).get("status")) == "ok"
    if (not llama_ok) and args.start_llama_if_needed:
        started = _run_json([sys.executable, "scripts/run_llama_cpp_server.py", "start", "--daemon"], ROOT, timeout=30)
        report["actions"].append({"action": "start_llama_cpp_server", "result": started})
        llama = _run_json([sys.executable, "scripts/run_llama_cpp_server.py", "status"], ROOT, timeout=20)
        report["checks"]["llama_cpp_status"] = llama
        llama_ok = bool(llama.get("ok")) and str((llama.get("body") or {}).get("status")) == "ok"

    api_health = _json_http("GET", base + "/api/v1/health", timeout=args.timeout)
    report["checks"]["api_health"] = api_health
    api_ok = bool(api_health.get("ok"))
    if (not api_ok) and args.start_api_if_needed:
        started = _run_json([sys.executable, "scripts/rth.py", "api", "start", "--port", str(args.port)], ROOT, timeout=30)
        report["actions"].append({"action": "start_api", "result": started})
        api_health = _json_http("GET", base + "/api/v1/health", timeout=max(args.timeout, 5.0))
        report["checks"]["api_health"] = api_health
        api_ok = bool(api_health.get("ok"))

    if api_ok:
        for name, path in [
            ("models_status", "/api/v1/models/status"),
            ("secrets_status", "/api/v1/secrets/status"),
            ("plugins_status", "/api/v1/plugins/status"),
            ("telegram_status", "/api/v1/jarvis/telegram/status"),
            ("whatsapp_status", "/api/v1/jarvis/whatsapp/status"),
            ("mail_status", "/api/v1/jarvis/mail/status"),
        ]:
            report["checks"][name] = _json_http("GET", base + path, timeout=args.timeout)

        report["checks"]["models_reload"] = _json_http("POST", base + "/api/v1/models/reload", {"reselect_path": True}, timeout=args.timeout)
        report["checks"]["local_chat_replay_smoke"] = _json_http(
            "POST",
            base + "/api/v1/jarvis/telegram/replay",
            {"text": "/status", "chat_id": "999000111", "username": "owner_test", "auto_reply": True},
            timeout=max(args.timeout, 30.0),
        )

    # Suggestions / next steps.
    report["next_steps"] = [
        "Apri UI: http://127.0.0.1:18030/ui/ (tab Secrets+Replay per test senza credenziali)",
        "Esegui gate RC1: python scripts/release_gate_rc1.py",
        "Configura credenziali dedicate nei secrets (non in .env) per Telegram/Mail/WhatsApp",
        "Esegui test canali live: python scripts/channels_live_final_check.py --require-all-configured [--allow-send ...]",
    ]

    failures = []
    warnings = []
    if not report["checks"]["quickstart_env"]["exists"]:
        failures.append("quickstart_env_missing")
    if not api_ok:
        failures.append("api_unreachable")
    if not llama_ok:
        warnings.append("llama_cpp_not_running")
    if api_ok:
        for ch in ("telegram_status", "whatsapp_status", "mail_status"):
            row = report["checks"].get(ch, {})
            if not row.get("ok"):
                warnings.append(f"{ch}_endpoint_error")
    report["summary"] = {
        "overall": "pass" if not failures else "fail",
        "failures": failures,
        "warnings": warnings,
        "api_ok": api_ok,
        "llama_cpp_ok": llama_ok,
    }

    out_path = Path(args.out) if args.out else (Path(tempfile.gettempdir()) / "rth_core" / "reports" / f"onboard_zero_friction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["summary"]["overall"], "summary": report["summary"], "report": str(out_path)}, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())

