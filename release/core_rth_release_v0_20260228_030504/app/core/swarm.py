"""
Agent Swarm orchestrator for read-only analysis and sublimation planning.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import hashlib
import tempfile
from concurrent.futures import ThreadPoolExecutor

from .permissions import permission_gate, Capability, RiskLevel
from .evolution import evolution_analyzer
from .memory_vault import memory_vault
from .governance import governance_queue
from .plugin_hub import plugin_hub
from .knowledge_graph import get_knowledge_graph, NodeType, RelationType

CORE_PATHS = [
    "app/main.py",
    "app/core/config.py",
    "app/core/event_bus.py",
    "app/core/knowledge_graph.py",
    "app/core/rth_chronicle.py",
    "app/core/rth_cortex.py",
    "app/core/rth_praxis.py",
    "app/core/rth_feedbackloop.py",
    "app/core/rth_synapse.py",
    "app/core/rth_metamorph.py",
    "app/core/permissions.py",
    "app/core/memory_vault.py",
    "app/core/fs_scanner.py",
    "app/core/evolution.py",
    "app/core/jarvis.py",
    "app/core/swarm.py",
    "app/core/plugin_runtime.py",
    "app/core/rth_lm_adapter.py",
    "app/api/api_v1/api.py",
    "app/api/api_v1/endpoints/jarvis.py",
]

ROLE_HINTS = {
    "rth_chronicle": "chronicle",
    "knowledge_graph": "knowledge_graph",
    "rth_cortex": "cortex",
    "rth_praxis": "praxis",
    "rth_feedbackloop": "feedback_loop",
    "rth_synapse": "synapse",
    "rth_metamorph": "metamorph",
    "permissions": "guardian",
    "memory_vault": "memory",
    "fs_scanner": "sensors",
    "evolution": "praxis",
    "jarvis": "jarvis",
    "rth_lm_adapter": "jarvis",
    "swarm": "swarm",
    "event_bus": "synapse",
}

@dataclass
class SwarmProposal:
    request_id: str
    created_at: str
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "created_at": self.created_at,
            "status": self.status
        }

class SwarmOrchestrator:
    def __init__(self):
        self.last_report: Optional[Dict[str, Any]] = None

    def propose(self, reason: str) -> SwarmProposal:
        request = permission_gate.propose(
            capability=Capability.SWARM_ANALYSIS,
            action="swarm_analysis",
            scope={"mode": "read_only"},
            reason=reason,
            risk=RiskLevel.MEDIUM
        )
        return SwarmProposal(
            request_id=request.request_id,
            created_at=datetime.now().isoformat(),
            status=request.decision.value
        )

    def run(self, request_id: str, roots: Optional[List[str]] = None, max_projects: int = 200) -> Dict[str, Any]:
        if not permission_gate.check(request_id):
            return {"status": "denied", "request_id": request_id}

        # Run analysis steps in parallel to keep swarm responsive.
        with ThreadPoolExecutor(max_workers=3) as ex:
            fut_core = ex.submit(self._analyze_core)
            fut_evo = ex.submit(self._analyze_evolution, roots, max_projects)
            fut_rank = ex.submit(self._load_rankings)
            core_map = fut_core.result()
            evolution = fut_evo.result()
            ranking = fut_rank.result()

        high_ranked = self._extract_high_ranked(ranking)
        plan = self._sublimation_plan(core_map, evolution, ranking, high_ranked)

        with ThreadPoolExecutor(max_workers=3) as ex:
            fut_gov = ex.submit(governance_queue.seed_from_plan, plan, "swarm")
            fut_plg = ex.submit(plugin_hub.sync_from_high_ranked, high_ranked)
            fut_kg = ex.submit(self._ingest_to_knowledge_graph, high_ranked, plan)
            governance_seeded = fut_gov.result()
            plugin_sync = fut_plg.result()
            kg_ingest = fut_kg.result()

        report = {
            "status": "ok",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "core_map": core_map,
            "evolution": evolution,
            "ranking": ranking,
            "high_ranked": high_ranked,
            "sublimation_plan": plan,
            "governance": {
                "seeded": governance_seeded,
                "summary": governance_queue.summary(),
            },
            "plugin_hub": {
                "sync": plugin_sync,
                "top_candidates": plugin_hub.list_plugins(min_score=6.0)[:20],
            },
            "knowledge_graph_ingest": kg_ingest,
        }

        self.last_report = report
        memory_vault.record_event("swarm_report", report, tags={"mode": "read_only"})
        self._write_report(report)
        return report

    def _analyze_core(self) -> Dict[str, Any]:
        entries = []
        for rel in CORE_PATHS:
            path = Path(rel)
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            lines = text.count("\n") + 1 if text else 0
            role = self._infer_role(path.name)
            entries.append({
                "file": str(rel),
                "role": role,
                "lines": lines,
                "size": path.stat().st_size,
                "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            })

        return {
            "files": entries,
            "count": len(entries)
        }

    def _infer_role(self, filename: str) -> str:
        low = filename.lower()
        for key, role in ROLE_HINTS.items():
            if key in low:
                return role
        return "core"

    def _analyze_evolution(self, roots: Optional[List[str]], max_projects: int) -> Dict[str, Any]:
        # Evolution analysis on a multi-GB JSONL index can take a long time.
        # Prefer a cached snapshot if present (fast), otherwise compute live.
        cached = self._load_evolution_snapshot(roots=roots, max_projects=max_projects)
        if cached:
            return cached
        return evolution_analyzer.propose(roots=roots, max_projects=max_projects)

    def _load_evolution_snapshot(self, roots: Optional[List[str]], max_projects: int) -> Optional[Dict[str, Any]]:
        candidates = [
            Path("logs") / "evolution_snapshot.json",
            Path("storage_runtime") / "logs" / "evolution_snapshot.json",
            Path(tempfile.gettempdir()) / "rth_core" / "logs" / "evolution_snapshot.json",
        ]
        snap_path = next((p for p in candidates if p.exists()), None)
        if not snap_path:
            return None

        try:
            payload = json.loads(snap_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        if payload.get("status") != "ok":
            return None

        projects = payload.get("projects", [])
        proposals = payload.get("proposals", [])
        if not isinstance(projects, list):
            return None

        roots_norm = None
        if roots:
            roots_norm = {str(r).replace("\\", "/").lower() for r in roots if str(r).strip()}

        def in_roots(p: str) -> bool:
            if not roots_norm:
                return True
            low = str(p).replace("\\", "/").lower()
            return any(low.startswith(r) for r in roots_norm)

        filtered_projects = [p for p in projects if in_roots(p.get("root", ""))]
        filtered_projects = filtered_projects[: max(1, int(max_projects or 200))]

        filtered_proposals = []
        if isinstance(proposals, list):
            for pr in proposals:
                if in_roots(pr.get("root", "")):
                    filtered_proposals.append(pr)

        return {
            "status": "ok",
            "cached": True,
            "snapshot_path": str(snap_path),
            "snapshot_mtime": datetime.fromtimestamp(snap_path.stat().st_mtime).isoformat(),
            "projects_found": len(filtered_projects),
            "projects_returned": len(filtered_projects),
            "projects": filtered_projects,
            "proposals": filtered_proposals,
        }

    def _load_rankings(self) -> Dict[str, Any]:
        ranking = {}
        candidates = [
            Path("logs"),
            Path("storage_runtime") / "logs",
            Path(tempfile.gettempdir()) / "rth_core" / "logs",
        ]
        for name in ["selected_ranking.json", "project_ranking.json", "personal_project_ranking.json"]:
            for base in candidates:
                path = base / name
                if path.exists():
                    ranking[name] = json.loads(path.read_text(encoding="utf-8"))
                    break
        return ranking

    def _extract_high_ranked(self, ranking: Dict[str, Any], min_score: float = 6.0) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for source_name, payload in ranking.items():
            for item in payload.get("ranked", []):
                try:
                    score = float(item.get("score", 0.0))
                except Exception:
                    continue
                if score < min_score:
                    continue
                root = str(item.get("root", "")).strip()
                if not root:
                    continue
                key = root.lower()
                existing = merged.get(key)
                candidate = {
                    "root": root,
                    "score": score,
                    "source": source_name,
                    "reasons": item.get("reasons", []),
                    "types": item.get("types", []),
                    "markers": item.get("markers", []),
                    "file_count": item.get("file_count", item.get("code_files", 0)),
                }
                if not existing or score > existing["score"]:
                    merged[key] = candidate
        values = list(merged.values())
        values.sort(key=lambda x: x["score"], reverse=True)
        return values

    def _sublimation_plan(
        self,
        core_map: Dict[str, Any],
        evolution: Dict[str, Any],
        ranking: Dict[str, Any],
        high_ranked: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        plan = []

        plan.append({
            "id": "plan-core-01",
            "title": "Unify governance over all analysis and actions",
            "component": "synapse/guardian",
            "rationale": "Swarm, scans, and evolution all run read-only but lack a single approval ledger for planned edits.",
            "proposed_changes": [
                "Introduce approval queue for proposed edits from swarm output.",
                "Require explicit scope and rollback plan for any write action."
            ],
            "requires_approval": True
        })

        plan.append({
            "id": "plan-core-02",
            "title": "Promote KnowledgeGraph to first-class memory index",
            "component": "knowledge_graph/memory",
            "rationale": "Current memory_vault is append-only; graph can link projects, concepts, and evolution insights.",
            "proposed_changes": [
                "Add ingest of project markers and swarm summaries into KnowledgeGraph.",
                "Expose graph queries for concept and file linkage."
            ],
            "requires_approval": True
        })

        if high_ranked:
            targets = [r.get("root") for r in high_ranked[:10]]
            plan.append({
                "id": "plan-evo-01",
                "title": "Assimilate top local candidates into Jarvis plugins",
                "component": "praxis/swarm",
                "rationale": "Highest-ranked local projects provide reusable agent and tooling modules.",
                "proposed_changes": [
                    f"Review and extract reusable modules from: {', '.join(targets)}",
                    "Define plugin interface and load order in Jarvis."
                ],
                "requires_approval": True
            })

        if evolution.get("status") == "ok":
            plan.append({
                "id": "plan-evo-02",
                "title": "Stabilize project hygiene across core repos",
                "component": "praxis",
                "rationale": "Multiple projects lack README/tests/CI/license according to evolution signals.",
                "proposed_changes": [
                    "Generate minimal README and testing bootstrap for core repo.",
                    "Add CI config for lint/test on change."
                ],
                "requires_approval": True
            })

        return plan

    def _ingest_to_knowledge_graph(self, high_ranked: List[Dict[str, Any]], plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        kg = get_knowledge_graph()
        created_nodes = 0
        created_relations = 0

        root_id = "framework_jarvis_swarm"
        if kg.add_node(
            node_id=root_id,
            node_type=NodeType.FRAMEWORK,
            name="Jarvis Swarm Sublimation",
            description="Read-only swarm synthesis over high-ranked local evolutions.",
            properties={"source": "swarm", "mode": "read_only"},
            reliability_score=0.9,
        ):
            created_nodes += 1

        for entry in high_ranked[:50]:
            root = entry.get("root", "")
            if not root:
                continue
            node_id = f"entity_project_{hashlib.md5(root.lower().encode()).hexdigest()[:10]}"
            if kg.add_node(
                node_id=node_id,
                node_type=NodeType.ENTITY,
                name=root,
                description=f"High-ranked local candidate (score={entry.get('score', 0)})",
                properties={
                    "score": entry.get("score", 0),
                    "source": entry.get("source", "ranking"),
                },
                reliability_score=0.8,
            ):
                created_nodes += 1
            if kg.add_relation(
                source_node_id=root_id,
                target_node_id=node_id,
                relation_type=RelationType.APPLIES_TO,
                weight=0.9,
                confidence=0.85,
                properties={"from": "swarm_high_ranked"},
            ):
                created_relations += 1

        for item in plan:
            title = item.get("title", "")
            if not title:
                continue
            plan_id = f"concept_plan_{hashlib.md5(title.lower().encode()).hexdigest()[:10]}"
            if kg.add_node(
                node_id=plan_id,
                node_type=NodeType.CONCEPT,
                name=title,
                description=item.get("rationale", ""),
                properties={"component": item.get("component", "core")},
                reliability_score=0.85,
            ):
                created_nodes += 1
            if kg.add_relation(
                source_node_id=root_id,
                target_node_id=plan_id,
                relation_type=RelationType.ENHANCES,
                weight=0.8,
                confidence=0.8,
                properties={"from": "swarm_plan"},
            ):
                created_relations += 1

        return {
            "created_nodes": created_nodes,
            "created_relations": created_relations,
            "kg_status": kg.get_status(),
        }

    def _write_report(self, report: Dict[str, Any]):
        candidates = [
            Path("logs"),
            Path("storage_runtime") / "logs",
            Path(tempfile.gettempdir()) / "rth_core" / "logs",
        ]
        for logs in candidates:
            try:
                logs.mkdir(parents=True, exist_ok=True)
                (logs / "swarm_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
                return
            except Exception:
                continue

swarm_orchestrator = SwarmOrchestrator()
