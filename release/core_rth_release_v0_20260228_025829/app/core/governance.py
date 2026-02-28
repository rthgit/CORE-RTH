"""
Governance queue for proposed system changes.
All actions remain proposal-first and require explicit approval.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
import hashlib
import json
import tempfile
from pathlib import Path

from .memory_vault import memory_vault


class GovernanceStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


@dataclass
class GovernanceItem:
    proposal_id: str
    title: str
    component: str
    rationale: str
    proposed_changes: List[str]
    source: str = "swarm"
    risk: str = "medium"
    status: GovernanceStatus = GovernanceStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None
    decision_note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "component": self.component,
            "rationale": self.rationale,
            "proposed_changes": self.proposed_changes,
            "source": self.source,
            "risk": self.risk,
            "status": self.status.value,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
            "decision_note": self.decision_note,
        }


class GovernanceQueue:
    def __init__(self):
        self.items: Dict[str, GovernanceItem] = {}
        self._state_path = self._choose_state_path()
        self._load_state()

    def _choose_state_path(self) -> Path:
        candidates = [
            Path("storage") / "governance",
            Path("storage_runtime") / "governance",
            Path(tempfile.gettempdir()) / "rth_core" / "governance",
        ]
        for base in candidates:
            try:
                base.mkdir(parents=True, exist_ok=True)
                probe = base / ".write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return base / "governance_queue.json"
            except Exception:
                continue
        return Path(tempfile.gettempdir()) / "rth_core" / "governance" / "governance_queue.json"

    def _load_state(self) -> None:
        try:
            if not self._state_path.exists():
                return
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            items = raw.get("items", [])
            for d in items:
                try:
                    item = GovernanceItem(
                        proposal_id=d.get("proposal_id", ""),
                        title=d.get("title", ""),
                        component=d.get("component", "core"),
                        rationale=d.get("rationale", ""),
                        proposed_changes=list(d.get("proposed_changes", []) or []),
                        source=d.get("source", "swarm"),
                        risk=d.get("risk", "medium"),
                        status=GovernanceStatus(d.get("status", "pending")),
                        created_at=d.get("created_at") or datetime.now().isoformat(),
                        decided_at=d.get("decided_at"),
                        decided_by=d.get("decided_by"),
                        decision_note=d.get("decision_note"),
                    )
                    if item.proposal_id:
                        self.items[item.proposal_id] = item
                except Exception:
                    continue
        except Exception:
            # Noisy logs here create confusion; governance is recoverable.
            return

    def _save_state(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "saved_at": datetime.now().isoformat(),
                "count": len(self.items),
                "items": [x.to_dict() for x in self.items.values()],
            }
            self._state_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        except Exception:
            return

    def seed_from_plan(self, plan: List[Dict[str, Any]], source: str = "swarm") -> List[Dict[str, Any]]:
        created = []
        for entry in plan:
            proposal_id = self._proposal_id(entry.get("title", ""), entry.get("component", ""))
            if proposal_id in self.items:
                created.append(self.items[proposal_id].to_dict())
                continue
            item = GovernanceItem(
                proposal_id=proposal_id,
                title=entry.get("title", ""),
                component=entry.get("component", "core"),
                rationale=entry.get("rationale", ""),
                proposed_changes=entry.get("proposed_changes", []),
                source=source,
                risk="high" if entry.get("requires_approval", True) else "low",
            )
            self.items[proposal_id] = item
            created.append(item.to_dict())
        if created:
            self._save_state()
            memory_vault.record_event("governance_seeded", {"count": len(created)}, tags={"source": source})
        return created

    def list_items(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        values = [item for item in self.items.values()]
        if status:
            values = [item for item in values if item.status.value == status]
        values.sort(key=lambda x: x.created_at, reverse=True)
        return [item.to_dict() for item in values]

    def approve(self, proposal_id: str, decided_by: str = "owner", note: str = "") -> Dict[str, Any]:
        item = self.items.get(proposal_id)
        if not item:
            raise ValueError("proposal_id not found")
        item.status = GovernanceStatus.APPROVED
        item.decided_at = datetime.now().isoformat()
        item.decided_by = decided_by
        item.decision_note = note
        self._save_state()
        memory_vault.record_event("governance_approved", item.to_dict())
        return item.to_dict()

    def reject(self, proposal_id: str, decided_by: str = "owner", note: str = "") -> Dict[str, Any]:
        item = self.items.get(proposal_id)
        if not item:
            raise ValueError("proposal_id not found")
        item.status = GovernanceStatus.REJECTED
        item.decided_at = datetime.now().isoformat()
        item.decided_by = decided_by
        item.decision_note = note
        self._save_state()
        memory_vault.record_event("governance_rejected", item.to_dict())
        return item.to_dict()

    def summary(self) -> Dict[str, Any]:
        counts = {
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "applied": 0,
        }
        for item in self.items.values():
            counts[item.status.value] += 1
        return {
            "counts": counts,
            "total": len(self.items),
        }

    def approve_all(self, decided_by: str = "owner", note: str = "", status: str = "pending") -> Dict[str, Any]:
        approved = []
        for item in self.items.values():
            if item.status.value != status:
                continue
            item.status = GovernanceStatus.APPROVED
            item.decided_at = datetime.now().isoformat()
            item.decided_by = decided_by
            item.decision_note = note
            approved.append(item.to_dict())
        if approved:
            self._save_state()
            memory_vault.record_event("governance_approved_all", {"count": len(approved), "status": status})
        return {"approved_count": len(approved), "items": approved}

    def _proposal_id(self, title: str, component: str) -> str:
        payload = f"{title.strip().lower()}|{component.strip().lower()}"
        return f"gov_{hashlib.md5(payload.encode()).hexdigest()[:10]}"


governance_queue = GovernanceQueue()
