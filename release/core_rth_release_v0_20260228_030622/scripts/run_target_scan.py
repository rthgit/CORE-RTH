"""
Run a targeted scan for specific roots with full content extraction.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.fs_scanner import ScanScope, fs_scanner, DEFAULT_EXCLUDES
from app.core.permissions import permission_gate, Decision

ROOTS = [
    r"C:\Users\PC\Desktop\Biome",
    r"D:\CODEX",
    r"D:\SIMULATORE_RCQ",
]

def main():
    scope = ScanScope(
        roots=ROOTS,
        exclude_globs=list(DEFAULT_EXCLUDES),
        include_globs=None,
        max_depth=None,
        max_file_size_mb=None,
        hash_files=True,
        content_snippets=False,
        content_full=True,
        snippet_bytes=256,
        max_files=None
    )

    proposal = fs_scanner.propose(scope, reason="Targeted scan for ranking")
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

    result = fs_scanner.execute(scope, proposal.request_id)
    print(json.dumps({
        "event": "completed",
        "timestamp": datetime.now().isoformat(),
        "result": result
    }, indent=2))

if __name__ == "__main__":
    main()
