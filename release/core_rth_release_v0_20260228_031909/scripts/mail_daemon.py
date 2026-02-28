"""
Simple mailbox polling daemon for RTH mail bridge.

Examples:
- python scripts/mail_daemon.py --once
- python scripts/mail_daemon.py --interval 30
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.jarvis import jarvis_core


def run_once(limit: int) -> int:
    out = jarvis_core.mail_poll_once(limit=limit)
    print(json.dumps({"timestamp": datetime.now().isoformat(), "result": out}, indent=2, default=str))
    return 0


def run_loop(interval: int, limit: int) -> int:
    print(json.dumps({"event": "mail_daemon_started", "interval_seconds": interval, "limit": limit}))
    while True:
        out = jarvis_core.mail_poll_once(limit=limit)
        print(json.dumps({"timestamp": datetime.now().isoformat(), "result": out}, default=str))
        time.sleep(max(5, interval))


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="poll only once and exit")
    ap.add_argument("--interval", type=int, default=30, help="poll interval in seconds")
    ap.add_argument("--limit", type=int, default=20, help="max unseen messages per poll")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    if args.once:
        return run_once(limit=args.limit)
    return run_loop(interval=args.interval, limit=args.limit)


if __name__ == "__main__":
    raise SystemExit(main())

