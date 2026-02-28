"""
Rank projects for potential alignment with the current core vision.
Uses evolution snapshot if present, otherwise computes one.
"""
import json
import math
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR_CANDIDATES = [
    ROOT / "logs",
    ROOT / "storage_runtime" / "logs",
    Path(tempfile.gettempdir()) / "rth_core" / "logs",
]

TYPE_WEIGHTS = {
    "python": 3.0,
    "node": 2.0,
    "rust": 2.0,
    "go": 2.0,
    "java": 1.0,
    "native": 1.0,
    "dotnet": 1.5,
    "php": 1.0,
    "ruby": 1.0,
    "elixir": 1.0,
}

KEYWORD_WEIGHTS = {
    "jarvis": 6.0,
    "assistant": 4.0,
    "agent": 3.5,
    "swarm": 3.0,
    "orchestr": 3.0,
    "cortex": 3.0,
    "synapse": 3.0,
    "praxis": 2.5,
    "knowledge": 2.5,
    "graph": 2.0,
    "memory": 2.0,
    "brain": 2.0,
    "core": 1.5,
    "engine": 2.0,
    "framework": 1.5,
    "automation": 2.5,
    "workflow": 2.0,
    "pipeline": 2.0,
    "tool": 1.5,
    "sdk": 1.5,
    "api": 1.5,
    "voice": 2.0,
    "chat": 1.5,
    "rag": 2.5,
    "vector": 2.0,
    "embedding": 2.0,
    "search": 1.5,
}

PENALTY_KEYWORDS = {
    "example": 1.5,
    "sample": 1.5,
    "demo": 1.0,
    "tutorial": 1.5,
    "test": 0.5,
    "tmp": 2.0,
    "backup": 2.0,
    "old": 1.5,
    "archive": 2.0,
}

SKIP_SUBSTRINGS = [
    "/appdata/",
    "/.cache/",
    "/.cursor/",
    "/.trae/",
    "/.antigravity/",
    "/.vscode/",
    "/.idea/",
    "/.gradle/",
    "/.m2/",
    "/.npm/",
    "/.yarn/",
    "/.pnpm/",
    "/android/sdk/",
    "/android-ndk/",
    "/flutter/engine/",
    "/flutter/dev/",
    "/flutter/bin/cache/",
    "/site-packages/",
    "/toolchains/",
    "/sysroot/",
    "/program files/",
    "/windows/",
    "/system volume information/",
    "/$recycle.bin/",
    "/node_modules/",
    "/.git/",
]


def _choose_logs_dir() -> Path:
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


def _snapshot_paths() -> List[Path]:
    return [base / "evolution_snapshot.json" for base in LOG_DIR_CANDIDATES]


def _load_existing_snapshot() -> Dict[str, Any]:
    candidates = [p for p in _snapshot_paths() if p.exists()]
    if not candidates:
        return {}
    newest = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    try:
        return json.loads(newest.read_text(encoding="utf-8"))
    except Exception:
        return {}

def load_snapshot() -> Dict[str, Any]:
    existing = _load_existing_snapshot()
    if existing.get("projects_found", 0) >= 1000:
        return existing
    # Fallback: compute on the fly
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from app.core.evolution import evolution_analyzer
    result = evolution_analyzer.propose(roots=["C:/", "D:/"], max_projects=5000)
    out_snapshot = _choose_logs_dir() / "evolution_snapshot.json"
    out_snapshot.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result

def normalize(path: str) -> str:
    return path.replace("\\", "/").lower().rstrip("/")

def collapse_nested(projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Keep highest-level roots to avoid duplicates like android/app inside android
    projects_sorted = sorted(projects, key=lambda p: len(normalize(p["root"])))
    kept: List[Dict[str, Any]] = []
    kept_roots: List[str] = []
    for p in projects_sorted:
        root = normalize(p["root"])
        if any(root.startswith(k + "/") for k in kept_roots):
            continue
        kept.append(p)
        kept_roots.append(root)
    return kept

def score_project(p: Dict[str, Any], recs: List[str]) -> Tuple[float, List[str]]:
    root = normalize(p["root"])
    reasons: List[str] = []
    score = 0.0

    # Size signal
    file_count = p.get("file_count") or 0
    score += math.log1p(file_count) * 0.6
    if file_count:
        reasons.append(f"files={file_count}")

    # Depth penalty for very deep roots
    depth = root.count("/")
    if depth >= 8:
        score -= 1.0
        reasons.append(f"deep={depth}")
    elif depth >= 6:
        score -= 0.5
        reasons.append(f"deep={depth}")

    # Type weights
    for t in p.get("types", []):
        w = TYPE_WEIGHTS.get(t, 0.5)
        score += w
        reasons.append(f"type:{t}")

    # Keyword weights from root path
    for kw, w in KEYWORD_WEIGHTS.items():
        if kw in root:
            score += w
            reasons.append(f"kw:{kw}")

    # Penalties for likely low-signal folders
    for kw, w in PENALTY_KEYWORDS.items():
        if kw in root:
            score -= w
            reasons.append(f"pen:{kw}")

    # Missing hygiene signals (from recommendations)
    missing = 0
    for r in recs:
        if "README" in r:
            missing += 1
        if "test" in r.lower():
            missing += 1
        if "CI" in r:
            missing += 1
        if "LICENSE" in r:
            missing += 1
    if missing:
        score -= missing * 0.4
        reasons.append(f"missing={missing}")

    return score, reasons

def main():
    out_path = _choose_logs_dir() / "project_ranking.json"
    snapshot = load_snapshot()
    projects = snapshot.get("projects", [])
    proposals = snapshot.get("proposals", [])
    if not projects:
        print("No projects found.")
        return

    rec_map: Dict[str, List[str]] = {}
    for p in proposals:
        rec_map[p["root"]] = p.get("recommendations", [])

    collapsed = collapse_nested(projects)

    filtered = []
    for p in collapsed:
        root = normalize(p["root"])
        if any(s in root for s in SKIP_SUBSTRINGS):
            continue
        filtered.append(p)

    ranked = []
    for p in filtered:
        recs = rec_map.get(p["root"], [])
        score, reasons = score_project(p, recs)
        ranked.append({
            "root": p["root"],
            "score": round(score, 3),
            "types": p.get("types", []),
            "markers": p.get("markers", []),
            "file_count": p.get("file_count"),
            "top_extensions": p.get("top_extensions", []),
            "recommendations": recs,
            "reasons": reasons[:8],
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)

    out_path.write_text(json.dumps({
        "ranked": ranked,
        "projects_total": len(projects),
        "projects_collapsed": len(collapsed),
        "projects_filtered": len(filtered)
    }, indent=2), encoding="utf-8")

    print(f"output={out_path}")
    print(f"projects_total={len(projects)}")
    print(f"projects_collapsed={len(collapsed)}")
    print(f"projects_filtered={len(filtered)}")
    print("top10:")
    for r in ranked[:10]:
        print(f"- {r['score']:>6} | {r['root']}")

if __name__ == "__main__":
    main()
