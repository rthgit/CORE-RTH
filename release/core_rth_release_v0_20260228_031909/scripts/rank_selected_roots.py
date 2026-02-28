"""
Rank subprojects within selected roots using file index.
"""
import json
import math
import tempfile
from pathlib import Path
from typing import Dict, Any, List

INDEX_CANDIDATES = [
    Path("storage") / "memory" / "files.jsonl",
    Path("storage_runtime") / "memory" / "files.jsonl",
    Path(tempfile.gettempdir()) / "rth_core" / "memory" / "files.jsonl",
]

LOG_DIR_CANDIDATES = [
    Path("logs"),
    Path("storage_runtime") / "logs",
    Path(tempfile.gettempdir()) / "rth_core" / "logs",
]

ROOTS = [
    "c:/users/pc/desktop/biome",
    "d:/codex",
    "d:/simulatore_rcq",
]

CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".cs",
    ".cpp", ".c", ".h", ".hpp", ".kt", ".kts", ".swift", ".php", ".rb",
    ".lua", ".sql", ".sh", ".ps1", ".bat", ".cmd", ".psm1", ".yaml",
    ".yml", ".json", ".toml", ".ini", ".cfg", ".md"
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

SKIP_SUBSTRINGS = [
    "/node_modules/",
    "/.git/",
    "/dist/",
    "/build/",
    "/.cache/",
    "/.venv/",
    "/venv/",
    "/env/",
    "/.pytest_cache/",
    "/.mypy_cache/",
    "/.ruff_cache/",
]


def _choose_index() -> Path:
    existing = [p for p in INDEX_CANDIDATES if p.exists()]
    if not existing:
        return INDEX_CANDIDATES[0]
    return sorted(existing, key=lambda p: (p.stat().st_size, p.stat().st_mtime), reverse=True)[0]


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

def normalize(path: str) -> str:
    return path.replace("\\", "/").lower()

def project_root(root: str, path: str) -> str:
    # group by first directory under root
    if not path.startswith(root):
        return root
    rel = path[len(root):].lstrip("/")
    if not rel:
        return root
    first = rel.split("/", 1)[0]
    return root.rstrip("/") + "/" + first

def score_project(root: str, s: Dict[str, Any]) -> Dict[str, Any]:
    code_files = s["code_files"]
    unique_ext = len(s["extensions"])
    score = math.log1p(code_files) * 0.9 + unique_ext * 0.2
    reasons = [f"code_files={code_files}", f"unique_ext={unique_ext}"]
    for kw, w in KEYWORD_WEIGHTS.items():
        if kw in root:
            score += w
            reasons.append(f"kw:{kw}")
    return {
        "root": root,
        "score": round(score, 3),
        "code_files": code_files,
        "unique_extensions": unique_ext,
        "top_extensions": sorted(s["extensions"].items(), key=lambda x: x[1], reverse=True)[:8],
        "examples": sorted(list(s["examples"]))[:3],
        "reasons": reasons[:8],
    }

def main():
    index_path = _choose_index()
    out_path = _choose_logs_dir() / "selected_ranking.json"
    if not index_path.exists():
        print("No file index found. Run a scan first.")
        return

    stats: Dict[str, Dict[str, Any]] = {}
    root_stats: Dict[str, Dict[str, Any]] = {r: {"code_files": 0} for r in ROOTS}

    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            path = rec.get("path") or ""
            norm = normalize(path)
            if any(s in norm for s in SKIP_SUBSTRINGS):
                continue

            ext = rec.get("extension") or Path(norm).suffix.lower()
            if ext not in CODE_EXTS:
                continue

            for root in ROOTS:
                if norm.startswith(root):
                    root_stats[root]["code_files"] += 1
                    proj = project_root(root, norm)
                    entry = stats.setdefault(proj, {"code_files": 0, "extensions": {}, "examples": set()})
                    entry["code_files"] += 1
                    entry["extensions"][ext] = entry["extensions"].get(ext, 0) + 1
                    if len(entry["examples"]) < 3:
                        entry["examples"].add(norm)
                    break

    ranked = []
    for root, s in stats.items():
        if s["code_files"] < 10:
            continue
        ranked.append(score_project(root, s))

    ranked.sort(key=lambda x: x["score"], reverse=True)

    out_path.write_text(json.dumps({
        "roots": ROOTS,
        "root_code_files": root_stats,
        "ranked": ranked
    }, indent=2), encoding="utf-8")

    print(f"index={index_path}")
    print(f"output={out_path}")
    print("roots:")
    for r, rs in root_stats.items():
        print(f"- {r} code_files={rs['code_files']}")
    print("top10:")
    for r in ranked[:10]:
        print(f"- {r['score']:>6} | {r['root']} | code_files={r['code_files']}")

if __name__ == "__main__":
    main()
