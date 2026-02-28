"""
Activate plugin candidates from top100 ranking for a rank interval.
Default interval: 11..50.
"""
import argparse
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List

import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.plugin_hub import plugin_hub
from app.core.permissions import permission_gate


LOG_DIR_CANDIDATES = [
    Path("logs"),
    Path("storage_runtime") / "logs",
    Path(tempfile.gettempdir()) / "rth_core" / "logs",
]


def _find_top100_path() -> Path:
    matches: List[Path] = []
    for base in LOG_DIR_CANDIDATES:
        p = base / "top100_evolutions.json"
        if p.exists():
            matches.append(p)
    if not matches:
        raise FileNotFoundError("top100_evolutions.json not found")
    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def _plugin_id(root: str) -> str:
    import hashlib
    return f"plg_{hashlib.md5(root.lower().encode()).hexdigest()[:10]}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=11)
    parser.add_argument("--end", type=int, default=50)
    parser.add_argument("--decided-by", type=str, default="owner")
    args = parser.parse_args()

    top100_path = _find_top100_path()
    payload = json.loads(top100_path.read_text(encoding="utf-8"))
    items = payload.get("items", [])
    if not items:
        raise RuntimeError("No items found in top100_evolutions.json")

    sync = plugin_hub.sync_from_high_ranked(items)

    selected = [x for x in items if args.start <= int(x.get("rank", 0)) <= args.end]
    activations: List[Dict[str, Any]] = []
    for entry in selected:
        root = str(entry.get("root", ""))
        pid = _plugin_id(root)
        try:
            proposal = plugin_hub.propose_activation(
                plugin_id=pid,
                reason=f"Activate rank {entry.get('rank')} from top100: {root}",
            )
            request_id = proposal.get("request_id")
            decision = permission_gate.approve(request_id=request_id, decided_by=args.decided_by)
            result = plugin_hub.activate(request_id=request_id)
            activations.append({
                "rank": entry.get("rank"),
                "root": root,
                "plugin_id": pid,
                "request_id": request_id,
                "decision": decision.decision.value,
                "status": result.get("status"),
            })
        except Exception as e:
            activations.append({
                "rank": entry.get("rank"),
                "root": root,
                "plugin_id": pid,
                "status": "error",
                "error": str(e),
            })

    activated_count = sum(1 for a in activations if a.get("status") == "active")
    failed = [a for a in activations if a.get("status") != "active"]

    out = {
        "top100_path": str(top100_path),
        "sync": sync,
        "range": {"start": args.start, "end": args.end},
        "requested": len(selected),
        "activated_count": activated_count,
        "failed_count": len(failed),
        "failed": failed,
        "activations": activations,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
