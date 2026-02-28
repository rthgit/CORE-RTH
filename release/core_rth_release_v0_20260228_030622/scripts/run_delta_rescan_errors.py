"""
Delta rescan focused on error-prone paths:
1) quick probe scan on C:\\ and D:\\ with shallow depth
2) derive roots from error samples
3) run targeted rescan only on those roots
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.fs_scanner import ScanScope, fs_scanner, DEFAULT_EXCLUDES
from app.core.permissions import permission_gate, Decision


def _propose_and_run(scope: ScanScope, reason: str) -> Dict[str, Any]:
    proposal = fs_scanner.propose(scope, reason=reason)
    if proposal.status == "denied":
        return {"status": "denied", "proposal": proposal.to_dict()}
    decision = permission_gate.approve(proposal.request_id, decided_by="owner")
    if decision.decision != Decision.APPROVED:
        return {
            "status": "not_approved",
            "proposal": proposal.to_dict(),
            "decision": decision.to_dict(),
        }
    result = fs_scanner.execute(scope, proposal.request_id)
    return {
        "status": "completed",
        "proposal": proposal.to_dict(),
        "result": result,
    }


def _derive_error_roots(error_samples: List[Dict[str, str]], limit: int = 120) -> List[str]:
    roots: List[str] = []
    seen = set()
    for sample in error_samples:
        p = Path(sample.get("path", ""))
        if not p:
            continue
        candidate = p if p.is_dir() else p.parent
        if not candidate:
            continue
        try:
            candidate = candidate.resolve()
        except Exception:
            pass
        text = str(candidate)
        if not text:
            continue
        # Keep only windows drive paths and skip obvious excluded system roots.
        norm = text.replace("\\", "/").lower()
        if not (norm.startswith("c:/") or norm.startswith("d:/")):
            continue
        if any(skip in norm for skip in [
            "/windows/",
            "/program files/",
            "/program files (x86)/",
            "/programdata/",
            "/$recycle.bin/",
            "/system volume information/",
        ]):
            continue
        if text in seen:
            continue
        seen.add(text)
        roots.append(text)
        if len(roots) >= limit:
            break
    return roots


def main():
    print(json.dumps({
        "event": "delta_rescan_started",
        "timestamp": datetime.now().isoformat()
    }, indent=2))

    probe_scope = ScanScope(
        roots=[r"C:\\", r"D:\\"],
        exclude_globs=list(DEFAULT_EXCLUDES),
        include_globs=None,
        max_depth=2,
        max_file_size_mb=10,
        hash_files=False,
        content_snippets=False,
        content_full=False,
        snippet_bytes=256,
        max_files=250000,
    )
    probe = _propose_and_run(probe_scope, reason="Delta probe for error roots")
    print(json.dumps({
        "event": "probe_completed",
        "timestamp": datetime.now().isoformat(),
        "probe_status": probe.get("status"),
        "probe_summary": (probe.get("result") or {})
    }, indent=2))

    probe_result = probe.get("result", {})
    error_samples = probe_result.get("error_samples", []) if isinstance(probe_result, dict) else []
    target_roots = _derive_error_roots(error_samples, limit=120)

    if not target_roots:
        print(json.dumps({
            "event": "delta_rescan_skipped",
            "timestamp": datetime.now().isoformat(),
            "reason": "no_error_targets_found"
        }, indent=2))
        return

    delta_scope = ScanScope(
        roots=target_roots,
        exclude_globs=list(DEFAULT_EXCLUDES),
        include_globs=None,
        max_depth=4,
        max_file_size_mb=25,
        hash_files=True,
        content_snippets=False,
        content_full=False,
        snippet_bytes=256,
        max_files=300000,
    )
    delta = _propose_and_run(delta_scope, reason="Delta rescan on previous error roots")
    print(json.dumps({
        "event": "delta_rescan_completed",
        "timestamp": datetime.now().isoformat(),
        "targets_count": len(target_roots),
        "targets_sample": target_roots[:25],
        "delta_status": delta.get("status"),
        "delta_summary": (delta.get("result") or {})
    }, indent=2))


if __name__ == "__main__":
    main()
