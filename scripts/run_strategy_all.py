"""
Run full strategic execution:
1) compute top 50
2) launch phase1 (top 3)
3) approve all pending governance
4) launch phase2 (next 7)
5) approve all pending governance again
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
    approved_phase1 = jarvis_core.governance_approve_all(
        decided_by="owner",
        note="approved batch phase1",
    )
    phase2 = jarvis_core.strategy_launch_phase2()
    approved_phase2 = jarvis_core.governance_approve_all(
        decided_by="owner",
        note="approved batch phase2",
    )

    out = {
        "top_count": top.get("count", 0),
        "top_10": top.get("assets", [])[:10],
        "phase1": {
            "status": phase1.get("status"),
            "targets": phase1.get("targets", []),
        },
        "approved_phase1": approved_phase1.get("approved_count", 0),
        "phase2": {
            "status": phase2.get("status"),
            "targets": phase2.get("targets", []),
        },
        "approved_phase2": approved_phase2.get("approved_count", 0),
        "governance_final": jarvis_core.governance_list().get("summary", {}),
        "plugins_top": jarvis_core.plugins(min_score=8.0).get("plugins", [])[:15],
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
