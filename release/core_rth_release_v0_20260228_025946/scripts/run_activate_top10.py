"""
Seed strategy phases and activate top 10 plugin candidates.
Also returns workspace discovery for Aletheion/Code/Cowork.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.jarvis import jarvis_core


def main():
    jarvis_core.strategy_top(limit=50)
    jarvis_core.strategy_launch_phase1()
    jarvis_core.strategy_launch_phase2()
    jarvis_core.governance_approve_all(decided_by="owner", note="approve pending strategic proposals")

    activation = jarvis_core.plugin_activate_top(limit=10, min_score=0.0, decided_by="owner")
    workspaces = jarvis_core.discover_workspaces()

    result = {
        "activation": {
            "requested": activation.get("requested", 0),
            "activated": activation.get("activated", 0),
            "failed": activation.get("failed", []),
            "items": activation.get("items", []),
        },
        "workspaces": workspaces.get("workspaces", {}),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
