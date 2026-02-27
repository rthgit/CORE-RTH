"""
Infer personal project roots from file index (no marker files required)
and rank them by code density and relevance to the core vision.
"""
import json
import math
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Set

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

CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".cs",
    ".cpp", ".c", ".h", ".hpp", ".kt", ".kts", ".swift", ".php", ".rb",
    ".lua", ".sql", ".sh", ".ps1", ".bat", ".cmd", ".psm1", ".yaml",
    ".yml", ".json", ".toml", ".ini", ".cfg", ".md"
}

CONTAINERS = {
    "projects", "project", "work", "code", "dev", "apps", "clients",
    "client", "lab", "labs", "repos", "repo", "workspace", "workspaces"
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

def pick_root(norm_path: str) -> str:
    # norm_path like d:/dir1/dir2/dir3/file.ext
    parts = [p for p in norm_path.split("/") if p]
    if not parts:
        return norm_path
    # parts[0] = "d:" or "c:"
    drive = parts[0]
    rest = parts[1:]
    if not rest:
        return drive + "/"

    # If under users/<name>/..., try to find container
    if len(rest) >= 2 and rest[0] == "users":
        user = rest[1]
        tail = rest[2:]
        for i, p in enumerate(tail):
            if p in CONTAINERS and i + 1 < len(tail):
                return "/".join([drive, "users", user, p, tail[i + 1]])
        # fallback: users/<name>/<next>
        if len(tail) >= 1:
            return "/".join([drive, "users", user, tail[0]])
        return "/".join([drive, "users", user])

    # generic container logic
    for i, p in enumerate(rest):
        if p in CONTAINERS and i + 1 < len(rest):
            return "/".join([drive] + rest[: i + 2])

    # fallback: drive + first two segments
    if len(rest) >= 2:
        return "/".join([drive, rest[0], rest[1]])
    return "/".join([drive, rest[0]])

def main():
    index_path = _choose_index()
    out_path = _choose_logs_dir() / "personal_project_ranking.json"

    if not index_path.exists():
        print("No file index found. Run a scan first.")
        return

    stats: Dict[str, Dict[str, Any]] = {}

    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            path = rec.get("path")
            if not path:
                continue
            norm = normalize(path)
            if any(s in norm for s in SKIP_SUBSTRINGS):
                continue

            ext = (rec.get("extension") or Path(norm).suffix.lower())
            if ext not in CODE_EXTS:
                continue

            root = pick_root(norm)
            entry = stats.setdefault(root, {
                "code_files": 0,
                "extensions": {},
                "examples": set(),
            })
            entry["code_files"] += 1
            entry["extensions"][ext] = entry["extensions"].get(ext, 0) + 1
            if len(entry["examples"]) < 3:
                entry["examples"].add(norm)

    ranked = []
    for root, s in stats.items():
        code_files = s["code_files"]
        if code_files < 60:
            continue
        unique_ext = len(s["extensions"])
        score = math.log1p(code_files) * 0.9 + unique_ext * 0.2
        reasons = [f"code_files={code_files}", f"unique_ext={unique_ext}"]

        for kw, w in KEYWORD_WEIGHTS.items():
            if kw in root:
                score += w
                reasons.append(f"kw:{kw}")

        ranked.append({
            "root": root,
            "score": round(score, 3),
            "code_files": code_files,
            "unique_extensions": unique_ext,
            "top_extensions": sorted(s["extensions"].items(), key=lambda x: x[1], reverse=True)[:8],
            "examples": sorted(list(s["examples"])),
            "reasons": reasons[:8]
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    out_path.write_text(json.dumps({"ranked": ranked}, indent=2), encoding="utf-8")

    print(f"index={index_path}")
    print(f"output={out_path}")
    print(f"ranked={len(ranked)}")
    for r in ranked[:12]:
        print(f"- {r['score']:>6} | {r['root']} | code_files={r['code_files']} | exts={r['unique_extensions']}")

if __name__ == "__main__":
    main()
