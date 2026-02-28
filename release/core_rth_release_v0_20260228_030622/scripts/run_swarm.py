"""
Run swarm analysis with auto-approval (read-only).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.swarm import swarm_orchestrator
from app.core.permissions import permission_gate, Decision

def main():
    proposal = swarm_orchestrator.propose("User-triggered swarm analysis")
    print(json.dumps({
        "event": "proposal",
        "timestamp": datetime.now().isoformat(),
        "proposal": proposal.to_dict()
    }, indent=2))

    if proposal.status == "denied":
        print(json.dumps({"event": "denied", "request_id": proposal.request_id}, indent=2))
        return

    decision = permission_gate.approve(proposal.request_id, decided_by="owner")
    if decision.decision != Decision.APPROVED:
        print(json.dumps({
            "event": "not_approved",
            "request_id": proposal.request_id,
            "decision": decision.to_dict()
        }, indent=2))
        return

    report = swarm_orchestrator.run(decision.request_id, roots=None, max_projects=200)
    summary = {
        "status": report.get("status"),
        "request_id": report.get("request_id"),
        "timestamp": report.get("timestamp"),
        "core_files": report.get("core_map", {}).get("count", 0),
        "projects_found": report.get("evolution", {}).get("projects_found", 0),
        "high_ranked": len(report.get("high_ranked", [])),
        "sublimation_plan_items": len(report.get("sublimation_plan", [])),
        "governance_summary": report.get("governance", {}).get("summary", {}),
        "plugin_sync": report.get("plugin_hub", {}).get("sync", {}),
        "kg_nodes": report.get("knowledge_graph_ingest", {}).get("kg_status", {}).get("metrics", {}).get("total_nodes", 0),
    }
    print(json.dumps({
        "event": "completed",
        "timestamp": datetime.now().isoformat(),
        "summary": summary
    }, indent=2))

if __name__ == "__main__":
    main()
