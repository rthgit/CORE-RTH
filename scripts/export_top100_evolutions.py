"""
Merge ranking outputs and export top 100 strategic evolutions
with practical usage and evolution guidance.
"""
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List

LOG_DIR_CANDIDATES = [
    Path("logs"),
    Path("storage_runtime") / "logs",
    Path(tempfile.gettempdir()) / "rth_core" / "logs",
]

RANK_FILES = [
    "project_ranking.json",
    "personal_project_ranking.json",
    "selected_ranking.json",
]


def choose_logs_dir() -> Path:
    for base in LOG_DIR_CANDIDATES:
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return base
        except Exception:
            continue
    return Path(tempfile.gettempdir()) / "rth_core" / "logs"


def find_rank_file(name: str) -> Path | None:
    matches: List[Path] = []
    for base in LOG_DIR_CANDIDATES:
        p = base / name
        if p.exists():
            matches.append(p)
    if not matches:
        return None
    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def infer_usage(root: str) -> str:
    low = root.lower()
    if any(k in low for k in ["biome", "knowledge", "rag", "vector", "embedding", "corpus"]):
        return "Motore conoscenza/RAG e memoria strutturata."
    if any(k in low for k in ["core rth", "rth_synapse", "jarvis", "swarm", "synapse", "cortex", "praxis"]):
        return "Core orchestrazione agenti e governance decisionale."
    if any(k in low for k in ["code-oss", "codex", "open-cowork", "assistant", "plugin"]):
        return "Adapter sviluppo software (build/test/run e toolchain coding)."
    if any(k in low for k in ["simulatore", "rcq"]):
        return "Simulazione, valutazione scenari e validazione modelli."
    if any(k in low for k in ["xilinx", "vitis", "vivado"]):
        return "Pipeline hardware/accelerazione e integrazione tool tecnici."
    return "Modulo ad alta densita codice riusabile nel framework."


def infer_evolution(entry: Dict[str, Any]) -> str:
    recs = entry.get("recommendations") or []
    if recs:
        return " ".join(str(r) for r in recs[:2])
    usage = entry.get("utilizzo", "").lower()
    if "conoscenza" in usage or "rag" in usage:
        return "Agganciare al Knowledge Graph, aggiungere metriche affidabilita e query tool."
    if "orchestrazione" in usage or "governance" in usage:
        return "Convertire in plugin governato con policy, consenso e test di regressione."
    if "sviluppo software" in usage:
        return "Standardizzare comandi build/run/test e aggiungere adapter con fallback."
    if "simulazione" in usage:
        return "Integrare benchmark, telemetry e feedback loop nel ciclo Praxis."
    if "hardware" in usage:
        return "Isolare wrapper operativi e aggiungere monitoraggio risorse/esiti."
    return "Definire interfacce chiare, test minimi e onboarding nel plugin hub."


def main():
    merged: Dict[str, Dict[str, Any]] = {}
    found_files: List[str] = []

    for name in RANK_FILES:
        path = find_rank_file(name)
        if not path:
            continue
        found_files.append(str(path))
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        ranked = payload.get("ranked", [])
        for item in ranked:
            root = str(item.get("root", "")).strip()
            if not root:
                continue
            key = root.lower()
            score = float(item.get("score", 0.0))
            existing = merged.get(key)
            if not existing:
                merged[key] = {
                    "root": root,
                    "score": score,
                    "sources": [name],
                    "reasons": list(item.get("reasons", []) or []),
                    "types": list(item.get("types", []) or []),
                    "markers": list(item.get("markers", []) or []),
                    "file_count": int(item.get("file_count", item.get("code_files", 0) or 0)),
                    "recommendations": list(item.get("recommendations", []) or []),
                }
                continue

            if score > existing["score"]:
                existing["score"] = score
            if name not in existing["sources"]:
                existing["sources"].append(name)
            for field in ["reasons", "types", "markers", "recommendations"]:
                vals = list(item.get(field, []) or [])
                for v in vals:
                    if v not in existing[field]:
                        existing[field].append(v)
            existing["file_count"] = max(existing.get("file_count", 0), int(item.get("file_count", item.get("code_files", 0) or 0)))

    values = list(merged.values())
    values.sort(key=lambda x: x.get("score", 0), reverse=True)
    top100 = values[:100]

    for i, entry in enumerate(top100, start=1):
        entry["rank"] = i
        entry["utilizzo"] = infer_usage(entry["root"])
        entry["evoluzione"] = infer_evolution(entry)

    out_dir = choose_logs_dir()
    out_json = out_dir / "top100_evolutions.json"
    out_md = out_dir / "top100_evolutions.md"

    out_json.write_text(json.dumps({
        "count": len(top100),
        "sources": found_files,
        "items": top100,
    }, indent=2), encoding="utf-8")

    lines = [
        "# Top 100 Evolutions",
        "",
        f"- count: {len(top100)}",
        "",
    ]
    for e in top100:
        lines.append(f"## {e['rank']}. {e['root']}")
        lines.append(f"- score: {e['score']:.3f}")
        lines.append(f"- utilizzo: {e['utilizzo']}")
        lines.append(f"- evoluzione: {e['evoluzione']}")
        if e.get("sources"):
            lines.append(f"- sources: {', '.join(e['sources'])}")
        lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"out_json={out_json}")
    print(f"out_md={out_md}")
    print(f"count={len(top100)}")
    print("top10:")
    for e in top100[:10]:
        print(f"- {e['rank']:>3} | {e['score']:>7.3f} | {e['root']}")


if __name__ == "__main__":
    main()
