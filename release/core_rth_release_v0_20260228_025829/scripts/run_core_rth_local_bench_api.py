import os
import sys
from pathlib import Path

# Force local benchmark mode before app imports .env/config.
os.environ["RTH_PATH_MAP_JSON"] = ""
os.environ.setdefault("PYTHONUNBUFFERED", "1")
os.environ["RTH_DISKLESS"] = os.environ.get("RTH_BENCH_DISKLESS", os.environ.get("RTH_DISKLESS", "false"))
bench_memory_base = os.environ.get("RTH_BENCH_MEMORY_BASE", "").strip()
if bench_memory_base:
    os.environ["RTH_MEMORY_BASE"] = bench_memory_base

import uvicorn


if __name__ == "__main__":
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    port = int(os.environ.get("RTH_BENCH_PORT", "18012"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="info")
