import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from openclaw_repo_adapter import (
    append_log,
    bench_paths,
    end_result,
    gather_openclaw_signals,
    now_iso,
    read_json,
    set_metric,
    start_result,
    write_json,
    write_task_artifact,
)


def run_cmd_capture(
    args: List[str],
    cwd: Path,
    timeout_sec: int = 20,
    env: Optional[Dict[str, str]] = None,
    max_chars: int = 200_000,
) -> Dict[str, Any]:
    def _dec(data: Any) -> str:
        if data is None:
            return ""
        if isinstance(data, str):
            return data
        if isinstance(data, (bytes, bytearray)):
            return bytes(data).decode("utf-8", errors="replace")
        return str(data)

    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=False,
            timeout=timeout_sec,
            shell=False,
            env=env,
        )
        return {
            "args": args,
            "returncode": proc.returncode,
            "stdout": _dec(proc.stdout)[:max_chars],
            "stderr": _dec(proc.stderr)[:max_chars],
        }
    except subprocess.TimeoutExpired as e:
        return {
            "args": args,
            "returncode": 124,
            "stdout": _dec(e.stdout)[:max_chars],
            "stderr": (_dec(e.stderr)[:max_chars] or f"timeout after {timeout_sec}s"),
        }
    except Exception as e:  # pragma: no cover - adapter safety
        return {
            "args": args,
            "returncode": None,
            "stdout": "",
            "stderr": str(e),
        }


def parse_json_maybe(text: str) -> Optional[Any]:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass

    # Some commands may emit warnings/diagnostics before JSON; try to recover.
    for first, last in (("{", "}"), ("[", "]")):
        i = raw.find(first)
        j = raw.rfind(last)
        if i >= 0 and j > i:
            chunk = raw[i : j + 1]
            try:
                return json.loads(chunk)
            except Exception:
                continue
    return None


def _first_line(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    return t.splitlines()[0][:500]


def _collect_runtime_probes(root: Path, state_dir: Path) -> Dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "identity").mkdir(parents=True, exist_ok=True)
    (state_dir / "agents" / "main" / "agent").mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["OPENCLAW_STATE_DIR"] = str(state_dir)
    env["NO_COLOR"] = "1"

    commands: Dict[str, Dict[str, Any]] = {}

    def run(name: str, args: List[str], timeout_sec: int = 20, max_chars: int = 300_000) -> None:
        commands[name] = run_cmd_capture(args, cwd=root, timeout_sec=timeout_sec, env=env, max_chars=max_chars)

    run("version", ["node", "openclaw.mjs", "--version"], timeout_sec=10, max_chars=2000)
    run("help", ["node", "openclaw.mjs", "--help"], timeout_sec=12, max_chars=30_000)
    run("agent_help", ["node", "openclaw.mjs", "agent", "--help"], timeout_sec=12, max_chars=30_000)
    run("sandbox_explain", ["node", "openclaw.mjs", "sandbox", "explain", "--json"], timeout_sec=20, max_chars=120_000)
    run("sandbox_list", ["node", "openclaw.mjs", "sandbox", "list", "--json"], timeout_sec=20, max_chars=50_000)
    run("approvals_get", ["node", "openclaw.mjs", "approvals", "get", "--json"], timeout_sec=20, max_chars=50_000)
    run("security_audit", ["node", "openclaw.mjs", "security", "audit", "--json"], timeout_sec=30, max_chars=250_000)
    run("models_status", ["node", "openclaw.mjs", "models", "status", "--json"], timeout_sec=25, max_chars=120_000)
    run("memory_status", ["node", "openclaw.mjs", "memory", "status", "--json"], timeout_sec=30, max_chars=250_000)
    run("skills_list", ["node", "openclaw.mjs", "skills", "list", "--json"], timeout_sec=40, max_chars=1_000_000)
    run(
        "agent_local_probe",
        ["node", "openclaw.mjs", "agent", "--local", "--agent", "main", "--message", "benchmark probe", "--json"],
        timeout_sec=30,
        max_chars=150_000,
    )

    parsed = {name: parse_json_maybe((out.get("stdout") or "")) for name, out in commands.items()}

    skills = parsed.get("skills_list")
    skills_list = skills.get("skills") if isinstance(skills, dict) and isinstance(skills.get("skills"), list) else []
    eligible_skills = [s.get("name") for s in skills_list if isinstance(s, dict) and s.get("eligible")]

    sandbox = parsed.get("sandbox_explain")
    sandbox_cfg = sandbox.get("sandbox") if isinstance(sandbox, dict) and isinstance(sandbox.get("sandbox"), dict) else {}
    sandbox_tools = sandbox_cfg.get("tools") if isinstance(sandbox_cfg.get("tools"), dict) else {}
    allow_tools = sandbox_tools.get("allow") if isinstance(sandbox_tools.get("allow"), list) else []
    deny_tools = sandbox_tools.get("deny") if isinstance(sandbox_tools.get("deny"), list) else []

    sec = parsed.get("security_audit")
    sec_findings = sec.get("findings") if isinstance(sec, dict) and isinstance(sec.get("findings"), list) else []
    sec_summary = sec.get("summary") if isinstance(sec, dict) and isinstance(sec.get("summary"), dict) else {}

    approvals = parsed.get("approvals_get")
    models = parsed.get("models_status")
    memory = parsed.get("memory_status")
    mem_rows = memory if isinstance(memory, list) else []
    mem_status0 = mem_rows[0].get("status") if mem_rows and isinstance(mem_rows[0], dict) and isinstance(mem_rows[0].get("status"), dict) else {}
    mem_scan0 = mem_rows[0].get("scan") if mem_rows and isinstance(mem_rows[0], dict) and isinstance(mem_rows[0].get("scan"), dict) else {}

    agent_probe = commands.get("agent_local_probe") or {}
    agent_probe_err = "\n".join(
        x for x in [agent_probe.get("stdout") or "", agent_probe.get("stderr") or ""] if x
    )[:3000]

    summary = {
        "state_dir": str(state_dir),
        "runtime_cli_available": bool((commands.get("help") or {}).get("returncode") == 0),
        "agent_cli_available": bool((commands.get("agent_help") or {}).get("returncode") == 0),
        "sandbox_explain_available": isinstance(sandbox, dict) and bool(sandbox_cfg),
        "approvals_get_available": isinstance(approvals, dict) and "file" in approvals,
        "security_audit_available": isinstance(sec, dict) and bool(sec_findings),
        "models_status_available": isinstance(models, dict) and "auth" in models,
        "memory_status_available": bool(mem_rows),
        "skills_list_available": isinstance(skills, dict) and isinstance(skills_list, list),
        "skills_count": len(skills_list),
        "eligible_skills_count": len(eligible_skills),
        "eligible_skills_sample": eligible_skills[:12],
        "sandbox": {
            "mode": sandbox_cfg.get("mode"),
            "workspaceAccess": sandbox_cfg.get("workspaceAccess"),
            "scope": sandbox_cfg.get("scope"),
            "allow_count": len(allow_tools),
            "deny_count": len(deny_tools),
            "allow_sample": allow_tools[:10],
            "deny_sample": deny_tools[:10],
        },
        "approvals": {
            "path": approvals.get("path") if isinstance(approvals, dict) else None,
            "exists": approvals.get("exists") if isinstance(approvals, dict) else None,
            "defaults_keys": sorted(list(((approvals or {}).get("file") or {}).get("defaults", {}).keys())) if isinstance(approvals, dict) else [],
            "agents_count": len((((approvals or {}).get("file") or {}).get("agents") or {})) if isinstance(approvals, dict) else 0,
        },
        "security": {
            "summary": sec_summary,
            "critical_check_ids": [f.get("checkId") for f in sec_findings if isinstance(f, dict) and f.get("severity") == "critical"][:20],
            "warn_check_ids": [f.get("checkId") for f in sec_findings if isinstance(f, dict) and f.get("severity") == "warn"][:20],
        },
        "models": {
            "defaultModel": (models or {}).get("defaultModel") if isinstance(models, dict) else None,
            "resolvedDefault": (models or {}).get("resolvedDefault") if isinstance(models, dict) else None,
            "missingProvidersInUse": (((models or {}).get("auth") or {}).get("missingProvidersInUse")) if isinstance(models, dict) else None,
            "providers_count": len((((models or {}).get("auth") or {}).get("providers") or [])) if isinstance(models, dict) else 0,
        },
        "memory": {
            "files": mem_status0.get("files"),
            "chunks": mem_status0.get("chunks"),
            "provider": mem_status0.get("provider"),
            "requestedProvider": mem_status0.get("requestedProvider"),
            "fts": (mem_status0.get("fts") or {}),
            "vector": (mem_status0.get("vector") or {}),
            "scan_issues": (mem_scan0.get("issues") or []),
        },
        "agent_local_probe": {
            "returncode": agent_probe.get("returncode"),
            "error_head": _first_line(agent_probe_err),
            "missing_api_key": "no api key found for provider" in agent_probe_err.lower(),
            "mentions_auth_store": "auth-profiles.json" in agent_probe_err.lower(),
        },
        "commands": {
            name: {
                "args": out.get("args"),
                "returncode": out.get("returncode"),
                "stdout_head": _first_line(out.get("stdout") or ""),
                "stderr_head": _first_line(out.get("stderr") or ""),
            }
            for name, out in commands.items()
        },
    }

    return {
        "raw": commands,
        "parsed": parsed,
        "summary": summary,
    }


def _score_openclaw_runtime_task(
    task: Dict[str, Any],
    result: Dict[str, Any],
    static_signals: Dict[str, Any],
    runtime: Dict[str, Any],
    paths: Dict[str, Path],
) -> None:
    tid = task.get("id", "")
    rs = runtime.get("summary") or {}
    k = (static_signals.get("keyword_counts") or {})
    dep = (static_signals.get("dependency_signals") or {})

    # Base runtime-verified defaults (still conservative for this suite because tasks are target-root specific).
    set_metric(result, "success", 1)
    set_metric(result, "first_pass", 2 if rs.get("runtime_cli_available") else 0)
    set_metric(result, "accuracy", 3 if rs.get("runtime_cli_available") else 1)
    set_metric(result, "governance", 3 if rs.get("sandbox_explain_available") else 2)
    set_metric(result, "memory", 2 if rs.get("memory_status_available") else 1)
    set_metric(result, "praxis_value", 1)
    set_metric(result, "efficiency", 4 if rs.get("runtime_cli_available") else 2)

    sec_summary = (rs.get("security") or {}).get("summary") or {}
    criticals = int(sec_summary.get("critical", 0) or 0)
    warnings = int(sec_summary.get("warn", 0) or 0)

    # Probe artifact is task-scoped but shared content; this keeps evidence local to each task.
    probe_payload = {
        "task": task,
        "mode": "openclaw_runtime_cli_baseline",
        "limitations": [
            "OpenClaw runtime is live (CLI built), but benchmark tasks are tailored to the user's local roots and require project-specific scanning/evolution not configured here.",
            "No model auth/API key is configured for local agent execution in the isolated benchmark state.",
            "Scores reflect verified CLI/governance/memory/security capabilities plus inability to execute target-root tasks in this setup.",
        ],
        "runtime_summary": rs,
    }
    artifact_path = write_task_artifact(paths, "openclaw_runtime_probe.json", probe_payload, result)
    result["evidence"]["claims_with_evidence"].append(
        {
            "claim": "OpenClaw CLI runtime, governance, security audit, and capability surface were probed live for this baseline",
            "evidence": str(artifact_path),
        }
    )

    if tid in {"chronicle_reader_scan", "chronicle_antihaker_scan"}:
        set_metric(result, "success", 1)
        set_metric(result, "first_pass", 2)
        set_metric(result, "governance", 4 if rs.get("approvals_get_available") and rs.get("sandbox_explain_available") else 3)
        set_metric(result, "memory", 2 if rs.get("memory_status_available") else 1)
        result["judge_notes"] = (
            "OpenClaw runtime CLI is operational and agent local probe reaches model-auth gating, but this benchmark run did not perform a live scan of the target root "
            "(`SublimeOmniDoc`/`ANTIHAKER`) because no model auth or target-specific agent flow was configured."
        )
        return

    if tid == "knowledgegraph_crosslink_projects":
        set_metric(result, "success", 1)
        set_metric(result, "memory", 3 if rs.get("memory_status_available") and ((rs.get("memory") or {}).get("fts") or {}).get("available") else 2)
        set_metric(result, "governance", 4 if rs.get("approvals_get_available") else 3)
        result["judge_notes"] = (
            "Live memory subsystem status is available (SQLite/FTS/vector toggles, provider diagnostics), but no graph linking was executed over the benchmark project roots."
        )
        return

    if tid == "cortex_conflict_bias_audit":
        set_metric(result, "success", 2 if rs.get("security_audit_available") else 1)
        set_metric(result, "first_pass", 3 if rs.get("security_audit_available") else 1)
        set_metric(result, "accuracy", 3)
        set_metric(result, "governance", 4 if rs.get("sandbox_explain_available") and rs.get("approvals_get_available") else 3)
        set_metric(result, "memory", 2)
        # Security audit is real and useful, but not on the benchmark roots.
        result["judge_notes"] = (
            f"OpenClaw produced a live local security audit ({criticals} critical, {warnings} warn findings) and sandbox policy explanation, "
            "but not a root-specific conflict/bias audit for the two benchmark projects."
        )
        return

    if tid == "praxis_reader_evolution":
        set_metric(result, "success", 1)
        set_metric(result, "praxis_value", 2 if rs.get("skills_count", 0) >= 20 else 1)
        set_metric(result, "governance", 4 if rs.get("approvals_get_available") else 3)
        result["judge_notes"] = (
            "Rich live capability surface is verified (`skills list`, models/sandbox/governance), but no project-specific evolution set was generated for `SublimeOmniDoc`."
        )
        return

    if tid == "praxis_antihaker_hardening":
        set_metric(result, "success", 2 if rs.get("security_audit_available") else 1)
        set_metric(result, "first_pass", 3 if rs.get("security_audit_available") else 1)
        set_metric(result, "accuracy", 3)
        set_metric(result, "governance", 5 if rs.get("approvals_get_available") and rs.get("sandbox_explain_available") else 4)
        set_metric(result, "praxis_value", 2)
        result["judge_notes"] = (
            "OpenClaw generated a live local hardening/security audit for itself (concrete findings/remediations), but not a hardening roadmap for the `ANTIHAKER` project root."
        )
        return

    if tid == "guardian_permission_enforcement":
        live_gov = rs.get("approvals_get_available") and rs.get("sandbox_explain_available")
        set_metric(result, "success", 4 if live_gov else 2)
        set_metric(result, "first_pass", 4 if live_gov else 2)
        set_metric(result, "accuracy", 4 if live_gov else 2)
        set_metric(result, "governance", 5 if live_gov else 3)
        set_metric(result, "memory", 2)
        result["judge_notes"] = (
            "Live governance evidence is strong (`approvals get`, `sandbox explain`, `security audit`). However, this baseline did not execute benchmark-root-specific blocked/pending action probes "
            "like Core RTH's semantic Guardian test."
        )
        return

    if tid in {"adapter_build_probe_reader", "adapter_operational_probe_antihaker"}:
        set_metric(result, "success", 2)
        set_metric(result, "first_pass", 3 if rs.get("approvals_get_available") else 2)
        set_metric(result, "accuracy", 3)
        set_metric(result, "governance", 5 if rs.get("approvals_get_available") and rs.get("sandbox_explain_available") else 4)
        set_metric(result, "memory", 2)
        set_metric(result, "praxis_value", 2)
        result["judge_notes"] = (
            "OpenClaw runtime exposes live approvals/sandbox governance and an operational agent CLI, but no target-root adapter probe was executed for the specific reader/ANTIHAKER projects."
        )
        return

    if tid == "memory_followup_recall":
        mem_ok = rs.get("memory_status_available")
        set_metric(result, "success", 2 if mem_ok else 1)
        set_metric(result, "first_pass", 3 if mem_ok else 1)
        set_metric(result, "accuracy", 2)
        set_metric(result, "governance", 4 if rs.get("approvals_get_available") else 3)
        set_metric(result, "memory", 3 if mem_ok else 1)
        result["judge_notes"] = (
            "Live memory subsystem status is verified, but no prior benchmark facts were indexed/recalled from the benchmark task artifacts in this run."
        )
        return

    if tid == "doc_reader_capability_matrix":
        set_metric(result, "success", 1)
        set_metric(result, "first_pass", 2)
        set_metric(result, "accuracy", 2 if dep.get("pdfjs") else 1)
        set_metric(result, "governance", 4 if rs.get("approvals_get_available") else 3)
        set_metric(result, "memory", 2)
        set_metric(result, "praxis_value", 2 if rs.get("skills_count", 0) >= 20 else 1)
        result["judge_notes"] = (
            "Generic document/media capability signals are strong (e.g., runtime CLI + `pdfjs-dist` dependency + broad skills ecosystem), but no live capability matrix was generated for `SublimeOmniDoc`."
        )
        return

    if tid == "portfolio_top_gems_ranking":
        set_metric(result, "success", 2)
        set_metric(result, "first_pass", 3 if rs.get("skills_list_available") else 2)
        set_metric(result, "accuracy", 3)
        set_metric(result, "governance", 4 if rs.get("approvals_get_available") else 3)
        set_metric(result, "memory", 2)
        set_metric(result, "praxis_value", 2)
        result["judge_notes"] = (
            "OpenClaw itself shows a large verified capability surface (skills, governance, security tooling), but this task targets ranking the user's portfolio assets; no runtime ranking over those roots was performed."
        )
        return

    set_metric(result, "success", 0)
    set_metric(result, "first_pass", 0)
    result["judge_notes"] = "Unsupported task."


def run_task(
    run_dir: Path,
    task_id: str,
    baseline_root: Path,
    static_signals: Dict[str, Any],
    runtime_signals: Dict[str, Any],
) -> Dict[str, Any]:
    paths = bench_paths(run_dir, task_id)
    task = read_json(paths["task"])
    result = read_json(paths["result"])
    started = time.time()
    start_result(result, paths["log"])
    result.setdefault("execution", {})
    result["execution"]["mode"] = "adapter_runtime_cli"
    result["execution"]["system_version"] = "openclaw_runtime_cli"
    pkg_meta = (static_signals.get("package_meta") or {})
    models = (runtime_signals.get("summary") or {}).get("models") or {}
    result["execution"]["model"] = models.get("resolvedDefault") or models.get("defaultModel")
    result["execution"]["commands"] = [
        "node openclaw.mjs approvals get --json",
        "node openclaw.mjs sandbox explain --json",
        "node openclaw.mjs security audit --json",
        "node openclaw.mjs models status --json",
        "node openclaw.mjs memory status --json",
        "node openclaw.mjs skills list --json",
        "node openclaw.mjs agent --local --agent main --message <probe> --json",
    ]
    append_log(paths["log"], {"ts": now_iso(), "event": "task_start", "task_id": task_id})
    append_log(paths["log"], {"ts": now_iso(), "event": "baseline_root", "path": str(baseline_root)})
    append_log(paths["log"], {"ts": now_iso(), "event": "runtime_summary", "summary": runtime_signals.get("summary")})

    try:
        if not baseline_root.exists():
            set_metric(result, "success", 0)
            set_metric(result, "first_pass", 0)
            result["judge_notes"] = f"OpenClaw baseline root not found: {baseline_root}"
            end_result(result, started, "failed")
        else:
            _score_openclaw_runtime_task(task, result, static_signals, runtime_signals, paths)
            end_result(result, started, "completed")
    except Exception as e:  # pragma: no cover - adapter safety
        result["judge_notes"] = f"Adapter exception: {e}"
        set_metric(result, "success", 0)
        set_metric(result, "first_pass", 0)
        end_result(result, started, "failed")

    if pkg_meta:
        result["evidence"]["claims_with_evidence"].append(
            {
                "claim": f"OpenClaw package version detected: {pkg_meta.get('version')}",
                "evidence": str(baseline_root / "package.json"),
            }
        )
    write_json(paths["result"], result)
    append_log(paths["log"], {"ts": now_iso(), "event": "task_end", "task_id": task_id, "status": result.get("status")})
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OpenClaw runtime CLI benchmark adapter")
    p.add_argument("--run", required=True, help="Run directory under bench/results")
    p.add_argument("--tasks", nargs="+", default=None, help="Task IDs to execute (default: all tasks in run)")
    p.add_argument(
        "--baseline-root",
        default=str((Path(__file__).resolve().parents[1] / "baselines" / "openclaw")),
        help="Path to cloned OpenClaw repo baseline",
    )
    p.add_argument(
        "--state-dir",
        default="",
        help="Optional isolated OPENCLAW_STATE_DIR for runtime probes (defaults to <run>/_openclaw_runtime_state)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run)
    baseline_root = Path(args.baseline_root)
    if not run_dir.exists():
        raise SystemExit(f"Run dir not found: {run_dir}")
    if not baseline_root.exists():
        raise SystemExit(f"Baseline root not found: {baseline_root}")

    static_signals = gather_openclaw_signals(baseline_root)
    state_dir = Path(args.state_dir) if args.state_dir else (run_dir / "_openclaw_runtime_state")
    runtime_signals = _collect_runtime_probes(baseline_root, state_dir)

    task_ids = args.tasks
    if not task_ids:
        task_ids = sorted(p.name for p in (run_dir / "tasks").iterdir() if p.is_dir())

    summary = []
    for task_id in task_ids:
        out = run_task(
            run_dir=run_dir,
            task_id=task_id,
            baseline_root=baseline_root,
            static_signals=static_signals,
            runtime_signals=runtime_signals,
        )
        summary.append((task_id, out.get("status"), (out.get("metrics") or {}).get("success")))

    print("OpenClaw runtime adapter run complete:")
    print(f"  state_dir={state_dir}")
    for tid, status, success in summary:
        print(f"  - {tid}: status={status}, success={success}")


if __name__ == "__main__":
    main()
