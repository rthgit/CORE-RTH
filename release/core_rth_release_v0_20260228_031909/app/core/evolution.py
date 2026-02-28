"""
Read-only evolution analyzer. Builds project inventory and proposals.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple
from pathlib import Path
import json
import tempfile
import os

MARKER_TYPES = {
    "package.json": ["node"],
    "requirements.txt": ["python"],
    "pyproject.toml": ["python"],
    "pipfile": ["python"],
    "cargo.toml": ["rust"],
    "go.mod": ["go"],
    "pom.xml": ["java"],
    "build.gradle": ["java"],
    "build.gradle.kts": ["java"],
    "composer.json": ["php"],
    "gemfile": ["ruby"],
    "mix.exs": ["elixir"],
    "cmakelists.txt": ["native"],
    "makefile": ["native"]
}

LOCKFILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pipfile.lock",
    "composer.lock",
    "cargo.lock",
    "gemfile.lock",
    "go.sum",
}

README_NAMES = {"readme.md", "readme.txt", "readme"}
LICENSE_NAMES = {"license", "license.txt", "license.md"}

@dataclass
class ProjectSignal:
    root: str
    types: Set[str] = field(default_factory=set)
    markers: Set[str] = field(default_factory=set)
    file_count: int = 0
    ext_counts: Dict[str, int] = field(default_factory=dict)
    has_readme: bool = False
    has_license: bool = False
    has_ci: bool = False
    has_tests: bool = False
    has_lock: bool = False

class EvolutionAnalyzer:
    def __init__(self):
        self.index_path = self._select_index_path()

    def _select_index_path(self) -> Path:
        env_base = os.getenv("RTH_MEMORY_BASE", "").strip()
        if env_base:
            # For isolated benchmark runs, force the dedicated memory index.
            return Path(env_base) / "files.jsonl"
        candidates = [
            Path("storage") / "memory" / "files.jsonl",
            Path("storage_runtime") / "memory" / "files.jsonl",
            Path(tempfile.gettempdir()) / "rth_core" / "memory" / "files.jsonl",
        ]
        existing = [p for p in candidates if p.exists()]
        if not existing:
            return candidates[0]
        return sorted(existing, key=lambda p: (p.stat().st_size, p.stat().st_mtime), reverse=True)[0]

    def propose(self, roots: Optional[List[str]] = None, max_projects: int = 200) -> Dict[str, Any]:
        self.index_path = self._select_index_path()
        if not self.index_path.exists():
            return {"status": "no_index", "detail": "Run a filesystem scan first."}

        roots_norm = None
        if roots:
            roots_norm = {self._normalize(r) for r in roots}

        project_map = self._discover_projects(roots_norm)
        if not project_map:
            return {"status": "no_projects", "detail": "No project markers found."}

        self._analyze_files(project_map, roots_norm)

        projects = []
        proposals = []
        for info in list(project_map.values())[:max_projects]:
            domains = self._detect_domains(info)
            project_entry = {
                "root": info.root,
                "types": sorted(info.types),
                "markers": sorted(info.markers),
                "file_count": info.file_count,
                "top_extensions": self._top_exts(info.ext_counts, 8),
                "domains": domains,
            }
            projects.append(project_entry)
            proposals.append(self._make_proposals(info))

        return {
            "status": "ok",
            "projects_found": len(project_map),
            "projects_returned": len(projects),
            "projects": projects,
            "proposals": [p for p in proposals if p["recommendations"]],
        }

    def _discover_projects(self, roots_norm: Optional[Set[str]]) -> Dict[str, ProjectSignal]:
        project_map: Dict[str, ProjectSignal] = {}
        with open(self.index_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                path = record.get("path")
                if not path:
                    continue
                norm = self._normalize(path)
                if roots_norm and not self._path_in_roots(norm, roots_norm):
                    continue

                dirname = self._dirname(norm)
                filename = self._basename(norm)
                lower_name = filename.lower()

                if lower_name.endswith(".sln") or lower_name.endswith(".csproj"):
                    info = project_map.get(dirname) or ProjectSignal(root=dirname)
                    info.types.add("dotnet")
                    info.markers.add(filename)
                    project_map[dirname] = info
                    continue

                if lower_name in MARKER_TYPES:
                    info = project_map.get(dirname) or ProjectSignal(root=dirname)
                    for t in MARKER_TYPES[lower_name]:
                        info.types.add(t)
                    info.markers.add(filename)
                    project_map[dirname] = info

        return project_map

    def _analyze_files(self, project_map: Dict[str, ProjectSignal], roots_norm: Optional[Set[str]]):
        root_keys = {self._normalize(p.root) for p in project_map.values()}
        with open(self.index_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except Exception:
                    continue
                path = record.get("path")
                if not path:
                    continue
                norm = self._normalize(path)
                if roots_norm and not self._path_in_roots(norm, roots_norm):
                    continue
                root_key = self._find_project_root(norm, root_keys)
                if not root_key:
                    continue

                info = project_map.get(root_key)
                if not info:
                    continue

                info.file_count += 1
                ext = Path(norm).suffix.lower()
                info.ext_counts[ext] = info.ext_counts.get(ext, 0) + 1

                name = self._basename(norm).lower()
                if name in README_NAMES:
                    info.has_readme = True
                if name in LICENSE_NAMES:
                    info.has_license = True
                if name in LOCKFILES:
                    info.has_lock = True
                if "/.github/workflows/" in norm or name == ".gitlab-ci.yml" or "/.circleci/" in norm:
                    info.has_ci = True
                if "/test/" in norm or "/tests/" in norm or name.startswith("test_") or name.endswith("_test.py"):
                    info.has_tests = True

    def _make_proposals(self, info: ProjectSignal) -> Dict[str, Any]:
        recs = []
        evidence = []
        domains = self._detect_domains(info)
        if info.markers:
            evidence.append("markers: " + ", ".join(sorted(info.markers)))
        if domains:
            evidence.append("domains: " + ", ".join(domains))

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

        recs.extend(self._domain_recommendations(info, domains))
        recs = self._dedupe_keep_order(recs)

        return {
            "root": info.root,
            "types": sorted(info.types),
            "domains": domains,
            "recommendations": recs,
            "evidence": evidence
        }

    def _detect_domains(self, info: ProjectSignal) -> List[str]:
        root = self._normalize(info.root)
        domains: List[str] = []
        exts = set((k or "").lower() for k in info.ext_counts.keys())
        markers = {m.lower() for m in info.markers}

        if "sublimeomnidoc" in root or ("src-tauri" in root and ".rs" in exts):
            domains.append("doc_reader_desktop")
        if "lettore" in root and "document" in root:
            domains.append("doc_reader_desktop")

        if any(k in root for k in ["antihaker", "shannon", "recon"]) or "security" in root:
            domains.append("security_orchestrator")

        if any(k in root for k in ["jarvis", "swarm", "agent", "plugin", "core rth"]) or {
            ".py", ".ts"
        }.issubset(exts):
            if "agent" in root or "swarm" in root or "core rth" in root:
                domains.append("agent_orchestration")

        if "cargo.toml" in markers and "package.json" in markers:
            # Hybrid desktop stacks often need cross-runtime coordination.
            if "doc_reader_desktop" not in domains:
                domains.append("desktop_hybrid")

        return self._dedupe_keep_order(domains)

    def _domain_recommendations(self, info: ProjectSignal, domains: List[str]) -> List[str]:
        root = self._normalize(info.root)
        exts = set((k or "").lower() for k in info.ext_counts.keys())
        recs: List[str] = []

        if "doc_reader_desktop" in domains:
            recs.extend([
                "Create a format regression corpus (PDF/DOCX/RTF/ODT/images) and run snapshot checks on rendering output.",
                "Add crash-safe session restore for open tabs/workspace state to protect long document review flows.",
                "Define a document parser capability matrix (internal renderer vs optional engines) and expose unsupported-edge-case tests.",
                "Separate untrusted document parsing from UI state with explicit sandbox boundaries and failure isolation.",
                "Add file-association safety checks (path quoting, spaces, unicode, huge file paths) for Windows launcher integration.",
            ])
            if ".tsx" in exts and ".rs" in exts:
                recs.extend([
                    "Add a cross-runtime contract test between Tauri commands (Rust) and frontend calls (TypeScript) to catch schema drift.",
                    "Version the app<->core IPC payloads so future AI/OnlyOffice/Ollama adapters cannot silently break desktop flows.",
                ])
            if "sublimeomnidoc" in root:
                recs.append("Add deterministic import/export smoke tests for annotated PDFs and markdown/code tabs to protect the core workflow.")

        if "security_orchestrator" in domains:
            recs.extend([
                "Make target authorization explicit with a signed/immutable target manifest required before any active security phase.",
                "Default every workflow to dry-run/recon-only mode and require a separate approval token for exploit-capable steps.",
                "Add tamper-evident audit logs (hash chain per workflow step) so outputs remain defensible for reviews and reports.",
                "Redact secrets/API keys from logs and reports by default before persisting artifacts to scan results folders.",
                "Define per-phase model budget caps and timeout policies (recon/vuln/exploit/report) to prevent runaway cost or latency.",
                "Add a replay mode that reuses cached HTTP evidence and tool outputs for report regeneration without re-touching target systems.",
            ])
            if "shannon" in root:
                recs.extend([
                    "Add a safe 'status-only health probe' command path with machine-readable exit codes for operator dashboards.",
                    "Split operator-facing launcher UX from engine internals so endpoint misuse cannot bypass policy checks.",
                ])

        if "agent_orchestration" in domains:
            recs.extend([
                "Version capability contracts (scan/run/build/social/payments) and validate requests against a schema before routing.",
                "Add deterministic approval state-machine tests for propose/approve/deny/expire flows to harden governance behavior.",
                "Record action traces as structured events (intent, capability, consent, result, rollback) for replay and debugging.",
                "Isolate adapters/plugins with explicit I/O boundaries and health probes so one failing integration cannot poison the core loop.",
            ])

        return recs

    def _dedupe_keep_order(self, items: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for item in items:
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    def _top_exts(self, counts: Dict[str, int], limit: int) -> List[Dict[str, Any]]:
        items = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [{"ext": k if k else "(none)", "count": v} for k, v in items]

    def _normalize(self, path: str) -> str:
        return path.replace("\\", "/").lower()

    def _basename(self, path: str) -> str:
        if "/" not in path:
            return path
        return path.rsplit("/", 1)[-1]

    def _dirname(self, path: str) -> str:
        if "/" not in path:
            return ""
        return path.rsplit("/", 1)[0]

    def _path_in_roots(self, path: str, roots_norm: Set[str]) -> bool:
        for root in roots_norm:
            if path.startswith(root):
                return True
        return False

    def _find_project_root(self, path: str, root_keys: Set[str]) -> Optional[str]:
        current = self._dirname(path)
        while current:
            if current in root_keys:
                return current
            parent = self._dirname(current)
            if parent == current:
                break
            current = parent
        return None

evolution_analyzer = EvolutionAnalyzer()
