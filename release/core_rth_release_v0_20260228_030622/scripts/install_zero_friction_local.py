#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], timeout: float = 600.0) -> dict:
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
        return {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "cmd": cmd,
            "stdout": (p.stdout or "")[:12000],
            "stderr": (p.stderr or "")[:8000],
        }
    except Exception as e:
        return {"ok": False, "cmd": cmd, "error": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Core Rth zero-friction local install/bootstrap")
    ap.add_argument("--skip-pip", action="store_true")
    ap.add_argument("--start-api", action="store_true", default=True)
    ap.add_argument("--start-llama", action="store_true")
    ap.add_argument("--api-port", type=int, default=18030)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    report = {"module": "install_zero_friction_local", "timestamp": datetime.now().isoformat(timespec="seconds"), "steps": []}

    report["steps"].append({"id": "python_version", "result": _run([sys.executable, "--version"], timeout=15)})
    if not args.skip_pip:
        report["steps"].append({"id": "pip_install_requirements", "result": _run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], timeout=1800)})

    onboard_cmd = [sys.executable, "scripts/onboard_zero_friction.py", "--api-base", f"http://127.0.0.1:{args.api_port}"]
    if args.start_api:
        onboard_cmd.append("--start-api-if-needed")
    if args.start_llama:
        onboard_cmd.append("--start-llama-if-needed")
    report["steps"].append({"id": "onboarding", "result": _run(onboard_cmd, timeout=300)})
    report["steps"].append({"id": "release_gate_rc1", "result": _run([sys.executable, "scripts/release_gate_rc1.py", "--api-base", f"http://127.0.0.1:{args.api_port}"], timeout=900)})

    failures = [s["id"] for s in report["steps"] if not s["result"].get("ok")]
    report["summary"] = {"overall": "pass" if not failures else "fail", "failed_steps": failures}

    out_path = Path(args.out) if args.out else (Path(tempfile.gettempdir()) / "rth_core" / "reports" / f"install_zero_friction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["summary"]["overall"], "summary": report["summary"], "report": str(out_path)}, ensure_ascii=False))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())

