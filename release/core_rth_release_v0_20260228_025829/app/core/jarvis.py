"""
Jarvis orchestrator with consent-gated execution.
"""
import asyncio
from typing import Dict, Any, Optional, List
import logging
import json
import hashlib
import tempfile
from datetime import datetime
from pathlib import Path
from .permissions import permission_gate, Capability, RiskLevel
from .memory_vault import memory_vault
from .fs_scanner import fs_scanner, ScanScope
from .evolution import evolution_analyzer
from .swarm import swarm_orchestrator
from .governance import governance_queue
from .plugin_hub import plugin_hub
from .plugin_runtime import plugin_runtime
from .knowledge_graph import get_knowledge_graph
from .strategy import strategy_engine
from .system_bridge import system_bridge
from .workspace_adapter import workspace_adapter
from .mail_bridge import mail_bridge
from .rth_lm_adapter import rth_lm_adapter
from .shadow_ccs_adapter import shadow_ccs_adapter
from .evolution_snapshot import evolution_snapshot_service
from .root_policy import load_strategic_roots

logger = logging.getLogger(__name__)

class JarvisCore:
    def __init__(self):
        self.last_scan: Optional[Dict[str, Any]] = None

    def capabilities(self) -> Dict[str, Any]:
        return {
            "capabilities": [c.value for c in Capability],
            "no_go": [c.value for c in permission_gate.no_go]
        }

    def propose_fs_scan(self, scope: ScanScope, reason: str) -> Dict[str, Any]:
        proposal = fs_scanner.propose(scope, reason)
        return proposal.to_dict()

    async def start_fs_scan(self, scope: ScanScope, request_id: str) -> Dict[str, Any]:
        result = await asyncio.to_thread(fs_scanner.execute, scope, request_id)
        self.last_scan = result
        return result

    def propose_evolution(self, roots: Optional[list] = None, max_projects: int = 200) -> Dict[str, Any]:
        return evolution_analyzer.propose(roots=roots, max_projects=max_projects)

    def evolution_snapshot_propose(self, roots: Optional[List[str]] = None, max_projects: int = 800, reason: str = "Rebuild evolution snapshot") -> Dict[str, Any]:
        return evolution_snapshot_service.propose(roots=roots, max_projects=max_projects, reason=reason)

    def evolution_snapshot_approve_and_start(self, request_id: str, decided_by: str = "owner") -> Dict[str, Any]:
        decision = permission_gate.approve(request_id=request_id, decided_by=decided_by)
        if decision.decision.value != "approved":
            return {"status": "denied", "decision": decision.to_dict()}
        return evolution_snapshot_service.start(request_id=request_id)

    def evolution_snapshot_status(self) -> Dict[str, Any]:
        return evolution_snapshot_service.status()

    def propose_swarm(self, reason: str) -> Dict[str, Any]:
        proposal = swarm_orchestrator.propose(reason)
        return proposal.to_dict()

    def run_swarm(self, request_id: str, roots: Optional[list] = None, max_projects: int = 200) -> Dict[str, Any]:
        return swarm_orchestrator.run(request_id, roots=roots, max_projects=max_projects)

    def governance_list(self, status: Optional[str] = None) -> Dict[str, Any]:
        return {
            "summary": governance_queue.summary(),
            "items": governance_queue.list_items(status=status),
        }

    def governance_approve(self, proposal_id: str, decided_by: str = "owner", note: str = "") -> Dict[str, Any]:
        return governance_queue.approve(proposal_id=proposal_id, decided_by=decided_by, note=note)

    def governance_reject(self, proposal_id: str, decided_by: str = "owner", note: str = "") -> Dict[str, Any]:
        return governance_queue.reject(proposal_id=proposal_id, decided_by=decided_by, note=note)

    def governance_approve_all(self, decided_by: str = "owner", note: str = "") -> Dict[str, Any]:
        return governance_queue.approve_all(decided_by=decided_by, note=note, status="pending")

    def plugins(self, min_score: float = 0.0) -> Dict[str, Any]:
        return {"plugins": plugin_hub.list_plugins(min_score=min_score)}

    def plugin_propose_activation(self, plugin_id: str, reason: str) -> Dict[str, Any]:
        return plugin_hub.propose_activation(plugin_id=plugin_id, reason=reason)

    def plugin_activate(self, request_id: str, decided_by: str = "owner") -> Dict[str, Any]:
        decision = permission_gate.approve(request_id=request_id, decided_by=decided_by)
        if decision.decision.value != "approved":
            return {"status": "denied", "decision": decision.to_dict()}
        return plugin_hub.activate(request_id=request_id)

    def plugin_runtime_status(self) -> Dict[str, Any]:
        return plugin_runtime.status()

    def plugin_runtime_manifest(self) -> Dict[str, Any]:
        return plugin_runtime.manifest()

    def plugin_runtime_propose(self, reason: str = "Plugin runtime cycle") -> Dict[str, Any]:
        return plugin_runtime.propose_cycle(reason=reason, scope={"mode": "read_only"})

    def plugin_runtime_run(self, request_id: str, min_score: float = 0.0) -> Dict[str, Any]:
        return plugin_runtime.run_cycle(request_id=request_id, min_score=min_score)

    def plugin_runtime_plan(self, min_score: float = 0.0) -> Dict[str, Any]:
        manifest = plugin_runtime.build_manifest(min_score=min_score)
        return plugin_runtime.plan(manifest)

    def plugin_activate_top(self, limit: int = 10, min_score: float = 0.0, decided_by: str = "owner") -> Dict[str, Any]:
        if not plugin_hub.list_plugins(min_score=0.0):
            self.strategy_top(limit=max(50, limit))
            self.strategy_launch_phase1()
            self.strategy_launch_phase2()
        plugins = plugin_hub.list_plugins(min_score=min_score)
        targets = [p for p in plugins if p.get("status") != "active"][:limit]
        activated = []
        failed = []
        for p in targets:
            plugin_id = p.get("plugin_id")
            try:
                proposal = plugin_hub.propose_activation(
                    plugin_id=plugin_id,
                    reason=f"Batch activate top plugin: {plugin_id}",
                )
                request_id = proposal.get("request_id")
                decision = permission_gate.approve(request_id=request_id, decided_by=decided_by)
                if decision.decision.value != "approved":
                    failed.append({"plugin_id": plugin_id, "status": "denied"})
                    continue
                result = plugin_hub.activate(request_id=request_id)
                if result.get("status") == "active":
                    activated.append(result.get("plugin"))
                else:
                    failed.append({"plugin_id": plugin_id, "status": result.get("status")})
            except Exception as e:
                failed.append({"plugin_id": plugin_id, "status": "error", "error": str(e)})
        return {
            "requested": len(targets),
            "activated": len(activated),
            "failed": failed,
            "items": activated,
        }

    def plugin_activate_range(self, start_rank: int = 1, end_rank: int = 10, decided_by: str = "owner") -> Dict[str, Any]:
        if start_rank <= 0 or end_rank <= 0 or end_rank < start_rank:
            raise ValueError("Invalid rank range")

        top100_path = self._find_top100_path()
        if not top100_path:
            raise FileNotFoundError("top100_evolutions.json not found")

        payload = json.loads(top100_path.read_text(encoding="utf-8"))
        items = payload.get("items", [])
        if not items:
            raise ValueError("top100_evolutions.json contains no items")

        sync = plugin_hub.sync_from_high_ranked(items)
        selected = [x for x in items if start_rank <= int(x.get("rank", 0)) <= end_rank]

        activations = []
        for entry in selected:
            root = str(entry.get("root", "")).strip()
            if not root:
                activations.append({
                    "rank": entry.get("rank"),
                    "root": root,
                    "status": "error",
                    "error": "missing_root",
                })
                continue
            plugin_id = f"plg_{hashlib.md5(root.lower().encode()).hexdigest()[:10]}"
            try:
                proposal = plugin_hub.propose_activation(
                    plugin_id=plugin_id,
                    reason=f"Activate rank {entry.get('rank')} from top100: {root}",
                )
                request_id = proposal.get("request_id")
                decision = permission_gate.approve(request_id=request_id, decided_by=decided_by)
                result = plugin_hub.activate(request_id=request_id)
                activations.append({
                    "rank": entry.get("rank"),
                    "root": root,
                    "plugin_id": plugin_id,
                    "request_id": request_id,
                    "decision": decision.decision.value,
                    "status": result.get("status"),
                })
            except Exception as e:
                activations.append({
                    "rank": entry.get("rank"),
                    "root": root,
                    "plugin_id": plugin_id,
                    "status": "error",
                    "error": str(e),
                })

        activated_count = sum(1 for a in activations if a.get("status") == "active")
        failed = [a for a in activations if a.get("status") != "active"]

        report = {
            "timestamp": datetime.now().isoformat(),
            "top100_path": str(top100_path),
            "range": {"start": start_rank, "end": end_rank},
            "sync": sync,
            "requested": len(selected),
            "activated_count": activated_count,
            "failed_count": len(failed),
            "failed": failed,
            "activations": activations,
        }
        audit_path = self._write_plugin_batch_audit(report)
        report["audit_path"] = audit_path
        memory_vault.record_event(
            "plugin_activation_batch",
            {
                "timestamp": report["timestamp"],
                "range": report["range"],
                "requested": report["requested"],
                "activated_count": report["activated_count"],
                "failed_count": report["failed_count"],
                "audit_path": audit_path,
            },
        )
        return report

    def plugins_weedkill_propose(self, reason: str = "Cull out-of-scope plugin roots") -> Dict[str, Any]:
        scope = {"strategic_roots": load_strategic_roots(), "mode": "disable_out_of_scope"}
        req = permission_gate.propose(
            capability=Capability.FILESYSTEM_WRITE,
            action="plugin_weedkill",
            scope=scope,
            reason=reason,
            risk=RiskLevel.HIGH,
        )
        return req.to_dict()

    def plugins_weedkill_approve_and_run(self, request_id: str, decided_by: str = "owner") -> Dict[str, Any]:
        decision = permission_gate.approve(request_id=request_id, decided_by=decided_by)
        if decision.decision.value != "approved":
            return {"status": "denied", "decision": decision.to_dict()}
        strategic_roots = list((decision.scope or {}).get("strategic_roots") or [])
        report = plugin_hub.weed_kill(scope_roots=strategic_roots or None)
        memory_vault.record_event("plugin_weedkill_applied", {"request_id": request_id, "changed": report.get("changed", 0)})
        return {"status": "ok", "request_id": request_id, "report": report}

    def _log_dir(self) -> Path:
        candidates = [
            Path("logs"),
            Path("storage_runtime") / "logs",
            Path(tempfile.gettempdir()) / "rth_core" / "logs",
        ]
        for c in candidates:
            try:
                c.mkdir(parents=True, exist_ok=True)
                probe = c / ".write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return c
            except Exception:
                continue
        return Path(tempfile.gettempdir()) / "rth_core" / "logs"

    def _find_top100_path(self) -> Optional[Path]:
        candidates = [
            Path("logs") / "top100_evolutions.json",
            Path("storage_runtime") / "logs" / "top100_evolutions.json",
            Path(tempfile.gettempdir()) / "rth_core" / "logs" / "top100_evolutions.json",
        ]
        existing = [p for p in candidates if p.exists()]
        if not existing:
            return None
        return sorted(existing, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    def _write_plugin_batch_audit(self, report: Dict[str, Any]) -> str:
        base = self._log_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = base / f"plugin_activation_batch_{ts}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        latest = base / "plugin_activation_batch_latest.json"
        latest.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return str(path)

    def kg_status(self) -> Dict[str, Any]:
        return get_knowledge_graph().get_status()

    def kg_query(self, concept: str, max_depth: int = 2) -> Dict[str, Any]:
        kg = get_knowledge_graph()
        return {
            "concept": concept,
            "results": kg.query_related_concepts(concept=concept, max_depth=max_depth),
        }

    def strategy_top(self, limit: int = 50) -> Dict[str, Any]:
        return strategy_engine.top_assets(limit=limit)

    def strategy_launch_phase1(self) -> Dict[str, Any]:
        return strategy_engine.launch_phase1()

    def strategy_launch_phase2(self) -> Dict[str, Any]:
        return strategy_engine.launch_phase2()

    def discover_workspaces(self) -> Dict[str, Any]:
        return {"workspaces": system_bridge.discover_workspaces()}

    def discover_apps(self, roots: List[str], max_depth: int = 4, max_results: int = 300) -> Dict[str, Any]:
        return system_bridge.discover_apps(roots=roots, max_depth=max_depth, max_results=max_results)

    def propose_app_launch(self, app_path: str, args: Optional[List[str]], reason: str) -> Dict[str, Any]:
        return system_bridge.propose_app_launch(app_path=app_path, args=args, reason=reason)

    def approve_and_launch_app(self, request_id: str, decided_by: str = "owner") -> Dict[str, Any]:
        decision = permission_gate.approve(request_id=request_id, decided_by=decided_by)
        if decision.decision.value != "approved":
            return {"status": "denied", "decision": decision.to_dict()}
        return system_bridge.execute_app_launch(request_id=request_id)

    def propose_mouse_action(self, action: str, x: Optional[int], y: Optional[int], reason: str) -> Dict[str, Any]:
        return system_bridge.propose_mouse_action(action=action, x=x, y=y, reason=reason)

    def mouse_status(self) -> Dict[str, Any]:
        return system_bridge.mouse_status()

    def approve_and_mouse_action(self, request_id: str, decided_by: str = "owner") -> Dict[str, Any]:
        decision = permission_gate.approve(request_id=request_id, decided_by=decided_by)
        if decision.decision.value != "approved":
            return {"status": "denied", "decision": decision.to_dict()}
        return system_bridge.execute_mouse_action(request_id=request_id)

    def workspace_profiles(self) -> Dict[str, Any]:
        return workspace_adapter.profiles()

    def workspace_propose(self, workspace: str, action: str, reason: str, command: Optional[List[str]] = None) -> Dict[str, Any]:
        return workspace_adapter.propose(workspace=workspace, action=action, reason=reason, command=command)

    def workspace_approve_and_execute(self, request_id: str, decided_by: str = "owner") -> Dict[str, Any]:
        decision = permission_gate.approve(request_id=request_id, decided_by=decided_by)
        if decision.decision.value != "approved":
            return {"status": "denied", "decision": decision.to_dict()}
        return workspace_adapter.execute(request_id=request_id)

    def workspace_jobs(self) -> Dict[str, Any]:
        return workspace_adapter.jobs()

    def rth_lm_status(self) -> Dict[str, Any]:
        return rth_lm_adapter.status()

    def rth_lm_propose(
        self,
        action: str,
        reason: str,
        prompt: Optional[str] = None,
        max_new: int = 256,
        temperature: float = 0.7,
        top_k: int = 40,
        top_p: float = 0.9,
    ) -> Dict[str, Any]:
        return rth_lm_adapter.propose(
            action=action,
            reason=reason,
            prompt=prompt,
            max_new=max_new,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
        )

    def rth_lm_approve_and_run(self, request_id: str, decided_by: str = "owner") -> Dict[str, Any]:
        decision = permission_gate.approve(request_id=request_id, decided_by=decided_by)
        if decision.decision.value != "approved":
            return {"status": "denied", "decision": decision.to_dict()}
        return rth_lm_adapter.execute(request_id=request_id)

    def rth_lm_jobs(self) -> Dict[str, Any]:
        return rth_lm_adapter.jobs()

    def shadow_status(self) -> Dict[str, Any]:
        return shadow_ccs_adapter.status()

    def shadow_propose(
        self,
        action: str,
        reason: str,
        output: Optional[str] = None,
        policy_id: str = "default",
        cluster_size: int = 3,
        context: Optional[Dict[str, Any]] = None,
        iterations: int = 100,
        warmup: int = 10,
    ) -> Dict[str, Any]:
        return shadow_ccs_adapter.propose(
            action=action,
            reason=reason,
            output=output,
            policy_id=policy_id,
            cluster_size=cluster_size,
            context=context,
            iterations=iterations,
            warmup=warmup,
        )

    def shadow_approve_and_run(self, request_id: str, decided_by: str = "owner") -> Dict[str, Any]:
        decision = permission_gate.approve(request_id=request_id, decided_by=decided_by)
        if decision.decision.value != "approved":
            return {"status": "denied", "decision": decision.to_dict()}
        return shadow_ccs_adapter.execute(request_id=request_id)

    def shadow_jobs(self) -> Dict[str, Any]:
        return shadow_ccs_adapter.jobs()

    def mail_status(self) -> Dict[str, Any]:
        return mail_bridge.status()

    def mail_poll_once(self, limit: int = 20) -> Dict[str, Any]:
        return mail_bridge.poll_once(limit=limit)

    def get_status(self) -> Dict[str, Any]:
        return {
            "memory": memory_vault.get_stats(),
            "last_scan": self.last_scan,
            "last_swarm_report": swarm_orchestrator.last_report,
            "governance": governance_queue.summary(),
        }

jarvis_core = JarvisCore()
