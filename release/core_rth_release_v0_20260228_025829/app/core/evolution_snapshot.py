"""
Evolution snapshot builder.

Builds a cached `logs/evolution_snapshot.json` from the large `files.jsonl` index.
This is intentionally a background job to keep the API responsive.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import tempfile
import threading
import time

from .permissions import permission_gate, Capability, RiskLevel
from .memory_vault import memory_vault
from .root_policy import dedupe_nested_roots, load_strategic_roots, normalize_path, is_within_roots
from .evolution import MARKER_TYPES, LOCKFILES, README_NAMES, LICENSE_NAMES, ProjectSignal

logger = logging.getLogger(__name__)


def _choose_logs_dir() -> Path:
    candidates = [
        Path("logs"),
        Path("storage_runtime") / "logs",
        Path(tempfile.gettempdir()) / "rth_core" / "logs",
    ]
    for base in candidates:
        try:
            base.mkdir(parents=True, exist_ok=True)
            probe = base / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return base
        except Exception:
            continue
    base = Path(tempfile.gettempdir()) / "rth_core" / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _select_index_path() -> Path:
    candidates = [
        Path("storage") / "memory" / "files.jsonl",
        Path("storage_runtime") / "memory" / "files.jsonl",
        Path(tempfile.gettempdir()) / "rth_core" / "memory" / "files.jsonl",
    ]
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return candidates[0]
    return sorted(existing, key=lambda p: (p.stat().st_size, p.stat().st_mtime), reverse=True)[0]


def _basename(path: str) -> str:
    if "/" not in path:
        return path
    return path.rsplit("/", 1)[-1]


def _dirname(path: str) -> str:
    if "/" not in path:
        return ""
    return path.rsplit("/", 1)[0]


def _top_exts(counts: Dict[str, int], limit: int = 8) -> List[Dict[str, Any]]:
    items = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"ext": k if k else "(none)", "count": v} for k, v in items]


def _make_recommendations(info: ProjectSignal) -> Dict[str, Any]:
    recs = []
    evidence = []
    if info.markers:
        evidence.append("markers: " + ", ".join(sorted(info.markers)))

    if not info.has_readme:
        recs.append("Add or refresh README with purpose, setup, and run steps.")
    if not info.has_tests:
        recs.append("Add a minimal test harness to prevent regressions.")
    if not info.has_ci:
        recs.append("Add CI to run tests and basic linting on commits.")
    if not info.has_license:
        recs.append("Add a LICENSE file to clarify usage rights.")

    if "node" in info.types and not info.has_lock:
        recs.append("Generate a lockfile to pin Node dependencies.")
    if "python" in info.types and not info.has_lock:
        recs.append("Pin Python dependencies with a lockfile or exact versions.")

    return {
        "root": info.root,
        "types": sorted(info.types),
        "recommendations": recs,
        "evidence": evidence,
    }


@dataclass
class SnapshotJob:
    job_id: str
    request_id: str
    status: str
    started_at: str
    roots: List[str]
    max_projects: int
    index_path: str
    progress: Dict[str, Any]
    result_path: Optional[str] = None
    error: Optional[str] = None
    ended_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "request_id": self.request_id,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "roots": self.roots,
            "max_projects": self.max_projects,
            "index_path": self.index_path,
            "progress": self.progress,
            "result_path": self.result_path,
            "error": self.error,
        }


class EvolutionSnapshotService:
    def __init__(self):
        self._jobs: Dict[str, SnapshotJob] = {}
        self._lock = threading.Lock()

    def propose(self, roots: Optional[List[str]] = None, max_projects: int = 800, reason: str = "Rebuild evolution snapshot") -> Dict[str, Any]:
        strategic = dedupe_nested_roots([normalize_path(r) for r in (roots or load_strategic_roots())])
        scope = {
            "roots": strategic,
            "max_projects": int(max_projects),
        }
        req = permission_gate.propose(
            capability=Capability.FILESYSTEM_WRITE,
            action="evolution_snapshot_build",
            scope=scope,
            reason=reason,
            risk=RiskLevel.HIGH,
        )
        return req.to_dict()

    def start(self, request_id: str) -> Dict[str, Any]:
        if not permission_gate.check(request_id):
            return {"status": "denied", "request_id": request_id}
        req = permission_gate.requests.get(request_id)
        if not req:
            return {"status": "not_found", "request_id": request_id}
        scope = req.scope or {}

        roots = [normalize_path(r) for r in (scope.get("roots") or [])]
        if not roots:
            roots = load_strategic_roots()
        roots = dedupe_nested_roots(roots)

        max_projects = int(scope.get("max_projects") or 800)
        index_path = _select_index_path()

        job_id = f"evo_{int(time.time()*1000)}"
        job = SnapshotJob(
            job_id=job_id,
            request_id=request_id,
            status="running",
            started_at=datetime.now().isoformat(),
            roots=roots,
            max_projects=max_projects,
            index_path=str(index_path),
            progress={"phase": "queued"},
        )
        with self._lock:
            self._jobs[job_id] = job

        t = threading.Thread(target=self._run_job, args=(job_id,), daemon=True)
        t.start()

        memory_vault.record_event("evolution_snapshot_job_started", {"job_id": job_id, "request_id": request_id, "roots": roots})
        return {"status": "started", "job": job.to_dict()}

    def jobs(self) -> Dict[str, Any]:
        with self._lock:
            items = [j.to_dict() for j in self._jobs.values()]
        items.sort(key=lambda x: x.get("started_at", ""), reverse=True)
        return {"count": len(items), "items": items}

    def status(self) -> Dict[str, Any]:
        latest = None
        with self._lock:
            if self._jobs:
                latest = sorted(self._jobs.values(), key=lambda j: j.started_at, reverse=True)[0].to_dict()
        return {
            "module": "evolution_snapshot",
            "index_path": str(_select_index_path()),
            "jobs": self.jobs(),
            "latest_job": latest,
        }

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            return

        try:
            index_path = Path(job.index_path)
            if not index_path.exists():
                raise FileNotFoundError(f"files.jsonl not found: {index_path}")

            # Phase 1: discover project roots by marker files.
            job.progress = {"phase": "discover", "bytes": 0, "projects": 0}
            project_map: Dict[str, ProjectSignal] = {}

            size = index_path.stat().st_size
            t0 = time.perf_counter()
            bytes_read = 0
            with open(index_path, "rb") as f:
                i = 0
                while True:
                    line = f.readline()
                    if not line:
                        break
                    i += 1
                    bytes_read += len(line)
                    if i % 200_000 == 0:
                        job.progress.update({"bytes": bytes_read, "pct": round((bytes_read / max(1, size)) * 100.0, 2), "projects": len(project_map)})
                    try:
                        record = json.loads(line)
                    except Exception:
                        continue
                    path = normalize_path(record.get("path", ""))
                    if not path or not is_within_roots(path, job.roots):
                        continue
                    name = _basename(path).lower()
                    dirname = _dirname(path)

                    if name.endswith(".sln") or name.endswith(".csproj"):
                        info = project_map.get(dirname) or ProjectSignal(root=dirname)
                        info.types.add("dotnet")
                        info.markers.add(name)
                        project_map[dirname] = info
                        continue

                    if name in MARKER_TYPES:
                        info = project_map.get(dirname) or ProjectSignal(root=dirname)
                        for t in MARKER_TYPES[name]:
                            info.types.add(t)
                        info.markers.add(name)
                        project_map[dirname] = info

            if not project_map:
                raise RuntimeError("No projects discovered (no markers under selected roots).")

            # Phase 2: analyze files and attach to nearest project root.
            job.progress = {"phase": "analyze", "bytes": 0, "pct": 0.0, "projects": len(project_map)}
            project_roots = set(project_map.keys())
            dir_cache: Dict[str, Optional[str]] = {}

            def find_project_root(dir_path: str) -> Optional[str]:
                if dir_path in dir_cache:
                    return dir_cache[dir_path]
                cur = dir_path
                while cur:
                    if cur in project_roots:
                        dir_cache[dir_path] = cur
                        return cur
                    parent = _dirname(cur)
                    if parent == cur:
                        break
                    cur = parent
                dir_cache[dir_path] = None
                return None

            bytes_read = 0
            with open(index_path, "rb") as f:
                i = 0
                while True:
                    line = f.readline()
                    if not line:
                        break
                    i += 1
                    bytes_read += len(line)
                    if i % 200_000 == 0:
                        job.progress.update({"bytes": bytes_read, "pct": round((bytes_read / max(1, size)) * 100.0, 2), "dirs_cached": len(dir_cache)})
                    try:
                        record = json.loads(line)
                    except Exception:
                        continue
                    path = normalize_path(record.get("path", ""))
                    if not path or not is_within_roots(path, job.roots):
                        continue

                    dir_path = _dirname(path)
                    root = find_project_root(dir_path)
                    if not root:
                        continue
                    info = project_map.get(root)
                    if not info:
                        continue

                    info.file_count += 1
                    ext = Path(path).suffix.lower()
                    info.ext_counts[ext] = info.ext_counts.get(ext, 0) + 1

                    name = _basename(path).lower()
                    if name in README_NAMES:
                        info.has_readme = True
                    if name in LICENSE_NAMES:
                        info.has_license = True
                    if name in LOCKFILES:
                        info.has_lock = True
                    if "/.github/workflows/" in path or name == ".gitlab-ci.yml" or "/.circleci/" in path:
                        info.has_ci = True
                    if "/test/" in path or "/tests/" in path or name.startswith("test_") or name.endswith("_test.py"):
                        info.has_tests = True

            # Build snapshot payload.
            projects = sorted(project_map.values(), key=lambda x: (x.file_count, x.root), reverse=True)
            projects = projects[: max(1, int(job.max_projects))]

            out_projects = []
            out_proposals = []
            for info in projects:
                out_projects.append(
                    {
                        "root": info.root,
                        "types": sorted(info.types),
                        "markers": sorted(info.markers),
                        "file_count": info.file_count,
                        "top_extensions": _top_exts(info.ext_counts, 8),
                    }
                )
                rec = _make_recommendations(info)
                if rec.get("recommendations"):
                    out_proposals.append(rec)

            payload = {
                "status": "ok",
                "timestamp": datetime.now().isoformat(),
                "strategic_roots": job.roots,
                "index": {
                    "path": str(index_path),
                    "size": index_path.stat().st_size,
                    "mtime": datetime.fromtimestamp(index_path.stat().st_mtime).isoformat(),
                    "elapsed_s": round(time.perf_counter() - t0, 3),
                },
                "projects_found": len(project_map),
                "projects_returned": len(out_projects),
                "projects": out_projects,
                "proposals": out_proposals,
            }

            logs = _choose_logs_dir()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            snap_path = logs / "evolution_snapshot.json"
            snap_hist = logs / f"evolution_snapshot_{ts}.json"
            snap_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            snap_hist.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            job.status = "completed"
            job.result_path = str(snap_path)
            job.ended_at = datetime.now().isoformat()
            job.progress = {"phase": "completed", "projects_found": len(project_map), "projects_returned": len(out_projects)}

            memory_vault.record_event("evolution_snapshot_built", {"path": str(snap_path), "projects_found": len(project_map), "roots": job.roots})
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.ended_at = datetime.now().isoformat()
            job.progress = {"phase": "failed"}
            logger.error(f"Evolution snapshot job failed: {e}")

        with self._lock:
            self._jobs[job_id] = job


evolution_snapshot_service = EvolutionSnapshotService()
