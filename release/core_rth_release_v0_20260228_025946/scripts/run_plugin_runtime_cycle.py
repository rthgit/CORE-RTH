"""
Run a read-only plugin runtime cycle:
1) propose (PLUGIN_RUNTIME)
2) approve
3) run cycle (manifest -> KG ingest -> governance plan)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.jarvis import jarvis_core
from app.core.permissions import permission_gate, Decision


def main():
    proposal = jarvis_core.plugin_runtime_propose(reason="Manual plugin runtime cycle")
    print(json.dumps({"event": "proposal", "timestamp": datetime.now().isoformat(), "proposal": proposal}, indent=2))

    request_id = proposal.get("request_id")
    if not request_id:
        print(json.dumps({"event": "error", "detail": "missing request_id"}, indent=2))
        return

    decision = permission_gate.approve(request_id, decided_by="owner")
    if decision.decision != Decision.APPROVED:
        print(json.dumps({"event": "denied", "decision": decision.to_dict()}, indent=2))
        return

    report = jarvis_core.plugin_runtime_run(request_id=request_id, min_score=0.0)
    print(json.dumps({"event": "completed", "timestamp": datetime.now().isoformat(), "summary": report.get("summary")}, indent=2))


if __name__ == "__main__":
    main()

