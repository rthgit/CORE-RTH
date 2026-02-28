"""
Strategic portfolio engine for high-impact local assets.
Focuses on actionable integration proposals for Jarvis.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import math
import logging
import os

from .governance import governance_queue
from .plugin_hub import plugin_hub

logger = logging.getLogger(__name__)


BASE_ROOTS = [
    "c:/users/pc/desktop/biome",
    "d:/codex",
    "d:/simulatore_rcq",
    "d:/core rth",
]

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".md", ".go", ".rs", ".java", ".cs",
    ".cpp", ".c", ".h", ".hpp", ".sql", ".sh", ".ps1", ".bat",
    ".cmd", ".php", ".rb", ".lua",
}

EXCLUDED_PARTS = {
    "node_modules", ".git", ".venv", "venv", "dist", "build", ".cache",
    "coverage", "tmp", "temp", "__pycache__",
}

EXCLUDED_SUBSTRINGS = tuple(f"/{p}/" for p in sorted(EXCLUDED_PARTS))

KEYWORD_BONUS = {
    "assistant": 3.0,
    "jarvis": 2.6,
    "agent": 2.0,
    "swarm": 2.0,
    "orchestr": 1.8,
    "simulatore": 2.7,
    "biome": 1.8,
    "core": 1.8,
    "runtime": 1.5,
    "server": 1.4,
    "hybrid": 1.7,
    "plugin": 1.4,
    "model": 1.2,
    "knowledge": 1.6,
    "expansion": 1.4,
}

KEYWORD_PENALTY = {
    "test": 0.9,
    "example": 1.0,
    "fixture": 1.0,
    "debug": 0.7,
    "logs": 0.8,
}


@dataclass
class StrategicAsset:
    rank: int
    root: str
    score: float
    files: int
    utilization: str
    evolution: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "root": self.root,
            "score": self.score,
            "files": self.files,
            "utilization": self.utilization,
            "evolution": self.evolution,
        }


class StrategyEngine:
    def __init__(self):
        self.index_path = self._select_index_path()
        self.last_assets: List[StrategicAsset] = []
        self._precomputed_paths = [
            Path("logs") / "selected_ranking.json",
            Path("logs") / "personal_project_ranking.json",
            Path("logs") / "project_ranking.json",
        ]
        self._cache_path = Path("storage") / "strategy" / "top_assets_cache.json"

    def _select_index_path(self) -> Path:
        env_base = os.getenv("RTH_MEMORY_BASE", "").strip()
        if env_base:
            return Path(env_base) / "files.jsonl"
        return Path("storage") / "memory" / "files.jsonl"

    def top_assets(self, limit: int = 50) -> Dict[str, Any]:
        rows = self._collect_assets()
        assets = []
        for i, row in enumerate(rows[:limit], 1):
            assets.append(
                StrategicAsset(
                    rank=i,
                    root=row["root"],
                    score=row["score"],
                    files=row["files"],
                    utilization=row["utilization"],
                    evolution=row["evolution"],
                )
            )
        self.last_assets = assets
        return {
            "status": "ok",
            "count": len(assets),
            "assets": [a.to_dict() for a in assets],
        }

    def launch_phase1(self) -> Dict[str, Any]:
        return self._launch_phase(start=0, count=3, phase_name="phase1")

    def launch_phase2(self) -> Dict[str, Any]:
        return self._launch_phase(start=3, count=7, phase_name="phase2")

    def _launch_phase(self, start: int, count: int, phase_name: str) -> Dict[str, Any]:
        if not self.last_assets:
            self.top_assets(limit=50)
        targets = self.last_assets[start:start + count]
        if len(targets) < count:
            self.top_assets(limit=max(50, start + count))
            targets = self.last_assets[start:start + count]

        if not targets:
            return {"status": "empty", "detail": "No strategic assets found."}

        source = f"strategy_{phase_name}"
        plan = []
        high_ranked = []
        for asset in targets:
            plan.append({
                "id": f"{phase_name}-{asset.rank}",
                "title": f"Integrate strategic asset: {asset.root}",
                "component": "praxis/swarm",
                "rationale": f"{asset.utilization}. Priority score={asset.score}.",
                "proposed_changes": [
                    "Define adapter boundary and public interface.",
                    "Map reusable modules and dependency risks.",
                    "Prepare plugin activation checklist with rollback.",
                ],
                "requires_approval": True,
            })
            high_ranked.append({
                "root": asset.root,
                "score": asset.score,
                "source": source,
                "reasons": [asset.utilization, asset.evolution],
            })

        seeded = governance_queue.seed_from_plan(plan, source=source)
        plugin_sync = plugin_hub.sync_from_high_ranked(high_ranked)
        return {
            "status": "ok",
            "phase": phase_name,
            "targets": [a.to_dict() for a in targets],
            "governance_seeded": seeded,
            "governance_summary": governance_queue.summary(),
            "plugin_sync": plugin_sync,
        }

    def _collect_assets(self) -> List[Dict[str, Any]]:
        precomputed = self._load_precomputed_assets()
        if precomputed:
            return precomputed

        cached = self._load_cache()
        if cached:
            return cached

        lvl1 = self._group_level_one()
        if not lvl1:
            return []

        rows = []
        for root, stats in lvl1.items():
            if stats["files"] < 8:
                continue
            rows.append({
                "root": root,
                "files": stats["files"],
                "unique_ext": len(stats["ext"]),
            })

        # Expand extra-large roots for better strategic granularity.
        parents = [r["root"] for r in sorted(rows, key=lambda x: x["files"], reverse=True) if r["files"] >= 1200][:12]
        lvl2 = self._group_level_two(parents)
        for root, stats in lvl2.items():
            if stats["files"] < 20:
                continue
            rows.append({
                "root": root,
                "files": stats["files"],
                "unique_ext": len(stats["ext"]),
            })

        dedup: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            key = row["root"].lower()
            if key not in dedup or row["files"] > dedup[key]["files"]:
                dedup[key] = row

        out = []
        for row in dedup.values():
            root = row["root"]
            files = row["files"]
            unique_ext = row["unique_ext"]
            score = self._score(root, files, unique_ext)
            out.append({
                "root": root,
                "score": score,
                "files": files,
                "utilization": self._infer_use(root),
                "evolution": self._infer_evolution(files, unique_ext),
            })

        out.sort(key=lambda x: x["score"], reverse=True)
        self._save_cache(out)
        return out

    def _load_precomputed_assets(self) -> List[Dict[str, Any]]:
        """
        Prefer fast, precomputed rankings if available.

        This avoids re-scanning very large `files.jsonl` on every request.
        """
        # For isolated benchmark runs, precomputed rankings are unrelated and would poison results.
        if os.getenv("RTH_MEMORY_BASE", "").strip():
            return []
        idx_mtime = None
        try:
            if self.index_path.exists():
                idx_mtime = float(self.index_path.stat().st_mtime)
        except Exception:
            idx_mtime = None

        for path in self._precomputed_paths:
            if not path.exists():
                continue

            # If the filesystem index is newer than the precomputed file,
            # treat it as stale and prefer rebuilding a fresh cache.
            try:
                if idx_mtime and float(path.stat().st_mtime) < idx_mtime:
                    continue
            except Exception:
                pass
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

            ranked = payload.get("ranked", [])
            if not isinstance(ranked, list) or not ranked:
                continue

            items: List[Dict[str, Any]] = []
            for item in ranked:
                try:
                    root = str(item.get("root", "")).strip()
                except Exception:
                    continue
                if not root:
                    continue

                low_root = root.replace("\\", "/").lower()
                if not any(low_root.startswith(base) for base in BASE_ROOTS):
                    # Keep strategy focused on the high-value bases.
                    continue

                try:
                    score = float(item.get("score", 0.0))
                except Exception:
                    score = 0.0

                files = item.get("code_files", item.get("file_count", 0))
                try:
                    files_i = int(files)
                except Exception:
                    files_i = 0

                unique_ext = item.get("unique_extensions", 0)
                try:
                    unique_ext_i = int(unique_ext)
                except Exception:
                    unique_ext_i = 0

                items.append(
                    {
                        "root": low_root,
                        "score": score,
                        "files": files_i,
                        "unique_ext": unique_ext_i,
                        "utilization": self._infer_use(low_root),
                        "evolution": self._infer_evolution(files_i, unique_ext_i),
                        "source": str(path),
                        "generated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                    }
                )

            if not items:
                continue

            items.sort(key=lambda x: x["score"], reverse=True)
            logger.info(f"StrategyEngine using precomputed ranking: {path} ({len(items)} items)")
            return items

        return []

    def _load_cache(self) -> List[Dict[str, Any]]:
        try:
            if os.getenv("RTH_MEMORY_BASE", "").strip():
                return []
            if not self._cache_path.exists():
                return []
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
            items = payload.get("items", [])
            if not isinstance(items, list) or not items:
                return []
            # If the index file has changed since caching, ignore cache.
            idx_mtime = None
            if self.index_path.exists():
                idx_mtime = self.index_path.stat().st_mtime
            cached_idx_mtime = payload.get("index_mtime")
            if idx_mtime and cached_idx_mtime and float(cached_idx_mtime) < float(idx_mtime):
                return []
            return items
        except Exception:
            return []

    def _save_cache(self, items: List[Dict[str, Any]]) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload: Dict[str, Any] = {
                "saved_at": datetime.now().isoformat(),
                "index_path": str(self.index_path),
                "index_mtime": self.index_path.stat().st_mtime if self.index_path.exists() else None,
                "count": len(items),
                "items": items,
            }
            self._cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            return

    def _group_level_one(self) -> Dict[str, Dict[str, Any]]:
        groups: Dict[str, Dict[str, Any]] = {}
        for item in self._iterate_index():
            root = self._group_root(item["path"])
            if not root:
                continue
            if root not in groups:
                groups[root] = {"files": 0, "ext": {}}
            groups[root]["files"] += 1
            ext = item["extension"]
            groups[root]["ext"][ext] = groups[root]["ext"].get(ext, 0) + 1
        return groups

    def _group_level_two(self, parents: List[str]) -> Dict[str, Dict[str, Any]]:
        groups: Dict[str, Dict[str, Any]] = {}
        parent_set = {p.lower() for p in parents}
        for item in self._iterate_index():
            path = item["path"]
            for parent in parent_set:
                if not path.startswith(parent + "/"):
                    continue
                rel = path[len(parent):].lstrip("/")
                if not rel:
                    continue
                child = rel.split("/", 1)[0]
                root = f"{parent}/{child}"
                if root == parent:
                    continue
                if root not in groups:
                    groups[root] = {"files": 0, "ext": {}}
                groups[root]["files"] += 1
                ext = item["extension"]
                groups[root]["ext"][ext] = groups[root]["ext"].get(ext, 0) + 1
                break
        return groups

    def _iterate_index(self):
        if not self.index_path.exists():
            return

        # Fast-path: parse just "path" and "extension" from JSONL without json.loads.
        # This matters because files.jsonl can be multi-GB and frequently queried.
        path_key = '"path": "'
        ext_key = '"extension": '

        with open(self.index_path, "rb") as f:
            for raw in f:
                try:
                    line = raw.decode("utf-8", errors="ignore")
                except Exception:
                    continue

                pidx = line.find(path_key)
                if pidx == -1:
                    continue
                pstart = pidx + len(path_key)
                pend = line.find('"', pstart)
                if pend == -1:
                    continue

                # JSON-escaped backslashes become '\\\\' in the file; normalize to forward slashes.
                path = line[pstart:pend].replace("\\\\", "/").replace("\\", "/").lower()
                if not path:
                    continue

                if any(s in path for s in EXCLUDED_SUBSTRINGS):
                    continue

                ext = ""
                eidx = line.find(ext_key)
                if eidx != -1:
                    vpos = eidx + len(ext_key)
                    if vpos < len(line) and line[vpos] == '"':
                        estart = vpos + 1
                        eend = line.find('"', estart)
                        if eend != -1:
                            ext = line[estart:eend].lower()

                if not ext:
                    ext = str(Path(path).suffix.lower())

                if ext not in CODE_EXTENSIONS:
                    continue

                yield {"path": path, "extension": ext}

    def _group_root(self, path: str) -> Optional[str]:
        for base in BASE_ROOTS:
            if not path.startswith(base):
                continue
            rel = path[len(base):].lstrip("/")
            if not rel:
                return base
            # Root-level file: group under the base itself for stability.
            if "/" not in rel:
                return base
            first = rel.split("/", 1)[0]
            return f"{base}/{first}"
        return None

    def _score(self, root: str, files: int, unique_ext: int) -> float:
        score = math.log1p(files) * 1.08 + unique_ext * 0.22
        low = root.lower()
        for key, val in KEYWORD_BONUS.items():
            if key in low:
                score += val
        for key, val in KEYWORD_PENALTY.items():
            if key in low:
                score -= val
        if low.endswith("/code-oss"):
            score -= 1.5
        return round(score, 3)

    def _infer_use(self, root: str) -> str:
        low = root.lower()
        if any(k in low for k in ["assistant", "jarvis", "agent", "swarm"]):
            return "Assistente/agent orchestration"
        if "simulatore" in low:
            return "Simulazione e decision support"
        if "biome" in low:
            return "Pipeline modulare AI/automation"
        if "codex" in low or "code-oss" in low:
            return "Piattaforma dev tooling/editor"
        return "Componente software"

    def _infer_evolution(self, files: int, unique_ext: int) -> str:
        first = "Stabilizzare API interne e contratti" if files >= 25 else "Consolidare struttura minima e setup"
        second = "Aggiungere CI con gate qualita" if unique_ext >= 3 else "Ampliare copertura test su moduli critici"
        return f"{first}; {second}"


strategy_engine = StrategyEngine()
