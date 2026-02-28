"""
Local filesystem scanner with permission gate.
"""
import asyncio
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import os
import fnmatch
import hashlib
import logging
import re
import zipfile
import xml.etree.ElementTree as ET
from .permissions import permission_gate, Capability, RiskLevel
from .memory_vault import memory_vault
from .pathmap import map_path
from .event_bus import get_event_bus, EventType

logger = logging.getLogger(__name__)

DEFAULT_EXCLUDES = [
    "**/Windows/**",
    "**/Program Files/**",
    "**/Program Files (x86)/**",
    "**/ProgramData/**",
    "**/$Recycle.Bin/**",
    "**/System Volume Information/**",
    "**/.git/**",
    "**/node_modules/**",
]

TEXT_EXTENSIONS = {
    ".txt", ".md", ".log", ".py", ".json", ".yaml", ".yml",
    ".ini", ".cfg", ".toml", ".csv", ".ts", ".js", ".html",
    ".css", ".xml", ".rtf"
}

EXTRACTABLE_EXTENSIONS = set(TEXT_EXTENSIONS) | {".docx", ".pdf"}

PROJECT_MARKER_CONCEPTS = {
    "package.json": {"node", "javascript"},
    "pnpm-lock.yaml": {"node"},
    "yarn.lock": {"node"},
    "package-lock.json": {"node"},
    "cargo.toml": {"rust"},
    "tauri.conf.json": {"tauri"},
    "tsconfig.json": {"typescript"},
    "vite.config.ts": {"vite"},
    "vite.config.js": {"vite"},
    "requirements.txt": {"python"},
    "pyproject.toml": {"python"},
}

SCAN_LOCKFILES = {
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "cargo.lock",
    "poetry.lock", "pipfile.lock", "go.sum"
}
SCAN_READMES = {"readme.md", "readme.txt", "readme"}
SCAN_LICENSES = {"license", "license.txt", "license.md"}

@dataclass
class ScanScope:
    roots: List[str]
    exclude_globs: Optional[List[str]] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    include_globs: Optional[List[str]] = None
    max_depth: Optional[int] = None
    max_file_size_mb: Optional[int] = 50
    hash_files: bool = False
    content_snippets: bool = False
    content_full: bool = False
    snippet_bytes: int = 256
    max_files: Optional[int] = None

@dataclass
class ScanProposal:
    request_id: str
    scope: ScanScope
    created_at: str
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "scope": self.scope.__dict__,
            "created_at": self.created_at,
            "status": self.status
        }

class FileSystemScanner:
    def __init__(self):
        self.last_scan: Optional[Dict[str, Any]] = None

    def propose(self, scope: ScanScope, reason: str) -> ScanProposal:
        request = permission_gate.propose(
            capability=Capability.FILESYSTEM_SCAN,
            action="filesystem_scan",
            scope=scope.__dict__,
            reason=reason,
            risk=RiskLevel.HIGH
        )
        proposal = ScanProposal(
            request_id=request.request_id,
            scope=scope,
            created_at=datetime.now().isoformat(),
            status=request.decision.value
        )
        return proposal

    def execute(self, scope: ScanScope, request_id: str) -> Dict[str, Any]:
        if not permission_gate.check(request_id):
            return {"status": "denied", "request_id": request_id}

        files_scanned = 0
        errors = 0
        error_samples: List[Dict[str, str]] = []
        error_sample_limit = 200
        stopped_early = False
        start = datetime.now()
        root_observations: Dict[str, Dict[str, Any]] = {}

        def add_error_sample(path: str, err: Exception | str):
            if len(error_samples) >= error_sample_limit:
                return
            error_samples.append({
                "path": path,
                "error": str(err)[:300]
            })

        for root in scope.roots:
            if stopped_early:
                break
            root_mapped = map_path(root)
            root_path = Path(root_mapped)
            if not root_path.exists():
                continue
            obs = root_observations.setdefault(str(root), self._new_root_observation(root=str(root), mapped=str(root_mapped)))

            def _on_walk_error(exc: OSError):
                nonlocal errors
                errors += 1
                add_error_sample(getattr(exc, "filename", str(root_path)), exc)

            for dirpath, dirnames, filenames in os.walk(root_path, onerror=_on_walk_error):
                if stopped_early:
                    break
                if scope.max_depth is not None:
                    rel = os.path.relpath(dirpath, root_path)
                    depth = 0 if rel == "." else rel.count(os.sep) + 1
                    if depth > scope.max_depth:
                        dirnames[:] = []
                        continue

                for name in filenames:
                    full_path = Path(dirpath) / name
                    path_str = str(full_path)
                    try:
                        if self._is_excluded(path_str, scope.exclude_globs):
                            continue
                        if scope.include_globs and not self._matches_any(path_str, scope.include_globs):
                            continue

                        size = full_path.stat().st_size
                        if scope.max_file_size_mb and scope.max_file_size_mb > 0:
                            if size > scope.max_file_size_mb * 1024 * 1024:
                                continue

                        record = {
                            "path": path_str,
                            "size": size,
                            "mtime": datetime.fromtimestamp(full_path.stat().st_mtime).isoformat(),
                            "extension": full_path.suffix.lower(),
                            "root": str(root_path),
                            "root_original": str(root),
                        }

                        if scope.hash_files:
                            record["sha256"] = self._hash_file(full_path)

                        ext = full_path.suffix.lower()
                        if scope.content_full and ext in EXTRACTABLE_EXTENSIONS:
                            content, content_error = self._read_full(full_path, ext)
                            if content_error:
                                record["content_error"] = content_error
                            if content:
                                content_meta = memory_vault.store_file_content(path_str, content)
                                if content_meta:
                                    record.update(content_meta)
                        elif scope.content_snippets and ext in TEXT_EXTENSIONS:
                            record["snippet"] = self._read_snippet(full_path, scope.snippet_bytes)

                        memory_vault.record_file(record)
                        files_scanned += 1
                        self._update_root_observation(obs, full_path=full_path, root_path=root_path)

                        if scope.max_files and files_scanned >= scope.max_files:
                            stopped_early = True
                            break

                    except Exception as e:
                        errors += 1
                        add_error_sample(path_str, e)
                        continue

        end = datetime.now()
        summary = {
            "status": "completed",
            "request_id": request_id,
            "roots": scope.roots,
            "files_scanned": files_scanned,
            "errors": errors,
            "error_samples": error_samples,
            "stopped_early": stopped_early,
            "started_at": start.isoformat(),
            "completed_at": end.isoformat(),
            "timestamp": end.isoformat()
        }
        self.last_scan = summary
        memory_vault.record_scan(summary)
        try:
            self._publish_scan_fragments(root_observations=root_observations, request_id=request_id, summary=summary)
        except Exception as e:
            logger.warning(f"Failed to publish local scan fragments to KG/Cortex: {e}")
        return summary

    def _new_root_observation(self, root: str, mapped: str) -> Dict[str, Any]:
        return {
            "root_original": root,
            "root_mapped": mapped,
            "files": 0,
            "extensions": Counter(),
            "markers": set(),
            "top_dirs": Counter(),
            "sample_files": [],
            "concepts": set(),
            "entities": set(),
            "has_ci": False,
            "has_tests": False,
            "has_lock": False,
            "has_readme": False,
            "has_license": False,
            "has_launcher": False,
            "has_docker": False,
        }

    def _update_root_observation(self, obs: Dict[str, Any], full_path: Path, root_path: Path) -> None:
        obs["files"] += 1
        ext = full_path.suffix.lower()
        if ext:
            obs["extensions"][ext] += 1

        name_lower = full_path.name.lower()
        if name_lower in PROJECT_MARKER_CONCEPTS:
            obs["markers"].add(name_lower)
            obs["concepts"].update(PROJECT_MARKER_CONCEPTS[name_lower])
        if name_lower in SCAN_LOCKFILES:
            obs["has_lock"] = True
            obs["concepts"].add("dependency_locking")
        if name_lower in SCAN_READMES:
            obs["has_readme"] = True
        if name_lower in SCAN_LICENSES:
            obs["has_license"] = True
        if name_lower.startswith("dockerfile") or name_lower.startswith("docker-compose"):
            obs["has_docker"] = True
            obs["concepts"].add("docker")
        if name_lower.startswith("avvia") and full_path.suffix.lower() in {".cmd", ".bat"}:
            obs["has_launcher"] = True
            obs["concepts"].add("launcher")

        if ext == ".tsx":
            obs["concepts"].update({"typescript", "react"})
        elif ext in {".ts", ".mts", ".cts"}:
            obs["concepts"].add("typescript")
        elif ext == ".rs":
            obs["concepts"].add("rust")
        elif ext in {".ps1", ".cmd", ".bat"}:
            obs["concepts"].add("automation")

        try:
            rel = full_path.relative_to(root_path).as_posix()
        except Exception:
            rel = full_path.as_posix()
        rel_lower = rel.lower()
        if "/.github/workflows/" in rel_lower or rel_lower.endswith("/.gitlab-ci.yml") or rel_lower.startswith(".github/workflows/"):
            obs["has_ci"] = True
            obs["concepts"].add("ci")
        if "/tests/" in rel_lower or "/test/" in rel_lower or rel_lower.startswith("tests/") or rel_lower.startswith("test/"):
            obs["has_tests"] = True
            obs["concepts"].add("testing")
        if rel_lower.endswith("_test.py") or rel_lower.endswith(".test.ts") or rel_lower.endswith(".spec.ts") or rel_lower.endswith(".test.tsx") or rel_lower.endswith(".spec.tsx"):
            obs["has_tests"] = True
            obs["concepts"].add("testing")
        parts = [p for p in rel.split("/") if p]
        if len(parts) > 1:
            top = parts[0].lower()
            obs["top_dirs"][top] += 1
            obs["entities"].add(top)
            if top == "src-tauri":
                obs["concepts"].add("tauri")

        if len(obs["sample_files"]) < 8:
            obs["sample_files"].append("/".join(parts[:3]) if parts else full_path.name)

        norm = f"{obs['root_original']} {rel}".lower().replace("\\", "/")
        if "sublimeomnidoc" in norm:
            obs["concepts"].update({"sublimeomnidoc", "documenti", "reader"})
            obs["entities"].add("sublimeomnidoc")
        if "antihaker" in norm:
            obs["concepts"].update({"antihaker", "security"})
            obs["entities"].add("antihaker")
        if "/shannon/" in norm or norm.endswith("/shannon"):
            obs["concepts"].update({"shannon", "security"})
            obs["entities"].add("shannon")
        if "omni-recon" in norm:
            obs["concepts"].update({"recon", "security"})
        if "onlyoffice" in norm:
            obs["concepts"].add("office")
        if "monaco" in norm:
            obs["concepts"].add("editor")

    def _publish_scan_fragments(self, root_observations: Dict[str, Dict[str, Any]], request_id: str, summary: Dict[str, Any]) -> None:
        if not root_observations:
            return
        published = 0
        for root_key, obs in root_observations.items():
            if int(obs.get("files", 0) or 0) <= 0:
                continue
            fragment = self._build_local_scan_fragment(obs=obs, request_id=request_id)
            if not fragment:
                continue
            if self._publish_event_sync(
                EventType.KNOWLEDGE_FRAGMENT_CREATED,
                {"fragment": fragment},
                source_module="FileSystemScanner",
                priority=3,
            ):
                published += 1

        if published:
            self._publish_event_sync(
                EventType.SOURCE_CRAWL_COMPLETED,
                {
                    "request_id": request_id,
                    "roots": summary.get("roots", []),
                    "files_scanned": summary.get("files_scanned", 0),
                    "local_scan_fragments_published": published,
                    "timestamp": summary.get("timestamp"),
                },
                source_module="FileSystemScanner",
                priority=4,
            )

    def _build_local_scan_fragment(self, obs: Dict[str, Any], request_id: str) -> Optional[Dict[str, Any]]:
        root_original = str(obs.get("root_original") or "")
        if not root_original:
            return None

        concepts = set(c.lower() for c in (obs.get("concepts") or set()) if c)
        entities = set(str(e) for e in (obs.get("entities") or set()) if e)

        root_name = Path(root_original.rstrip("\\/")).name or root_original
        entities.add(root_name)
        concepts.update(self._tokenize_to_concepts(root_name))
        concepts.update(self._tokenize_to_concepts(root_original))

        # Domain-specific aliases for high-value local assets (improves project recall in KG queries)
        low_root = root_original.lower()
        if "sublimeomnidoc" in low_root:
            concepts.update({"sublimeomnidoc", "documenti", "reader"})
        if "lettore" in low_root and "document" in low_root:
            concepts.update({"documenti", "reader"})
        if "antihaker" in low_root:
            concepts.update({"antihaker", "security"})
        if "sicurezza" in low_root:
            concepts.add("security")

        # Add top-level directories as entities and concepts for discoverability.
        for name, _count in (obs.get("top_dirs") or {}).most_common(8):
            entities.add(name)
            concepts.update(self._tokenize_to_concepts(name))
            if name == "shannon":
                concepts.update({"shannon", "security"})

        # Keep concepts meaningful and stable.
        concepts = {c for c in concepts if len(c) >= 2 and c not in {"src", "app", "cmd", "log"}}
        entities = {e for e in entities if len(e) >= 2}

        ext_counts: Counter = obs.get("extensions") or Counter()
        top_exts = [f"{ext}:{count}" for ext, count in ext_counts.most_common(8)]
        markers = sorted(obs.get("markers") or set())
        top_dirs = [f"{name}:{count}" for name, count in (obs.get("top_dirs") or Counter()).most_common(8)]
        sample_files = list(obs.get("sample_files") or [])

        content = (
            f"Local project scan summary for {root_original}. "
            f"Files={obs.get('files', 0)}. "
            f"Markers={', '.join(markers) or 'none'}. "
            f"Flags="
            f"ci:{bool(obs.get('has_ci'))},tests:{bool(obs.get('has_tests'))},lock:{bool(obs.get('has_lock'))},"
            f"readme:{bool(obs.get('has_readme'))},license:{bool(obs.get('has_license'))},launcher:{bool(obs.get('has_launcher'))}. "
            f"TopDirs={', '.join(top_dirs) or 'none'}. "
            f"TopExts={', '.join(top_exts) or 'none'}. "
            f"SampleFiles={', '.join(sample_files) or 'none'}."
        )
        fragment_hash = hashlib.md5(f"{request_id}|{root_original}".encode("utf-8", errors="ignore")).hexdigest()[:12]
        return {
            "fragment_id": f"local_scan_{fragment_hash}",
            "title": f"Local Scan: {root_name}",
            "content": content,
            "source_type": "internal",
            "source_url": f"local://filesystem_scan/{request_id}",
            "reliability_score": "high",
            "entities": sorted(entities)[:24],
            "concepts": sorted(concepts)[:32],
            "metadata": {
                "kind": "local_filesystem_scan",
                "request_id": request_id,
                "root_original": root_original,
                "root_mapped": obs.get("root_mapped"),
                "files": obs.get("files", 0),
                "markers": markers,
                "scan_flags": {
                    "has_ci": bool(obs.get("has_ci")),
                    "has_tests": bool(obs.get("has_tests")),
                    "has_lock": bool(obs.get("has_lock")),
                    "has_readme": bool(obs.get("has_readme")),
                    "has_license": bool(obs.get("has_license")),
                    "has_launcher": bool(obs.get("has_launcher")),
                    "has_docker": bool(obs.get("has_docker")),
                },
                "top_extensions": dict(ext_counts.most_common(12)),
                "top_dirs": dict((obs.get("top_dirs") or Counter()).most_common(12)),
            },
            "created_at": datetime.now().isoformat(),
            "processed_at": None,
        }

    def _tokenize_to_concepts(self, text: str) -> set[str]:
        pieces = re.split(r"[^a-zA-Z0-9]+", (text or "").lower())
        out = set()
        for p in pieces:
            if not p:
                continue
            # preserve informative tokens; drop noisy generic segments
            if p in {"users", "pc", "desktop", "drive", "core", "rth"}:
                continue
            out.add(p)
        return out

    def _publish_event_sync(self, event_type: EventType, data: Dict[str, Any], source_module: str, priority: int = 5) -> bool:
        try:
            asyncio.run(
                get_event_bus().publish(
                    event_type=event_type,
                    data=data,
                    source_module=source_module,
                    priority=priority,
                )
            )
            return True
        except RuntimeError:
            # If a loop is already running in this thread, skip rather than blocking incorrectly.
            logger.debug(f"Skipped sync publish for {event_type.value}: event loop already running")
            return False
        except Exception as e:
            logger.warning(f"Event publish failed ({event_type.value}): {e}")
            return False

    def _normalize_path(self, path_str: str) -> str:
        return path_str.replace("\\", "/")

    def _is_excluded(self, path_str: str, patterns: Optional[List[str]]) -> bool:
        norm = self._normalize_path(path_str)
        patterns = patterns or list(DEFAULT_EXCLUDES)
        for pattern in patterns:
            pat = pattern.replace("\\", "/")
            if fnmatch.fnmatch(norm, pat):
                return True
        return False

    def _matches_any(self, path_str: str, patterns: Optional[List[str]]) -> bool:
        if not patterns:
            return False
        norm = self._normalize_path(path_str)
        for pattern in patterns:
            pat = pattern.replace("\\", "/")
            if fnmatch.fnmatch(norm, pat):
                return True
        return False

    def _hash_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _read_snippet(self, path: Path, limit: int) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(limit)
        except Exception:
            return ""

    def _read_full(self, path: Path, ext: str) -> Tuple[str, Optional[str]]:
        if ext in TEXT_EXTENSIONS:
            return self._read_text(path), None
        if ext == ".docx":
            return self._read_docx(path)
        if ext == ".pdf":
            return self._read_pdf(path)
        return "", "unsupported_extension"

    def _read_text(self, path: Path) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return ""

    def _read_docx(self, path: Path) -> Tuple[str, Optional[str]]:
        try:
            with zipfile.ZipFile(path, "r") as zf:
                if "word/document.xml" not in zf.namelist():
                    return "", "docx_missing_document"
                xml_data = zf.read("word/document.xml")
            root = ET.fromstring(xml_data)
            texts = [node.text for node in root.iter() if node.text]
            return " ".join(texts), None
        except Exception:
            return "", "docx_extract_failed"

    def _read_pdf(self, path: Path) -> Tuple[str, Optional[str]]:
        reader = None
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(path)
        except Exception:
            try:
                from pypdf import PdfReader  # type: ignore
                reader = PdfReader(path)
            except Exception:
                return "", "pdf_extract_unavailable"

        try:
            texts = []
            for page in reader.pages:
                try:
                    text = page.extract_text() or ""
                    texts.append(text)
                except Exception:
                    continue
            return "\n".join(texts), None
        except Exception:
            return "", "pdf_extract_failed"

fs_scanner = FileSystemScanner()
