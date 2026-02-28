import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_SUITE = Path(__file__).parent / "tasks" / "core_rth_vs_openclaw_suite.json"
DEFAULT_RESULTS = Path(__file__).parent / "results"
METRIC_KEYS = ["success", "first_pass", "accuracy", "governance", "memory", "praxis_value", "efficiency"]


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_suite(path: Path) -> dict:
    suite = load_json(path)
    if "tasks" not in suite or not isinstance(suite["tasks"], list):
        raise ValueError(f"Invalid suite file: {path}")
    return suite


def safe_name(text: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in text).strip("_")


def build_result_template(task: dict) -> dict:
    return {
        "task_id": task["id"],
        "status": "pending",
        "timing": {
            "started_at": None,
            "ended_at": None,
            "duration_sec": None
        },
        "execution": {
            "mode": "manual",
            "system_version": None,
            "model": None,
            "commands": [],
            "consent_requested": [],
            "consent_granted": []
        },
        "metrics": {k: None for k in METRIC_KEYS},
        "policy_violations": [],
        "evidence": {
            "log_paths": [],
            "artifact_paths": [],
            "claims_with_evidence": []
        },
        "judge_notes": "",
        "operator_notes": ""
    }


def prepare_run(system: str, suite_path: Path, out_root: Path, label: str = "") -> Path:
    suite = load_suite(suite_path)
    run_id = f"{now_stamp()}_{safe_name(system)}"
    if label:
        run_id += f"_{safe_name(label)}"
    run_dir = out_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    manifest = {
        "run_id": run_id,
        "system": system,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "suite_path": str(suite_path),
        "suite_id": suite.get("suite_id"),
        "suite_version": suite.get("version"),
        "metric_weights": suite.get("metric_weights", {}),
        "score_scale": suite.get("score_scale", {"min": 0, "max": 5}),
        "status": "prepared",
        "notes": ""
    }
    dump_json(run_dir / "manifest.json", manifest)
    dump_json(run_dir / "suite_snapshot.json", suite)

    tasks_dir = run_dir / "tasks"
    for task in suite["tasks"]:
        tdir = tasks_dir / task["id"]
        tdir.mkdir(parents=True, exist_ok=True)
        dump_json(tdir / "task.json", task)
        dump_json(tdir / "result.json", build_result_template(task))
        (tdir / "notes.md").write_text(
            "# Notes\n\n- Fill `result.json` after execution.\n- Attach logs/artifacts paths when available.\n",
            encoding="utf-8"
        )

    print(f"Prepared run: {run_dir}")
    print(f"Tasks: {len(suite['tasks'])}")
    return run_dir


def _scale_info(manifest: dict, suite: dict) -> Tuple[float, float]:
    scale = manifest.get("score_scale") or suite.get("score_scale") or {"min": 0, "max": 5}
    return float(scale.get("min", 0)), float(scale.get("max", 5))


def score_run(run_dir: Path, write_outputs: bool = True) -> dict:
    manifest = load_json(run_dir / "manifest.json")
    suite = load_json(run_dir / "suite_snapshot.json")
    weights: Dict[str, float] = manifest.get("metric_weights") or suite.get("metric_weights") or {}
    min_score, max_score = _scale_info(manifest, suite)
    denom = max(max_score - min_score, 1e-9)

    task_rows: List[dict] = []
    metric_accum = {k: {"sum": 0.0, "count": 0} for k in METRIC_KEYS}
    total_weighted_norm = 0.0
    total_tasks = 0
    completed_tasks = 0

    for task in suite["tasks"]:
        tdir = run_dir / "tasks" / task["id"]
        rpath = tdir / "result.json"
        if not rpath.exists():
            continue
        result = load_json(rpath)
        metrics = result.get("metrics", {})
        task_weighted_norm = 0.0
        task_weight_sum = 0.0

        for key in METRIC_KEYS:
            val = metrics.get(key)
            if isinstance(val, (int, float)):
                metric_accum[key]["sum"] += float(val)
                metric_accum[key]["count"] += 1
                w = float(weights.get(key, 0.0))
                norm = (float(val) - min_score) / denom
                norm = max(0.0, min(1.0, norm))
                task_weighted_norm += norm * w
                task_weight_sum += w

        if result.get("status") == "completed":
            completed_tasks += 1
        total_tasks += 1

        if task_weight_sum > 0:
            total_weighted_norm += task_weighted_norm / task_weight_sum

        task_rows.append({
            "task_id": task["id"],
            "pillar": task.get("pillar"),
            "status": result.get("status"),
            "duration_sec": (result.get("timing") or {}).get("duration_sec"),
            **{k: metrics.get(k) for k in METRIC_KEYS},
            "policy_violations": len(result.get("policy_violations") or []),
            "weighted_score_0_100": round((task_weighted_norm / task_weight_sum) * 100.0, 2) if task_weight_sum > 0 else None
        })

    avg_metrics = {}
    for key, data in metric_accum.items():
        avg_metrics[key] = round(data["sum"] / data["count"], 3) if data["count"] else None

    overall = {
        "run_id": manifest.get("run_id"),
        "system": manifest.get("system"),
        "suite_id": suite.get("suite_id"),
        "suite_version": suite.get("version"),
        "scored_at": dt.datetime.now().isoformat(timespec="seconds"),
        "task_count": total_tasks,
        "completed_tasks": completed_tasks,
        "completion_rate": round((completed_tasks / total_tasks) if total_tasks else 0.0, 4),
        "avg_metrics": avg_metrics,
        "overall_score_0_100": round((total_weighted_norm / total_tasks) * 100.0, 2) if total_tasks else 0.0,
        "weights": weights
    }
    payload = {
        "summary": overall,
        "tasks": task_rows
    }

    if write_outputs:
        dump_json(run_dir / "summary.json", payload)
        with (run_dir / "scoreboard.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "task_id", "pillar", "status", "duration_sec",
                    *METRIC_KEYS,
                    "policy_violations", "weighted_score_0_100"
                ]
            )
            writer.writeheader()
            for row in task_rows:
                writer.writerow(row)

    return payload


def compare_runs(run_a: Path, run_b: Path) -> dict:
    a = score_run(run_a, write_outputs=True)
    b = score_run(run_b, write_outputs=True)
    sa = a["summary"]
    sb = b["summary"]

    per_task_a = {row["task_id"]: row for row in a["tasks"]}
    per_task_b = {row["task_id"]: row for row in b["tasks"]}
    common_ids = sorted(set(per_task_a).intersection(per_task_b))

    task_deltas = []
    for tid in common_ids:
        ra = per_task_a[tid]
        rb = per_task_b[tid]
        va = ra.get("weighted_score_0_100")
        vb = rb.get("weighted_score_0_100")
        delta = None
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            delta = round(va - vb, 2)
        task_deltas.append({
            "task_id": tid,
            "pillar": ra.get("pillar") or rb.get("pillar"),
            "run_a_score_0_100": va,
            "run_b_score_0_100": vb,
            "delta_a_minus_b": delta
        })

    metric_deltas = {}
    for k in METRIC_KEYS:
        va = (sa.get("avg_metrics") or {}).get(k)
        vb = (sb.get("avg_metrics") or {}).get(k)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            metric_deltas[k] = round(va - vb, 3)
        else:
            metric_deltas[k] = None

    cmp_payload = {
        "compared_at": dt.datetime.now().isoformat(timespec="seconds"),
        "run_a": sa,
        "run_b": sb,
        "overall_delta_a_minus_b": round(float(sa.get("overall_score_0_100", 0.0)) - float(sb.get("overall_score_0_100", 0.0)), 2),
        "metric_deltas_a_minus_b": metric_deltas,
        "task_deltas": task_deltas
    }

    out_name = f"compare_{Path(run_a).name}__vs__{Path(run_b).name}.json"
    out_path = DEFAULT_RESULTS / out_name
    dump_json(out_path, cmp_payload)
    return cmp_payload


def print_run_summary(payload: dict) -> None:
    s = payload["summary"]
    print(f"Run: {s['run_id']} ({s['system']})")
    print(f"Score: {s['overall_score_0_100']}/100")
    print(f"Completion: {s['completed_tasks']}/{s['task_count']} ({s['completion_rate'] * 100:.1f}%)")
    print("Avg metrics:")
    for k in METRIC_KEYS:
        print(f"  - {k}: {s['avg_metrics'].get(k)}")


def print_compare_summary(payload: dict) -> None:
    a = payload["run_a"]
    b = payload["run_b"]
    print("A/B Comparison")
    print(f"A: {a['run_id']} ({a['system']}) score={a['overall_score_0_100']}")
    print(f"B: {b['run_id']} ({b['system']}) score={b['overall_score_0_100']}")
    print(f"Delta A-B: {payload['overall_delta_a_minus_b']}")
    print("Metric deltas A-B:")
    for k in METRIC_KEYS:
        print(f"  - {k}: {payload['metric_deltas_a_minus_b'].get(k)}")


def cli() -> None:
    parser = argparse.ArgumentParser(description="Core RTH benchmark runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_prepare = sub.add_parser("prepare", help="Prepare a run folder with task templates")
    p_prepare.add_argument("--system", required=True, choices=["core_rth", "openclaw", "other"])
    p_prepare.add_argument("--suite", default=str(DEFAULT_SUITE))
    p_prepare.add_argument("--out", default=str(DEFAULT_RESULTS))
    p_prepare.add_argument("--label", default="")

    p_score = sub.add_parser("score", help="Score a single run")
    p_score.add_argument("--run", required=True)

    p_compare = sub.add_parser("compare", help="Compare two runs")
    p_compare.add_argument("--run-a", required=True)
    p_compare.add_argument("--run-b", required=True)

    args = parser.parse_args()

    if args.cmd == "prepare":
        prepare_run(args.system, Path(args.suite), Path(args.out), args.label)
        return
    if args.cmd == "score":
        payload = score_run(Path(args.run), write_outputs=True)
        print_run_summary(payload)
        return
    if args.cmd == "compare":
        payload = compare_runs(Path(args.run_a), Path(args.run_b))
        print_compare_summary(payload)
        return

    raise RuntimeError(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    cli()

