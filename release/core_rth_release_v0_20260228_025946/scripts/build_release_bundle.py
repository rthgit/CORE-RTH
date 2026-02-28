#!/usr/bin/env python3
"""
Build a curated Core Rth release folder (code + configs + benchmark harness + evidence).

This creates a self-contained release subtree inside ./release/ so we can ship only that.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
RELEASES_DIR = ROOT / "release"

IGNORE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
IGNORE_SUFFIXES = {".pyc", ".pyo"}


ROOT_FILES = [
    "requirements.txt",
    "Dockerfile",
    "docker-compose.core-shadow.yml",
    ".env.example",
    ".dockerignore",
    "LICENSE",
    "SAFETY_WARNING.md",
]

FULL_DIRS = [
    "app",
    "docs",
    "scripts",
]

BENCH_FILES = [
    "bench/README.md",
    "bench/runner.py",
    "bench/score.py",
    "bench/OPENCLAW_COMPETITIVE_PLAN_20260225.md",
    "bench/tasks/core_rth_vs_openclaw_suite.json",
    "bench/adapters/core_rth_http_adapter.py",
    "bench/adapters/openclaw_repo_adapter.py",
    "bench/adapters/openclaw_runtime_adapter.py",
]

BENCH_EVIDENCE_FILES = [
    "bench/results/20260224_220842_core_rth_core9_full12_guardsemantic/summary.json",
    "bench/results/20260224_220842_core_rth_core9_full12_guardsemantic/scoreboard.csv",
    "bench/results/20260224_220842_core_rth_core9_full12_guardsemantic/tasks/guardian_permission_enforcement/guardian_permission_probe.json",
    "bench/results/20260225_000700_openclaw_runtime_cli_live/summary.json",
    "bench/results/20260225_000700_openclaw_runtime_cli_live/scoreboard.csv",
    "bench/results/20260225_000700_openclaw_runtime_cli_live/tasks/guardian_permission_enforcement/openclaw_runtime_probe.json",
    "bench/results/compare_20260224_220842_core_rth_core9_full12_guardsemantic__vs__20260225_000700_openclaw_runtime_cli_live.json",
    "bench/results/compare_20260225_000700_openclaw_runtime_cli_live__vs__20260224_230614_openclaw_static_repo_baseline.json",
]


def _ignore_name(path: Path) -> bool:
    return path.name in IGNORE_DIRS or path.suffix.lower() in IGNORE_SUFFIXES


def _copy_tree(src: Path, dst: Path) -> Dict[str, int]:
    counts = {"files": 0, "dirs": 0}
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        if any(part in IGNORE_DIRS for part in rel.parts):
            continue
        if item.is_file():
            if _ignore_name(item):
                continue
            out = dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, out)
            counts["files"] += 1
        elif item.is_dir():
            (dst / rel).mkdir(parents=True, exist_ok=True)
            counts["dirs"] += 1
    return counts


def _copy_file(rel_path: str, target_root: Path, copied: List[str], missing: List[str]) -> None:
    src = ROOT / rel_path
    if not src.exists():
        missing.append(rel_path)
        return
    dst = target_root / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    copied.append(rel_path)


def _next_release_dir(base_dir: Path | None = None) -> Path:
    base = f"core_rth_release_v0_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    candidates = []
    env_base = os.getenv("RTH_RELEASE_BUNDLE_BASE", "").strip()
    if base_dir:
        candidates.append(Path(base_dir))
    elif env_base:
        candidates.append(Path(os.path.expandvars(os.path.expanduser(env_base))))
    candidates.append(RELEASES_DIR)
    candidates.append(Path(tempfile.gettempdir()) / "rth_core" / "release")
    last_err = None
    for root in candidates:
        try:
            root.mkdir(parents=True, exist_ok=True)
            out = root / base
            out.mkdir(parents=True, exist_ok=False)
            return out
        except Exception as e:
            last_err = e
            continue
    raise last_err if last_err else RuntimeError("Unable to create release bundle directory")


def _write_release_docs(release_dir: Path, manifest: Dict[str, object]) -> None:
    readme = """# Core Rth Release Bundle (Curated)

This folder is a curated release subset of the workspace:

- runtime code (`app/`)
- operational scripts (`scripts/`)
- benchmark harness + selected evidence (`bench/`)
- deployment files (`Dockerfile`, `docker-compose.core-shadow.yml`, `.env.example`)

## Quick Start

1. Install Python deps:

```powershell
pip install -r requirements.txt
```

2. Start API (local):

```powershell
python scripts/run_core_rth_local_bench_api.py
```

3. Use CLI spine:

```powershell
python scripts/rth.py --help
python scripts/rth.py api start --port 18030
python scripts/rth.py api status
python scripts/rth.py guardian policy
python scripts/rth.py guardian policy get
python scripts/rth.py guardian audit
python scripts/rth.py cortex status
```

4. Open the local UI (Operator Chat + Multi-LLM Control Plane v0):

```text
http://127.0.0.1:18030/ui/
```

5. One-click RC1 gate + onboarding:

```powershell
python scripts/install_zero_friction_local.py --start-api --start-llama
python scripts/release_gate_rc1.py --start-api-if-needed
python scripts/onboard_zero_friction.py --start-api-if-needed
python scripts/channels_live_final_check.py
```

## Notes

- This bundle excludes secrets (`.env`) and large optional model artifacts.
- External project roots (`SublimeOmniDoc`, `ANTIHAKER`) are not copied here.
- See `RELEASE_MANIFEST.json` for included/excluded items.
"""
    (release_dir / "README_RELEASE.md").write_text(readme, encoding="utf-8")

    launch_cli = "@echo off\r\ncd /d %~dp0\r\npython scripts\\rth.py %*\r\n"
    (release_dir / "RTH_CLI.cmd").write_text(launch_cli, encoding="utf-8")

    launch_api = (
        "@echo off\r\n"
        "cd /d %~dp0\r\n"
        "python scripts\\run_core_rth_local_bench_api.py\r\n"
    )
    (release_dir / "START_CORE_RTH_API.cmd").write_text(launch_api, encoding="utf-8")

    gate_cmd = (
        "@echo off\r\n"
        "cd /d %~dp0\r\n"
        "python scripts\\release_gate_rc1.py --start-api-if-needed %*\r\n"
    )
    (release_dir / "RUN_RELEASE_GATE_RC1.cmd").write_text(gate_cmd, encoding="utf-8")

    onboard_cmd = (
        "@echo off\r\n"
        "cd /d %~dp0\r\n"
        "python scripts\\onboard_zero_friction.py --start-api-if-needed --start-llama-if-needed %*\r\n"
    )
    (release_dir / "RTH_ONBOARD_ZERO_FRICTION.cmd").write_text(onboard_cmd, encoding="utf-8")

    channels_cmd = (
        "@echo off\r\n"
        "cd /d %~dp0\r\n"
        "python scripts\\channels_live_final_check.py %*\r\n"
    )
    (release_dir / "RTH_CHANNELS_LIVE_CHECK.cmd").write_text(channels_cmd, encoding="utf-8")

    install_cmd = (
        "@echo off\r\n"
        "cd /d %~dp0\r\n"
        "python scripts\\install_zero_friction_local.py --start-api --start-llama %*\r\n"
    )
    (release_dir / "INSTALL_CORE_RTH_ZERO_FRICTION.cmd").write_text(install_cmd, encoding="utf-8")

    (release_dir / "RELEASE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build curated Core Rth release bundle")
    p.add_argument("--out-base", default="", help="Optional base directory for release bundle output")
    return p


def main() -> int:
    args = build_parser().parse_args()
    release_dir = _next_release_dir(Path(args.out_base) if args.out_base else None)
    copied_files: List[str] = []
    missing_files: List[str] = []
    dir_counts: Dict[str, Dict[str, int]] = {}

    # Core directories.
    for rel_dir in FULL_DIRS:
        src = ROOT / rel_dir
        dst = release_dir / rel_dir
        if not src.exists():
            missing_files.append(rel_dir)
            continue
        dst.mkdir(parents=True, exist_ok=True)
        dir_counts[rel_dir] = _copy_tree(src, dst)

    # Curated files.
    for rel in ROOT_FILES + BENCH_FILES + BENCH_EVIDENCE_FILES:
        _copy_file(rel, release_dir, copied_files, missing_files)

    # Empty runtime folders used by the app.
    for rel in ["logs", "storage_runtime", "storage_runtime/memory", "storage_runtime/logs"]:
        (release_dir / rel).mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "release_dir": str(release_dir),
        "version_tag": "core-rth-release-v0",
        "included": {
            "root_files": ROOT_FILES,
            "full_dirs": FULL_DIRS,
            "bench_files": BENCH_FILES,
            "bench_evidence_files": BENCH_EVIDENCE_FILES,
            "empty_runtime_dirs": ["logs", "storage_runtime", "storage_runtime/memory", "storage_runtime/logs"],
        },
        "copy_stats": {
            "copied_files_explicit": len(copied_files),
            "copied_dirs": dir_counts,
        },
        "missing": missing_files,
        "excluded": {
            "secrets": [".env", "API_RTH_Gateway.env", "KEY_API.env.py"],
            "large_optional_artifacts": [
                "SOUL_FINAL_GOLDEN.pt",
                "shadow_x_models/",
                "bench/baselines/openclaw/",
                "bench/results/* (except selected summaries/probes)",
                "storage/",
                "logs/*",
                "storage_runtime/* (except empty folders)",
            ],
            "external_project_roots_not_copied": [
                "E:\\lettore  documenti\\SublimeOmniDoc",
                "D:\\SICUREZZA ANTIHAKER",
            ],
        },
        "notes": [
            "This is a curated code-and-evidence release bundle for Core Rth v0 product spine work.",
            "Use scripts/build_release_bundle.py to regenerate a fresh release folder after code changes.",
        ],
    }

    _write_release_docs(release_dir, manifest)

    # Generate MANIFEST.sha256
    import hashlib
    manifest_lines = []
    for fp in release_dir.rglob("*"):
        if fp.is_file() and fp.name != "MANIFEST.sha256":
            rel_path = fp.relative_to(release_dir).as_posix()
            file_hash = hashlib.sha256(fp.read_bytes()).hexdigest()
            manifest_lines.append(f"{file_hash} *{rel_path}")
    
    manifest_file = release_dir / "MANIFEST.sha256"
    manifest_file.write_text("\n".join(sorted(manifest_lines)) + "\n", encoding="utf-8")

    print(f"Release bundle created: {release_dir}")
    print(f"MANIFEST.sha256 generated with {len(manifest_lines)} entries.")
    print(f"Copied explicit files: {len(copied_files)}")
    for rel_dir, counts in dir_counts.items():
        print(f"  - {rel_dir}: files={counts['files']} dirs={counts['dirs']}")
    if missing_files:
        print("Missing entries:")
        for m in missing_files:
            print(f"  - {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
