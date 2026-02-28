"""
Run strategic extraction and launch phase1 proposals (top 3 assets).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.jarvis import jarvis_core


def main():
    top = jarvis_core.strategy_top(limit=50)
    phase1 = jarvis_core.strategy_launch_phase1()

    summary = {
        "top_count": top.get("count", 0),
        "top_10": top.get("assets", [])[:10],
        "phase1_status": phase1.get("status"),
        "phase1_targets": phase1.get("targets", []),
        "governance_summary": phase1.get("governance_summary", {}),
        "plugin_sync": phase1.get("plugin_sync", {}),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
