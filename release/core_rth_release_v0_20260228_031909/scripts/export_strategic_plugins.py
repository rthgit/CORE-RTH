"""
Export top strategic plugins from the latest plugin manifest.

This is intentionally heuristic: it favors stable roots with signals of maintainability
(README/tests/known stack) and penalizes missing roots and unstable/system paths.

Outputs:
- %TEMP%\\rth_core\\logs\\top50_strategic_plugins.json
- %TEMP%\\rth_core\\logs\\top50_strategic_plugins.md
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _logs_dir() -> Path:
    p = Path(tempfile.gettempdir()) / "rth_core" / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_manifest() -> Dict[str, Any]:
    # Prefer latest manifest file written by plugin_runtime.
    p = _logs_dir() / "plugin_manifest_latest.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))

    # Fallback: build one on-demand.
    from app.core.plugin_runtime import plugin_runtime

    return plugin_runtime.build_manifest(min_score=0.0)


def _strategic_score(item: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    score = float(item.get("score", 0.0))
    signals = item.get("signals") or {}
    flags = set(item.get("flags") or [])
    types = signals.get("types") or []

    bonus = 0.0
    penalty = 0.0
    reasons: List[str] = []

    if signals.get("has_readme"):
        bonus += 1.2
        reasons.append("has_readme")
    else:
        penalty += 0.8

    if signals.get("has_tests_dir"):
        bonus += 1.0
        reasons.append("has_tests")
    else:
        # Only penalize if it looks like code.
        if types:
            penalty += 0.6

    if signals.get("has_license"):
        bonus += 0.2
        reasons.append("has_license")

    if signals.get("has_package_json"):
        bonus += 0.3
        reasons.append("node_marker")
    if signals.get("has_pyproject") or signals.get("has_requirements"):
        bonus += 0.3
        reasons.append("python_marker")
    if signals.get("has_cargo"):
        bonus += 0.3
        reasons.append("rust_marker")
    if signals.get("has_go_mod"):
        bonus += 0.3
        reasons.append("go_marker")
    if signals.get("has_dotnet"):
        bonus += 0.3
        reasons.append("dotnet_marker")

    if "missing_root" in flags:
        penalty += 10.0
        reasons.append("missing_root")
    if "unstable_or_system_path" in flags:
        penalty += 2.5
        reasons.append("unstable_path")
    if "missing_readme" in flags:
        # already partially penalized above, but keep a small extra
        penalty += 0.3
    if "missing_tests_dir" in flags:
        penalty += 0.2

    out = score + bonus - penalty
    meta = {
        "base_score": score,
        "bonus": bonus,
        "penalty": penalty,
        "reasons": reasons,
        "types": types,
    }
    return out, meta


def _evolution_hint(item: Dict[str, Any]) -> str:
    cat = str(item.get("category", "misc"))
    signals = item.get("signals") or {}
    types = signals.get("types") or []

    if cat == "knowledge":
        return "KG: indicizza in chunk, estrai entita/concetti, aggiungi valutazione affidabilita"
    if cat == "orchestration":
        return "CORE: rendilo plugin con contract v1 (actions, capabilities, telemetry) e governance"
    if cat == "devtools":
        if "node" in types:
            return "TOOL: adapter build/run/test, poi comandi standard e logs + consenso"
        return "TOOL: wrapper ispezione repo + task runner governato"
    if cat == "simulation":
        return "SIM: definisci scenario runner + metriche (barometro) + feedback loop"
    if cat == "hardware":
        return "SENSORI: crea adapter che legge toolchain/log e alimenta Chronicle/KG"
    return "MISC: se utile, normalizza come plugin; altrimenti demoti ad asset o disattiva"


def main() -> int:
    manifest = _load_manifest()
    items = list(manifest.get("items") or [])
    ranked = []
    for it in items:
        s, meta = _strategic_score(it)
        ranked.append((s, meta, it))
    ranked.sort(key=lambda x: x[0], reverse=True)

    top = ranked[:50]
    payload = {
        "generated_at": datetime.now().isoformat(),
        "source_manifest_timestamp": manifest.get("timestamp"),
        "count": len(top),
        "items": [
            {
                "rank": i + 1,
                "strategic_score": round(s, 4),
                "score": float(it.get("score", 0.0)),
                "root": it.get("root"),
                "category": it.get("category"),
                "status": it.get("status"),
                "signals": it.get("signals") or {},
                "flags": it.get("flags") or [],
                "meta": meta,
                "evolution_hint": _evolution_hint(it),
            }
            for i, (s, meta, it) in enumerate(top)
        ],
    }

    out_json = _logs_dir() / "top50_strategic_plugins.json"
    out_md = _logs_dir() / "top50_strategic_plugins.md"
    out_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = []
    lines.append("# Top 50 Strategic Plugins")
    lines.append("")
    lines.append(f"- generated_at: `{payload['generated_at']}`")
    lines.append(f"- source_manifest_timestamp: `{payload.get('source_manifest_timestamp')}`")
    lines.append("")
    lines.append("| # | strategic | score | category | types | root | evolution |")
    lines.append("|---:|---:|---:|---|---|---|---|")
    for row in payload["items"]:
        types = ",".join((row.get("meta") or {}).get("types") or [])
        lines.append(
            "| {rank} | {strategic_score:.2f} | {score:.2f} | {category} | {types} | `{root}` | {evolution} |".format(
                rank=row["rank"],
                strategic_score=row["strategic_score"],
                score=row["score"],
                category=row.get("category", "misc"),
                types=types or "-",
                root=str(row.get("root", "")),
                evolution=str(row.get("evolution_hint", "")),
            )
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": "ok", "json": str(out_json), "md": str(out_md)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

