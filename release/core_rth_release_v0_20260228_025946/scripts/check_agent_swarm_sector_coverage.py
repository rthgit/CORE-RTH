import argparse
import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib import request, error


def http_json(base_url: str, path: str, method: str = "GET", body=None, timeout: float = 30.0):
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    with request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return resp.status, json.loads(raw)


def safe_call(base_url, path, method="GET", body=None, timeout=30.0):
    started = time.time()
    try:
        status, payload = http_json(base_url, path, method=method, body=body, timeout=timeout)
        return {
            "ok": True,
            "http_status": status,
            "elapsed_ms": round((time.time() - started) * 1000, 1),
            "payload": payload,
        }
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw}
        return {
            "ok": False,
            "http_status": e.code,
            "elapsed_ms": round((time.time() - started) * 1000, 1),
            "error": f"HTTPError {e.code}",
            "payload": payload,
        }
    except Exception as e:
        return {
            "ok": False,
            "http_status": None,
            "elapsed_ms": round((time.time() - started) * 1000, 1),
            "error": repr(e),
        }


def task_message(task_class: str) -> str:
    samples = {
        "chat_general": "Give a short multilingual readiness summary.",
        "coding": "Explain 3 safe refactoring steps for a Python module.",
        "planning": "Create a practical 3-step execution plan.",
        "research": "List a research approach and validation criteria.",
        "summarization": "Summarize a system status in 5 bullets.",
        "vision": "Explain how you would process an image task and what input is required.",
        "verification": "Describe a verification checklist for a release candidate.",
        "tool_calling": "Describe how to safely select and call tools with consent.",
    }
    return samples.get(task_class, f"Route explain test for task_class={task_class}")


def main():
    ap = argparse.ArgumentParser(description="Check agent swarm/sector coverage across Core Rth surfaces.")
    ap.add_argument("--api-base", default="http://127.0.0.1:18030")
    ap.add_argument("--report-dir", default="bench/results")
    ap.add_argument("--swarm-root", default=str(Path.cwd()))
    ap.add_argument("--swarm-max-projects", type=int, default=25)
    args = ap.parse_args()

    base = args.api_base.rstrip("/")
    report = {
        "suite": "agent_swarm_sector_coverage_v1",
        "timestamp": datetime.now().isoformat(),
        "api_base": base,
        "sections": {},
        "summary": {},
    }

    # Health
    health = safe_call(base, "/api/v1/health", timeout=10)
    report["sections"]["api_health"] = health
    if not health.get("ok"):
        report["summary"] = {"status": "fail", "reason": "API not reachable"}
        print(json.dumps(report, indent=2))
        return 2

    # Models catalog / task sectors
    catalog = safe_call(base, "/api/v1/models/catalog", timeout=20)
    report["sections"]["models_catalog"] = {
        "ok": catalog["ok"],
        "elapsed_ms": catalog.get("elapsed_ms"),
        "items_count": len((catalog.get("payload") or {}).get("items", []) if catalog.get("payload") else []),
        "task_classes": (catalog.get("payload") or {}).get("task_classes", []),
    }
    task_classes = list((catalog.get("payload") or {}).get("task_classes") or [])
    if not task_classes:
        task_classes = ["chat_general", "coding", "planning", "research", "summarization", "verification", "tool_calling"]

    route_results = []
    for tc in task_classes:
        body = {
            "task_class": tc,
            "message": task_message(tc),
            "privacy_mode": "local_only",
            "difficulty": "normal",
        }
        res = safe_call(base, "/api/v1/models/route/explain", method="POST", body=body, timeout=20)
        payload = res.get("payload") or {}
        route_results.append({
            "task_class": tc,
            "ok": res["ok"] and payload.get("status") == "ok",
            "elapsed_ms": res.get("elapsed_ms"),
            "selected": ((payload.get("selected") or {}).get("ref") if isinstance(payload, dict) else None),
            "status": payload.get("status") if isinstance(payload, dict) else None,
            "route_status": payload.get("route_status") if isinstance(payload, dict) else None,
            "error": res.get("error"),
        })
    report["sections"]["route_explain_task_sectors"] = route_results

    # AI Village modes (live swarm-style multi-role execution)
    village_modes = ["brainstorm", "decision", "execution"]
    village_results = []
    for mode in village_modes:
        body = {
            "prompt": f"Sector coverage check for mode={mode}. Produce a concise output.",
            "mode": mode,
            "privacy_mode": "local_only",
            "budget_cap": 2.0,
            "roles": ["researcher", "critic"],
            "allow_budget_overrun": False,
            "max_roles": 2,
            "confirm_owner": True,
            "decided_by": "owner",
            "reason": f"sector coverage village run {mode}",
        }
        res = safe_call(base, "/api/v1/models/village/run", method="POST", body=body, timeout=180)
        payload = res.get("payload") or {}
        role_results = payload.get("role_results") or []
        village_results.append({
            "mode": mode,
            "ok": res["ok"] and payload.get("status") == "ok",
            "elapsed_ms": res.get("elapsed_ms"),
            "status": payload.get("status"),
            "roles_total": len(role_results),
            "roles_ok": sum(1 for r in role_results if isinstance(r, dict) and r.get("status") == "ok"),
            "synthesis_status": ((payload.get("synthesis") or {}).get("status") if isinstance(payload, dict) else None),
            "error": res.get("error"),
        })
    report["sections"]["village_mode_coverage"] = village_results

    # Jarvis swarm orchestrator (read-only synthesis over repo root)
    swarm_body = {
        "roots": [args.swarm_root],
        "max_projects": int(args.swarm_max_projects),
        "reason": "agent swarm sector coverage validation",
    }
    swarm_run = safe_call(base, "/api/v1/jarvis/swarm/run", method="POST", body=swarm_body, timeout=180)
    swarm_payload = swarm_run.get("payload") or {}
    report["sections"]["jarvis_swarm_run"] = {
        "ok": swarm_run["ok"] and swarm_payload.get("status") == "ok",
        "elapsed_ms": swarm_run.get("elapsed_ms"),
        "status": swarm_payload.get("status"),
        "keys": sorted(list(swarm_payload.keys())) if isinstance(swarm_payload, dict) else [],
        "high_ranked_count": len((swarm_payload.get("high_ranked") or []) if isinstance(swarm_payload, dict) else []),
        "has_sublimation_plan": bool((swarm_payload.get("sublimation_plan") or []) if isinstance(swarm_payload, dict) else False),
        "error": swarm_run.get("error"),
    }

    # Guardian multilingual + channels replay unicode
    guardian_it = safe_call(base, "/api/v1/jarvis/policy?lang=it", timeout=20)
    guardian_en = safe_call(base, "/api/v1/jarvis/policy?lang=en", timeout=20)
    reqs_it = safe_call(base, "/api/v1/jarvis/permissions?lang=it", timeout=20)
    reqs_en = safe_call(base, "/api/v1/jarvis/permissions?lang=en", timeout=20)
    report["sections"]["guardian_localized"] = {
        "policy_it_ok": guardian_it["ok"],
        "policy_en_ok": guardian_en["ok"],
        "reqs_it_ok": reqs_it["ok"],
        "reqs_en_ok": reqs_en["ok"],
        "policy_it_lang": ((guardian_it.get("payload") or {}).get("localized") or {}).get("lang"),
        "policy_en_lang": ((guardian_en.get("payload") or {}).get("localized") or {}).get("lang"),
        "reqs_it_lang": (reqs_it.get("payload") or {}).get("lang"),
        "reqs_en_lang": (reqs_en.get("payload") or {}).get("lang"),
    }

    unicode_text = "/chat Ciao ✅ — English OK — Español ñáéíóú — 日本語テスト"
    tg_replay = safe_call(base, "/api/v1/jarvis/telegram/replay", method="POST", body={
        "text": unicode_text,
        "chat_id": "999000111",
        "username": "owner_test",
        "auto_reply": True,
    }, timeout=30)
    wa_replay = safe_call(base, "/api/v1/jarvis/whatsapp/replay", method="POST", body={
        "text": unicode_text,
        "from_number": "15550001111",
        "auto_reply": True,
    }, timeout=30)
    mail_replay = safe_call(base, "/api/v1/jarvis/mail/replay", method="POST", body={
        "payload": {"cmd": "status", "secret": "rth-replay-secret"},
        "from_addr": "owner@example.local",
        "subject": "[Replay Unicode]",
        "shared_secret": "rth-replay-secret",
        "allow_remote_approve": False,
    }, timeout=30)
    report["sections"]["channels_replay_unicode"] = {
        "telegram_ok": tg_replay["ok"],
        "whatsapp_ok": wa_replay["ok"],
        "mail_ok": mail_replay["ok"],
        "telegram_status": (tg_replay.get("payload") or {}).get("status"),
        "whatsapp_status": (wa_replay.get("payload") or {}).get("status"),
        "mail_status": (mail_replay.get("payload") or {}).get("status"),
    }

    # Summary
    route_ok = sum(1 for r in route_results if r["ok"])
    village_ok = sum(1 for r in village_results if r["ok"])
    checks = {
        "route_task_sectors": {"ok": route_ok == len(route_results), "passed": route_ok, "total": len(route_results)},
        "village_modes": {"ok": village_ok == len(village_results), "passed": village_ok, "total": len(village_results)},
        "jarvis_swarm": {"ok": bool(report["sections"]["jarvis_swarm_run"]["ok"])},
        "guardian_localized": {"ok": all([
            report["sections"]["guardian_localized"]["policy_it_ok"],
            report["sections"]["guardian_localized"]["policy_en_ok"],
            report["sections"]["guardian_localized"]["reqs_it_ok"],
            report["sections"]["guardian_localized"]["reqs_en_ok"],
        ])},
        "channels_replay_unicode": {"ok": all([
            report["sections"]["channels_replay_unicode"]["telegram_ok"],
            report["sections"]["channels_replay_unicode"]["whatsapp_ok"],
            report["sections"]["channels_replay_unicode"]["mail_ok"],
        ])},
    }
    report["summary"] = {
        "status": "ok" if all(v.get("ok") for v in checks.values()) else "partial",
        "checks": checks,
    }

    out_name = f"agent_swarm_sector_coverage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_dir = Path(args.report_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / out_name
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        fallback_dir = Path(tempfile.gettempdir()) / "rth_core" / "reports"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        out_path = fallback_dir / out_name
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"status": report["summary"]["status"], "report": str(out_path), "checks": report["summary"]["checks"]}, indent=2, ensure_ascii=False))
    return 0 if report["summary"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
