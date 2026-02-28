#!/usr/bin/env python3
"""
llama.cpp server helper for Core Rth (llama-cpp-python server backend).

Usage examples:
  python scripts/run_llama_cpp_server.py status
  python scripts/run_llama_cpp_server.py check
  python scripts/run_llama_cpp_server.py start --model "D:\\models\\my.gguf" --daemon
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


def _load_quick_env() -> Dict[str, str]:
    out: Dict[str, str] = {}
    p = Path(".env.rth.quickstart.local")
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _base_url(args) -> str:
    env = _load_quick_env()
    return (args.base_url or env.get("LLAMA_CPP_BASE_URL") or "http://127.0.0.1:8080/v1").strip()


def _state_dir() -> Path:
    for p in [Path("storage_runtime") / "llama_cpp_server", Path("storage") / "llama_cpp_server", Path(tempfile.gettempdir()) / "rth_core" / "llama_cpp_server"]:
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            continue
    return Path(tempfile.gettempdir())


def _http_get_json(url: str, timeout: float = 5.0) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "RTH-Core/0.1 (+llama_cpp_helper)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        body = json.loads(raw) if raw.strip() else {}
        return {"ok": True, "url": url, "status_code": int(getattr(resp, "status", 200)), "body": body, "raw_preview": raw[:500]}


def cmd_status(args) -> int:
    base = _base_url(args).rstrip("/")
    urls = [f"{base}/models", f"{base.rsplit('/v1', 1)[0]}/models"] if base.endswith("/v1") else [f"{base}/models", f"{base}/v1/models"]
    attempts: List[Dict[str, Any]] = []
    for url in urls:
        try:
            res = _http_get_json(url, timeout=args.timeout_sec)
            models = []
            body = res.get("body")
            if isinstance(body, dict):
                for row in body.get("data", []) or []:
                    if isinstance(row, dict) and row.get("id"):
                        models.append(str(row["id"]))
            res["models"] = models[:20]
            print(json.dumps({"status": "ok", "base_url": base, "attempt": res}, ensure_ascii=True, indent=2))
            return 0
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = ""
            attempts.append({"url": url, "ok": False, "status_code": getattr(e, "code", None), "error": str(e), "detail": detail})
        except Exception as e:
            attempts.append({"url": url, "ok": False, "error": str(e)})
    print(json.dumps({"status": "error", "base_url": base, "attempts": attempts}, ensure_ascii=True, indent=2))
    return 1


def cmd_check(args) -> int:
    probes = []
    for cmd in [
        [sys.executable, "-m", "llama_cpp.server", "--help"],
        [sys.executable, "-c", "import llama_cpp; print(getattr(llama_cpp, '__version__', 'unknown'))"],
    ]:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=max(2.0, float(args.timeout_sec)), shell=False)
            probes.append({
                "cmd": cmd,
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout_preview": (proc.stdout or "")[:500],
                "stderr_preview": (proc.stderr or "")[:500],
            })
        except Exception as e:
            probes.append({"cmd": cmd, "ok": False, "error": str(e)})
    print(json.dumps({"status": "ok" if any(p.get("ok") for p in probes) else "error", "probes": probes}, ensure_ascii=True, indent=2))
    return 0 if any(p.get("ok") for p in probes) else 1


def _model_path(args) -> str:
    env = _load_quick_env()
    return (args.model or env.get("RTH_LLAMA_CPP_MODEL_PATH") or "").strip()


def cmd_start(args) -> int:
    model_path = _model_path(args)
    if not model_path:
        print(json.dumps({"status": "missing_model_path", "hint": "Set RTH_LLAMA_CPP_MODEL_PATH in .env.rth.quickstart.local or pass --model"}, ensure_ascii=True, indent=2))
        return 2
    p = Path(model_path)
    if not p.exists():
        print(json.dumps({"status": "model_not_found", "model_path": model_path}, ensure_ascii=True, indent=2))
        return 2
    host = args.host
    port = int(args.port)
    cmd = [
        sys.executable, "-m", "llama_cpp.server",
        "--model", str(p),
        "--host", host,
        "--port", str(port),
    ]
    if args.n_ctx:
        cmd += ["--n_ctx", str(int(args.n_ctx))]
    if args.n_gpu_layers is not None:
        cmd += ["--n_gpu_layers", str(int(args.n_gpu_layers))]
    if args.chat_format:
        cmd += ["--chat_format", str(args.chat_format)]

    if not args.daemon:
        print(json.dumps({"status": "starting_foreground", "cmd": cmd}, ensure_ascii=True, indent=2))
        return subprocess.call(cmd)

    sd = _state_dir()
    log_path = sd / "llama_cpp_server.log"
    pid_path = sd / "llama_cpp_server.pid"
    with open(log_path, "a", encoding="utf-8", errors="replace") as logf:
        proc = subprocess.Popen(cmd, stdout=logf, stderr=logf, shell=False)
    pid_path.write_text(str(proc.pid), encoding="utf-8")
    print(json.dumps({"status": "started", "pid": proc.pid, "cmd": cmd, "log_path": str(log_path), "pid_path": str(pid_path)}, ensure_ascii=True, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status")
    p_status.add_argument("--base-url", default="")
    p_status.add_argument("--timeout-sec", type=float, default=5.0)
    p_status.set_defaults(func=cmd_status)

    p_check = sub.add_parser("check")
    p_check.add_argument("--timeout-sec", type=float, default=8.0)
    p_check.set_defaults(func=cmd_check)

    p_start = sub.add_parser("start")
    p_start.add_argument("--model", default="")
    p_start.add_argument("--host", default="127.0.0.1")
    p_start.add_argument("--port", type=int, default=8080)
    p_start.add_argument("--n-ctx", type=int, default=0)
    p_start.add_argument("--n-gpu-layers", type=int)
    p_start.add_argument("--chat-format", default="")
    p_start.add_argument("--daemon", action="store_true")
    p_start.set_defaults(func=cmd_start)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

