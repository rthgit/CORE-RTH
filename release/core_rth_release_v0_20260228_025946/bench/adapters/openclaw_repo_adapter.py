import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def append_log(path: Path, record: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def bench_paths(run_dir: Path, task_id: str) -> Dict[str, Path]:
    tdir = run_dir / "tasks" / task_id
    return {
        "task": tdir / "task.json",
        "result": tdir / "result.json",
        "log": tdir / "adapter_log.jsonl",
        "dir": tdir,
    }


def fill_base_execution(result: Dict[str, Any], model_name: str = "openclaw_repo_static") -> None:
    result.setdefault("execution", {})
    result["execution"]["mode"] = "adapter_static_repo"
    result["execution"]["system_version"] = "openclaw_repo_static"
    result["execution"]["model"] = model_name
    result["execution"].setdefault("commands", [])
    result["execution"].setdefault("consent_requested", [])
    result["execution"].setdefault("consent_granted", [])
    result.setdefault("evidence", {})
    result["evidence"].setdefault("log_paths", [])
    result["evidence"].setdefault("artifact_paths", [])
    result["evidence"].setdefault("claims_with_evidence", [])
    result.setdefault("policy_violations", [])
    result.setdefault("metrics", {})


def start_result(result: Dict[str, Any], log_path: Path) -> None:
    fill_base_execution(result)
    result["status"] = "running"
    result["timing"] = result.get("timing") or {}
    result["timing"]["started_at"] = now_iso()
    if str(log_path) not in result["evidence"]["log_paths"]:
        result["evidence"]["log_paths"].append(str(log_path))


def end_result(result: Dict[str, Any], started_ts: float, status: str) -> None:
    result["status"] = status
    result["timing"]["ended_at"] = now_iso()
    result["timing"]["duration_sec"] = round(time.time() - started_ts, 3)


def set_metric(result: Dict[str, Any], key: str, value: Optional[float]) -> None:
    if key in result["metrics"]:
        result["metrics"][key] = value


def safe_read(path: Path, limit: int = 2_000_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return ""


def count_substrings(text: str, needles: List[str]) -> int:
    low = text.lower()
    return sum(low.count(n.lower()) for n in needles)


def run_cmd(args: List[str], cwd: Path, timeout_sec: int = 15) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            shell=False,
        )
        return {
            "args": args,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[:4000],
            "stderr": (proc.stderr or "")[:4000],
        }
    except Exception as e:
        return {
            "args": args,
            "returncode": None,
            "stdout": "",
            "stderr": str(e),
        }


def _json_load_maybe(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def gather_openclaw_signals(root: Path) -> Dict[str, Any]:
    pkg = _json_load_maybe(root / "package.json") or {}
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    deps = pkg.get("dependencies") if isinstance(pkg.get("dependencies"), dict) else {}
    dev_deps = pkg.get("devDependencies") if isinstance(pkg.get("devDependencies"), dict) else {}

    changelog_text = safe_read(root / "CHANGELOG.md", limit=1_500_000)
    readme_text = safe_read(root / "README.md", limit=600_000)
    approvals_doc = safe_read(root / "docs" / "cli" / "approvals.md", limit=200_000)
    memory_doc = safe_read(root / "docs" / "concepts" / "memory.md", limit=900_000)
    nodes_doc = safe_read(root / "docs" / "nodes" / "index.md", limit=500_000)

    runtime_probe_help = run_cmd(["node", "openclaw.mjs", "--help"], cwd=root, timeout_sec=10)
    runtime_probe_rpc = run_cmd(["node", "openclaw.mjs", "agent", "--mode", "rpc", "--json", "--help"], cwd=root, timeout_sec=10)

    dist_dir = root / "dist"
    runtime_available = dist_dir.exists() and any((dist_dir / n).exists() for n in ["entry.js", "entry.mjs"])

    signals = {
        "baseline_root": str(root),
        "repo_exists": root.exists(),
        "dist_present": dist_dir.exists(),
        "runtime_available": runtime_available,
        "node_modules_present": (root / "node_modules").exists(),
        "pnpm_lock_present": (root / "pnpm-lock.yaml").exists(),
        "scripts": {
            "openclaw:rpc": scripts.get("openclaw:rpc"),
            "moltbot:rpc": scripts.get("moltbot:rpc"),
            "build": scripts.get("build"),
            "test": scripts.get("test"),
            "start": scripts.get("start"),
        },
        "docs_presence": {
            "approvals": bool(approvals_doc),
            "memory": bool(memory_doc),
            "nodes": bool(nodes_doc),
            "gateway_protocol": (root / "docs" / "gateway" / "protocol.md").exists(),
        },
        "keyword_counts": {
            "changelog_exec_approvals": count_substrings(changelog_text, ["exec approvals", "exec-approvals.json"]),
            "changelog_memory_qmd": count_substrings(changelog_text, ["memory/qmd", "memorysearch", "qmd"]),
            "changelog_operator_scopes": count_substrings(changelog_text, ["operator.read", "operator.write", "pairing"]),
            "docs_exec_approvals": count_substrings(approvals_doc + nodes_doc, ["exec-approvals.json", "approvals", "system.run"]),
            "docs_memory": count_substrings(memory_doc, ["memorysearch", "qmd", "memory_search", "sqlite"]),
            "docs_operator": count_substrings(nodes_doc + safe_read(root / "docs" / "gateway" / "protocol.md", 200_000), ["operator.read", "operator.write"]),
        },
        "dependency_signals": {
            "pdfjs": "pdfjs-dist" in deps,
            "sqlite_vec": "sqlite-vec" in deps,
            "node_llama_peer": "node-llama-cpp" in (pkg.get("peerDependencies") or {}),
            "playwright": "playwright-core" in deps,
            "ws": "ws" in deps,
        },
        "repo_layout": {
            "src": (root / "src").exists(),
            "extensions": (root / "extensions").exists(),
            "docs": (root / "docs").exists(),
            "scripts": (root / "scripts").exists(),
            "test": (root / "test").exists(),
        },
        "runtime_probe_help": runtime_probe_help,
        "runtime_probe_rpc": runtime_probe_rpc,
        "readme_mentions": {
            "gateway": count_substrings(readme_text, ["gateway", "operator", "channels", "tools"]),
            "memory": count_substrings(readme_text, ["memory", "qmd"]),
            "agents": count_substrings(readme_text, ["agent", "subagent", "agents"]),
        },
        "package_meta": {
            "name": pkg.get("name"),
            "version": pkg.get("version"),
            "bin": pkg.get("bin"),
            "engines": pkg.get("engines"),
            "scripts_count": len(scripts),
            "deps_count": len(deps),
            "dev_deps_count": len(dev_deps),
        },
    }
    return signals


def write_task_artifact(paths: Dict[str, Path], name: str, payload: Dict[str, Any], result: Dict[str, Any]) -> Path:
    ap = paths["dir"] / name
    write_json(ap, payload)
    result["evidence"]["artifact_paths"].append(str(ap))
    return ap


def score_task_openclaw_static(task: Dict[str, Any], result: Dict[str, Any], signals: Dict[str, Any], paths: Dict[str, Path]) -> None:
    tid = task.get("id", "")
    runtime_available = bool(signals.get("runtime_available"))
    rpc_declared = bool((signals.get("scripts") or {}).get("openclaw:rpc") or (signals.get("scripts") or {}).get("moltbot:rpc"))
    k = signals.get("keyword_counts") or {}
    docs = signals.get("docs_presence") or {}
    dep = signals.get("dependency_signals") or {}
    runtime_probe = {
        "help": signals.get("runtime_probe_help"),
        "rpc": signals.get("runtime_probe_rpc"),
        "runtime_available": runtime_available,
    }

    # Defaults for static mismatch evaluation.
    set_metric(result, "first_pass", 1)
    set_metric(result, "accuracy", 2)
    set_metric(result, "governance", 2)
    set_metric(result, "efficiency", 5)

    notes = []
    notes.append("OpenClaw baseline evaluated via static repo analysis because local runtime build output (`dist/`) is missing.")
    if not runtime_available:
        rp = runtime_probe["help"] or {}
        err = (rp.get("stderr") or "") + " " + (runtime_probe.get("rpc") or {}).get("stderr", "")
        if "missing dist/entry" in err.lower():
            notes.append("Runtime probe confirms missing build output (`dist/entry.(m)js`).")

    if tid in {"chronicle_reader_scan", "chronicle_antihaker_scan"}:
        set_metric(result, "success", 1 if rpc_declared else 0)
        set_metric(result, "first_pass", 1 if rpc_declared else 0)
        set_metric(result, "governance", 3 if docs.get("approvals") else 2)
        result["judge_notes"] = (
            "OpenClaw repo shows agent/RPC and operator tooling docs, but this run could not execute the runtime "
            "and therefore did not scan the target local project root."
        )
    elif tid == "knowledgegraph_crosslink_projects":
        set_metric(result, "success", 1)
        set_metric(result, "memory", 2 if int(k.get("docs_memory", 0)) > 0 else 1)
        set_metric(result, "governance", 3)
        result["judge_notes"] = (
            "OpenClaw has documented memory/QMD features, but no executed graph build over the benchmark roots "
            "was possible in this environment."
        )
    elif tid == "cortex_conflict_bias_audit":
        set_metric(result, "success", 1)
        set_metric(result, "memory", 2 if int(k.get("docs_memory", 0)) > 0 else 1)
        set_metric(result, "governance", 3)
        result["judge_notes"] = (
            "No Cortex-equivalent root-specific audit was executed. Static evidence exists for security/approvals and memory systems, "
            "but this benchmark task remained unverified."
        )
    elif tid in {"praxis_reader_evolution", "praxis_antihaker_hardening"}:
        set_metric(result, "success", 1)
        set_metric(result, "governance", 3 if docs.get("approvals") else 2)
        set_metric(result, "praxis_value", 1)
        result["judge_notes"] = (
            "OpenClaw baseline was not run against the target roots, so no project-specific evolution/hardening proposals "
            "were generated for this suite."
        )
    elif tid == "guardian_permission_enforcement":
        # Strongest static evidence area for OpenClaw.
        approvals_strength = int(k.get("docs_exec_approvals", 0)) + int(k.get("changelog_exec_approvals", 0))
        operator_strength = int(k.get("docs_operator", 0)) + int(k.get("changelog_operator_scopes", 0))
        set_metric(result, "success", 3 if approvals_strength > 5 and operator_strength > 2 else 2)
        set_metric(result, "first_pass", 3 if rpc_declared else 2)
        set_metric(result, "accuracy", 3)
        set_metric(result, "governance", 4)
        set_metric(result, "memory", 2)
        result["judge_notes"] = (
            "Strong static evidence of exec approvals and operator scope governance (`exec-approvals.json`, operator.read/write), "
            "but no live enforcement run was executed because the local OpenClaw runtime build is missing."
        )
    elif tid in {"adapter_build_probe_reader", "adapter_operational_probe_antihaker"}:
        set_metric(result, "success", 2 if rpc_declared else 1)
        set_metric(result, "first_pass", 2 if rpc_declared else 1)
        set_metric(result, "governance", 4 if docs.get("approvals") else 3)
        set_metric(result, "memory", 1)
        result["judge_notes"] = (
            "OpenClaw shows RPC agent entrypoints and exec-approval documentation, suggesting an operator path, "
            "but no adapter probe on the target roots was executed in this environment."
        )
    elif tid == "memory_followup_recall":
        mem_score = 3 if int(k.get("docs_memory", 0)) > 20 and int(k.get("changelog_memory_qmd", 0)) > 10 else 2
        set_metric(result, "success", 2)
        set_metric(result, "first_pass", 2)
        set_metric(result, "governance", 3)
        set_metric(result, "memory", mem_score)
        result["judge_notes"] = (
            "OpenClaw has extensive documented memory/QMD capabilities, but recall on the benchmark's prior task artifacts "
            "was not runnable/verified here."
        )
    elif tid == "doc_reader_capability_matrix":
        set_metric(result, "success", 1)
        set_metric(result, "first_pass", 1)
        set_metric(result, "governance", 3)
        set_metric(result, "memory", 1)
        # Static signal only: OpenClaw has pdf/media libs, but the task is specific to SublimeOmniDoc.
        if dep.get("pdfjs"):
            set_metric(result, "accuracy", 2)
        result["judge_notes"] = (
            "Task is specific to `SublimeOmniDoc`. OpenClaw repo has generic media/document-related dependencies "
            "(e.g. `pdfjs-dist`) but no executed capability matrix for the target app."
        )
    elif tid == "portfolio_top_gems_ranking":
        set_metric(result, "success", 2)
        set_metric(result, "first_pass", 2)
        set_metric(result, "accuracy", 3)
        set_metric(result, "governance", 3)
        set_metric(result, "memory", 2)
        set_metric(result, "praxis_value", 2)
        result["judge_notes"] = (
            "OpenClaw itself appears to be a mature multi-agent gateway project, but this task targets ranking the user's "
            "portfolio assets and integration priority; no runtime-based ranking over those assets was executed."
        )
    else:
        set_metric(result, "success", 0)
        set_metric(result, "first_pass", 0)
        result["judge_notes"] = "Unsupported task."

    task_artifact = {
        "task": task,
        "openclaw_static_signals": signals,
        "runtime_probe": runtime_probe,
        "limitations": [
            "Cloned source repo lacks `dist/` build output in this environment.",
            "No dependency install/build was performed, so OpenClaw runtime/agent RPC was not executed.",
            "Scores represent static baseline fitness/evidence for this suite, not live runtime performance.",
        ],
    }
    artifact_path = write_task_artifact(paths, "openclaw_static_probe.json", task_artifact, result)
    result["evidence"]["claims_with_evidence"].append({
        "claim": "OpenClaw benchmark baseline scored via static repository evidence and runtime probe",
        "evidence": str(artifact_path),
    })


def run_task(run_dir: Path, task_id: str, baseline_root: Path, signals: Dict[str, Any]) -> Dict[str, Any]:
    paths = bench_paths(run_dir, task_id)
    task = read_json(paths["task"])
    result = read_json(paths["result"])
    started = time.time()
    start_result(result, paths["log"])
    append_log(paths["log"], {"ts": now_iso(), "event": "task_start", "task_id": task_id})
    append_log(paths["log"], {"ts": now_iso(), "event": "baseline_root", "path": str(baseline_root)})

    try:
        if not baseline_root.exists():
            set_metric(result, "success", 0)
            set_metric(result, "first_pass", 0)
            result["judge_notes"] = f"OpenClaw baseline root not found: {baseline_root}"
            end_result(result, started, "failed")
        else:
            score_task_openclaw_static(task=task, result=result, signals=signals, paths=paths)
            end_result(result, started, "completed")
    except Exception as e:
        result["judge_notes"] = f"Adapter exception: {e}"
        set_metric(result, "success", 0)
        set_metric(result, "first_pass", 0)
        end_result(result, started, "failed")

    write_json(paths["result"], result)
    append_log(paths["log"], {"ts": now_iso(), "event": "task_end", "task_id": task_id, "status": result.get("status")})
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="OpenClaw repo static benchmark adapter")
    p.add_argument("--run", required=True, help="Run directory under bench/results")
    p.add_argument("--tasks", nargs="+", required=True, help="Task IDs to execute")
    p.add_argument(
        "--baseline-root",
        default=str((Path(__file__).resolve().parents[1] / "baselines" / "openclaw")),
        help="Path to cloned OpenClaw repo baseline",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run)
    baseline_root = Path(args.baseline_root)
    if not run_dir.exists():
        raise SystemExit(f"Run dir not found: {run_dir}")
    signals = gather_openclaw_signals(baseline_root)

    summary = []
    for task_id in args.tasks:
        out = run_task(run_dir=run_dir, task_id=task_id, baseline_root=baseline_root, signals=signals)
        summary.append((task_id, out.get("status"), (out.get("metrics") or {}).get("success")))

    print("OpenClaw static adapter run complete:")
    for tid, status, success in summary:
        print(f"  - {tid}: status={status}, success={success}")


if __name__ == "__main__":
    main()
