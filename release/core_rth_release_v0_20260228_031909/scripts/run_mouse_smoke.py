"""
Smoke test for consent-gated mouse actions.
Uses "position" action to avoid moving/clicking the cursor.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.jarvis import jarvis_core


def main():
    status = jarvis_core.mouse_status()
    proposal = jarvis_core.propose_mouse_action(
        action="position",
        x=None,
        y=None,
        reason="Mouse smoke test (safe position read)",
    )

    request_id = proposal.get("request_id")
    if not request_id:
        print(json.dumps({"status": "error", "proposal": proposal}, indent=2))
        return

    execution = jarvis_core.approve_and_mouse_action(request_id=request_id, decided_by="owner")
    out = {
        "mouse_status": status,
        "proposal": proposal,
        "execution": execution,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
