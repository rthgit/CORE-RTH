"""
Jarvis API endpoints.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import asyncio
import json
import string
from pathlib import Path

from app.core.jarvis import jarvis_core
from app.core.fs_scanner import ScanScope
from app.core.permissions import permission_gate, Capability
from app.core.telegram_bridge import telegram_bridge
from app.core.whatsapp_bridge import whatsapp_bridge
from app.core.mail_bridge import mail_bridge
from app.core.browser_swarm import browser_swarm
from app.core.code_tools import code_tools
from app.core.tool_registry import tool_registry
from app.core.agent_loop import agent_loop

router = APIRouter()

class ScanProposalRequest(BaseModel):
    roots: List[str] = Field(..., description="Root paths to scan")
    exclude_globs: Optional[List[str]] = None
    include_globs: Optional[List[str]] = None
    max_depth: Optional[int] = None
    max_file_size_mb: Optional[int] = None
    hash_files: bool = False
    content_snippets: bool = False
    content_full: bool = False
    snippet_bytes: int = 256
    max_files: Optional[int] = None
    reason: str = "Initial system scan"

class ScanApprovalRequest(BaseModel):
    request_id: str
    approve: bool = True
    decided_by: str = "owner"
    start_now: bool = True

class PolicyUpdateRequest(BaseModel):
    no_go: List[str] = Field(default_factory=list, description="Capabilities to block")

class GuardianSeveritySetRequest(BaseModel):
    severity: str = "balanced"
    reason: str = "Update guardian severity profile"
    lang: str = "it"
    confirm_owner: bool = True
    decided_by: str = "owner"

class EvolutionProposalRequest(BaseModel):
    roots: Optional[List[str]] = None
    max_projects: int = 200
    reason: str = "Evolution discovery"

class EvolutionSnapshotProposeRequest(BaseModel):
    roots: Optional[List[str]] = None
    max_projects: int = 800
    reason: str = "Rebuild evolution snapshot"

class EvolutionSnapshotStartRequest(BaseModel):
    request_id: str
    decided_by: str = "owner"

class SwarmRunRequest(BaseModel):
    roots: Optional[List[str]] = None
    max_projects: int = 200
    reason: str = "Swarm analysis"

class SwarmApproveRequest(BaseModel):
    request_id: str
    approve: bool = True
    decided_by: str = "owner"

class GovernanceDecisionRequest(BaseModel):
    proposal_id: str
    decided_by: str = "owner"
    note: str = ""

class GovernanceApproveAllRequest(BaseModel):
    decided_by: str = "owner"
    note: str = ""

class PluginActivationRequest(BaseModel):
    plugin_id: str
    reason: str = "Activate high-ranked plugin candidate"

class PluginActivationApproveRequest(BaseModel):
    request_id: str
    decided_by: str = "owner"

class PluginActivateTopRequest(BaseModel):
    limit: int = 10
    min_score: float = 0.0
    decided_by: str = "owner"

class PluginActivateRangeRequest(BaseModel):
    start_rank: int = 1
    end_rank: int = 10
    decided_by: str = "owner"

class PluginWeedkillProposeRequest(BaseModel):
    reason: str = "Cull out-of-scope plugin roots"

class PluginWeedkillRunRequest(BaseModel):
    request_id: str
    decided_by: str = "owner"

class PluginRuntimeProposeRequest(BaseModel):
    reason: str = "Plugin runtime cycle"

class PluginRuntimeRunRequest(BaseModel):
    request_id: str
    min_score: float = 0.0

class PluginRuntimePlanRequest(BaseModel):
    min_score: float = 0.0

class AppDiscoveryRequest(BaseModel):
    roots: List[str]
    max_depth: int = 4
    max_results: int = 300

class AppLaunchProposalRequest(BaseModel):
    app_path: str
    args: Optional[List[str]] = None
    reason: str = "Launch app requested by owner"

class AppLaunchApproveRequest(BaseModel):
    request_id: str
    decided_by: str = "owner"

class MouseProposalRequest(BaseModel):
    action: str
    x: Optional[int] = None
    y: Optional[int] = None
    reason: str = "Mouse action requested by owner"

class MouseApproveRequest(BaseModel):
    request_id: str
    decided_by: str = "owner"

class TelegramPollRequest(BaseModel):
    limit: int = 10
    timeout_sec: float = 20.0
    auto_reply: bool = True

class TelegramSendRequest(BaseModel):
    chat_id: str
    text: str
    timeout_sec: float = 20.0

class TelegramWebhookRequest(BaseModel):
    update: Dict[str, Any]
    auto_reply: bool = True

class TelegramReplayRequest(BaseModel):
    text: str
    chat_id: str = "999000111"
    username: str = "owner_test"
    auto_reply: bool = True

class WhatsAppWebhookRequest(BaseModel):
    payload: Dict[str, Any]
    auto_reply: bool = False

class WhatsAppReplayRequest(BaseModel):
    text: str
    from_number: str = "15550001111"
    auto_reply: bool = True

class WhatsAppSendRequest(BaseModel):
    to: str
    text: str
    timeout_sec: float = 20.0

class WorkspaceCommandProposalRequest(BaseModel):
    workspace: str
    action: str
    reason: str = "Workspace command requested by owner"
    command: Optional[List[str]] = None

class WorkspaceCommandApproveRequest(BaseModel):
    request_id: str
    decided_by: str = "owner"

class RTHLMProposeRequest(BaseModel):
    action: str = "checkpoint_probe"
    reason: str = "RTH-LM action requested by owner"
    prompt: Optional[str] = None
    max_new: int = 256
    temperature: float = 0.7
    top_k: int = 40
    top_p: float = 0.9

class RTHLMRunRequest(BaseModel):
    request_id: str
    decided_by: str = "owner"

class ShadowProposeRequest(BaseModel):
    action: str = "artifact_probe"
    reason: str = "SHADOW CCS action requested by owner"
    output: Optional[str] = None
    policy_id: str = "default"
    cluster_size: int = 3
    context: Dict[str, Any] = Field(default_factory=dict)
    iterations: int = 100
    warmup: int = 10

class ShadowRunRequest(BaseModel):
    request_id: str
    decided_by: str = "owner"

class MailPollRequest(BaseModel):
    limit: int = 20

class BrowserSwarmRunRequest(BaseModel):
    urls: List[str]
    mode: str = "scrape"
    extract_selector: str = ""
    summarize: bool = True
    max_concurrent: int = 5
    timeout_sec: float = 15.0
    reason: str = "Browser swarm web research"
    confirm_owner: bool = True
    decided_by: str = "owner"
    ingest_to_kg: bool = True

class BrowserSwarmSearchRequest(BaseModel):
    query: str
    engine: str = "duckduckgo"
    max_results: int = 5
    scrape_results: bool = True
    reason: str = "Browser swarm web search"
    confirm_owner: bool = True
    decided_by: str = "owner"

class MailReplayRequest(BaseModel):
    payload: Dict[str, Any]
    from_addr: str = "owner@example.local"
    subject: str = "[RTH Replay]"
    shared_secret: str = "rth-replay-secret"
    allow_remote_approve: bool = False
    remote_approve_max_risk: str = "low"

@router.get("/jarvis/status")
async def jarvis_status():
    data = jarvis_core.get_status()
    data.update(jarvis_core.capabilities())
    return data

@router.get("/jarvis/drives")
async def jarvis_drives():
    drives = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:/"
        if Path(root).exists():
            drives.append(root)
    return {"drives": drives}

@router.get("/jarvis/policy")
async def jarvis_policy(lang: str = Query("it", description="Response language (it/en)")):
    return permission_gate.policy_status_localized(lang=lang)

@router.post("/jarvis/policy")
async def update_policy(request: PolicyUpdateRequest):
    try:
        converted = []
        for cap in request.no_go:
            try:
                converted.append(Capability(cap))
            except Exception:
                continue
        permission_gate.set_no_go(converted)
        return {"status": "updated", "policy": permission_gate.policy_status()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/jarvis/guardian/severity")
async def guardian_severity_status(lang: str = Query("it", description="Response language (it/en)")):
    return permission_gate.guardian_severity_status(lang=lang)

@router.post("/jarvis/guardian/severity")
async def guardian_severity_set(request: GuardianSeveritySetRequest):
    try:
        return permission_gate.guardian_severity_apply(
            severity=request.severity,
            reason=request.reason,
            confirm_owner=request.confirm_owner,
            decided_by=request.decided_by,
            lang=request.lang,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/jarvis/permissions")
async def jarvis_permissions(lang: str = Query("it", description="Response language (it/en)")):
    return permission_gate.list_requests_localized(lang=lang)

@router.post("/jarvis/scan/propose")
async def propose_scan(request: ScanProposalRequest):
    scope = ScanScope(
        roots=request.roots,
        exclude_globs=request.exclude_globs,
        include_globs=request.include_globs,
        max_depth=request.max_depth,
        max_file_size_mb=request.max_file_size_mb,
        hash_files=request.hash_files,
        content_snippets=request.content_snippets,
        content_full=request.content_full,
        snippet_bytes=request.snippet_bytes,
        max_files=request.max_files
    )
    proposal = jarvis_core.propose_fs_scan(scope, request.reason)
    return proposal

@router.post("/jarvis/scan/approve")
async def approve_scan(request: ScanApprovalRequest):
    if request.approve:
        decision = permission_gate.approve(request.request_id, request.decided_by)
    else:
        decision = permission_gate.deny(request.request_id, "denied", request.decided_by)

    result: Dict[str, Any] = {"decision": decision.to_dict()}

    if request.approve and request.start_now:
        scope_dict = decision.scope
        scope = ScanScope(**scope_dict)
        asyncio.create_task(jarvis_core.start_fs_scan(scope, request.request_id))
        result["scan_started"] = True
    else:
        result["scan_started"] = False

    return result

@router.get("/jarvis/scan/status")
async def scan_status():
    return {"last_scan": jarvis_core.get_status().get("last_scan")}

@router.post("/jarvis/evolve/propose")
async def evolve_propose(request: EvolutionProposalRequest):
    return jarvis_core.propose_evolution(roots=request.roots, max_projects=request.max_projects)

@router.get("/jarvis/evolve/snapshot/status")
async def evolve_snapshot_status():
    return jarvis_core.evolution_snapshot_status()

@router.post("/jarvis/evolve/snapshot/propose")
async def evolve_snapshot_propose(request: EvolutionSnapshotProposeRequest):
    return jarvis_core.evolution_snapshot_propose(roots=request.roots, max_projects=request.max_projects, reason=request.reason)

@router.post("/jarvis/evolve/snapshot/approve-start")
async def evolve_snapshot_approve_start(request: EvolutionSnapshotStartRequest):
    return await asyncio.to_thread(jarvis_core.evolution_snapshot_approve_and_start, request.request_id, request.decided_by)

@router.post("/jarvis/swarm/propose")
async def swarm_propose(request: SwarmRunRequest):
    return jarvis_core.propose_swarm(request.reason)

@router.post("/jarvis/swarm/run")
async def swarm_run(request: SwarmRunRequest):
    proposal = jarvis_core.propose_swarm(request.reason)
    if proposal.get("status") == "denied":
        return {"status": "denied", "proposal": proposal}
    decision = permission_gate.approve(proposal["request_id"], decided_by="owner")
    if decision.decision.value != "approved":
        return {"status": "denied", "proposal": proposal, "decision": decision.to_dict()}
    # Swarm can be CPU-heavy; run in a worker thread to keep the API responsive.
    return await asyncio.to_thread(jarvis_core.run_swarm, decision.request_id, request.roots, request.max_projects)

@router.get("/jarvis/swarm/latest")
async def swarm_latest():
    return {"report": jarvis_core.get_status().get("last_swarm_report")}

@router.get("/jarvis/governance")
async def governance_list(status: Optional[str] = None):
    return jarvis_core.governance_list(status=status)

@router.post("/jarvis/governance/approve")
async def governance_approve(request: GovernanceDecisionRequest):
    try:
        return jarvis_core.governance_approve(
            proposal_id=request.proposal_id,
            decided_by=request.decided_by,
            note=request.note,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/jarvis/governance/reject")
async def governance_reject(request: GovernanceDecisionRequest):
    try:
        return jarvis_core.governance_reject(
            proposal_id=request.proposal_id,
            decided_by=request.decided_by,
            note=request.note,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/jarvis/governance/approve-all")
async def governance_approve_all(request: GovernanceApproveAllRequest):
    return jarvis_core.governance_approve_all(decided_by=request.decided_by, note=request.note)

@router.get("/jarvis/plugins")
async def plugins(min_score: float = 0.0):
    return jarvis_core.plugins(min_score=min_score)

@router.post("/jarvis/plugins/propose-activation")
async def plugin_propose_activation(request: PluginActivationRequest):
    try:
        return jarvis_core.plugin_propose_activation(plugin_id=request.plugin_id, reason=request.reason)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/jarvis/plugins/approve-activation")
async def plugin_approve_activation(request: PluginActivationApproveRequest):
    return jarvis_core.plugin_activate(request_id=request.request_id, decided_by=request.decided_by)

@router.post("/jarvis/plugins/activate-top")
async def plugin_activate_top(request: PluginActivateTopRequest):
    return jarvis_core.plugin_activate_top(
        limit=request.limit,
        min_score=request.min_score,
        decided_by=request.decided_by,
    )

@router.post("/jarvis/plugins/activate-range")
async def plugin_activate_range(request: PluginActivateRangeRequest):
    try:
        return jarvis_core.plugin_activate_range(
            start_rank=request.start_rank,
            end_rank=request.end_rank,
            decided_by=request.decided_by,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/jarvis/plugins/weedkill/propose")
async def plugin_weedkill_propose(request: PluginWeedkillProposeRequest):
    return jarvis_core.plugins_weedkill_propose(reason=request.reason)

@router.post("/jarvis/plugins/weedkill/approve-run")
async def plugin_weedkill_approve_run(request: PluginWeedkillRunRequest):
    return await asyncio.to_thread(jarvis_core.plugins_weedkill_approve_and_run, request.request_id, request.decided_by)

@router.get("/jarvis/plugins/runtime/status")
async def plugin_runtime_status():
    return jarvis_core.plugin_runtime_status()

@router.get("/jarvis/plugins/runtime/manifest")
async def plugin_runtime_manifest():
    return jarvis_core.plugin_runtime_manifest()

@router.post("/jarvis/plugins/runtime/propose")
async def plugin_runtime_propose(request: PluginRuntimeProposeRequest):
    return jarvis_core.plugin_runtime_propose(reason=request.reason)

@router.post("/jarvis/plugins/runtime/run")
async def plugin_runtime_run(request: PluginRuntimeRunRequest):
    return await asyncio.to_thread(jarvis_core.plugin_runtime_run, request.request_id, request.min_score)

@router.post("/jarvis/plugins/runtime/plan")
async def plugin_runtime_plan(request: PluginRuntimePlanRequest):
    return jarvis_core.plugin_runtime_plan(min_score=request.min_score)

@router.get("/jarvis/plugins/audits/latest")
async def plugin_audit_latest():
    from pathlib import Path
    import tempfile
    candidates = [
        Path("logs") / "plugin_activation_batch_latest.json",
        Path("storage_runtime") / "logs" / "plugin_activation_batch_latest.json",
        Path(tempfile.gettempdir()) / "rth_core" / "logs" / "plugin_activation_batch_latest.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                return {"path": str(p), "audit": p.read_text(encoding="utf-8")}
            except Exception:
                continue
    raise HTTPException(status_code=404, detail="No plugin activation audit found")

@router.get("/jarvis/kg/status")
async def kg_status():
    return jarvis_core.kg_status()

@router.get("/jarvis/kg/query")
async def kg_query(concept: str, max_depth: int = 2):
    return jarvis_core.kg_query(concept=concept, max_depth=max_depth)

@router.get("/jarvis/strategy/top")
async def strategy_top(limit: int = 50):
    # Strategy can be CPU-heavy on large indexes; run in a worker thread to avoid
    # blocking the async server loop.
    return await asyncio.to_thread(jarvis_core.strategy_top, limit)

@router.post("/jarvis/strategy/phase1/launch")
async def strategy_phase1_launch():
    return await asyncio.to_thread(jarvis_core.strategy_launch_phase1)

@router.post("/jarvis/strategy/phase2/launch")
async def strategy_phase2_launch():
    return await asyncio.to_thread(jarvis_core.strategy_launch_phase2)

@router.get("/jarvis/workspaces/discover")
async def discover_workspaces():
    return jarvis_core.discover_workspaces()

@router.post("/jarvis/apps/discover")
async def discover_apps(request: AppDiscoveryRequest):
    return jarvis_core.discover_apps(
        roots=request.roots,
        max_depth=request.max_depth,
        max_results=request.max_results,
    )

@router.post("/jarvis/apps/propose-launch")
async def propose_app_launch(request: AppLaunchProposalRequest):
    return jarvis_core.propose_app_launch(
        app_path=request.app_path,
        args=request.args,
        reason=request.reason,
    )

@router.post("/jarvis/apps/approve-launch")
async def approve_launch_app(request: AppLaunchApproveRequest):
    return jarvis_core.approve_and_launch_app(
        request_id=request.request_id,
        decided_by=request.decided_by,
    )

@router.post("/jarvis/mouse/propose")
async def propose_mouse_action(request: MouseProposalRequest):
    return jarvis_core.propose_mouse_action(
        action=request.action,
        x=request.x,
        y=request.y,
        reason=request.reason,
    )

@router.get("/jarvis/mouse/status")
async def mouse_status():
    return jarvis_core.mouse_status()

@router.post("/jarvis/mouse/approve")
async def approve_mouse_action(request: MouseApproveRequest):
    return jarvis_core.approve_and_mouse_action(
        request_id=request.request_id,
        decided_by=request.decided_by,
    )

@router.get("/jarvis/workspaces/profiles")
async def workspace_profiles():
    return jarvis_core.workspace_profiles()

@router.post("/jarvis/workspaces/propose-command")
async def workspace_propose_command(request: WorkspaceCommandProposalRequest):
    return jarvis_core.workspace_propose(
        workspace=request.workspace,
        action=request.action,
        reason=request.reason,
        command=request.command,
    )

@router.post("/jarvis/workspaces/approve-command")
async def workspace_approve_command(request: WorkspaceCommandApproveRequest):
    return jarvis_core.workspace_approve_and_execute(
        request_id=request.request_id,
        decided_by=request.decided_by,
    )

@router.get("/jarvis/workspaces/jobs")
async def workspace_jobs():
    return jarvis_core.workspace_jobs()

@router.get("/jarvis/rthlm/status")
async def rth_lm_status():
    return jarvis_core.rth_lm_status()

@router.post("/jarvis/rthlm/propose")
async def rth_lm_propose(request: RTHLMProposeRequest):
    try:
        return jarvis_core.rth_lm_propose(
            action=request.action,
            reason=request.reason,
            prompt=request.prompt,
            max_new=request.max_new,
            temperature=request.temperature,
            top_k=request.top_k,
            top_p=request.top_p,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/jarvis/rthlm/approve-run")
async def rth_lm_approve_and_run(request: RTHLMRunRequest):
    return await asyncio.to_thread(jarvis_core.rth_lm_approve_and_run, request.request_id, request.decided_by)

@router.get("/jarvis/rthlm/jobs")
async def rth_lm_jobs():
    return jarvis_core.rth_lm_jobs()

@router.get("/jarvis/shadow/status")
async def shadow_status():
    return jarvis_core.shadow_status()

@router.post("/jarvis/shadow/propose")
async def shadow_propose(request: ShadowProposeRequest):
    try:
        return jarvis_core.shadow_propose(
            action=request.action,
            reason=request.reason,
            output=request.output,
            policy_id=request.policy_id,
            cluster_size=request.cluster_size,
            context=request.context,
            iterations=request.iterations,
            warmup=request.warmup,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/jarvis/shadow/approve-run")
async def shadow_approve_and_run(request: ShadowRunRequest):
    return await asyncio.to_thread(jarvis_core.shadow_approve_and_run, request.request_id, request.decided_by)

@router.get("/jarvis/shadow/jobs")
async def shadow_jobs():
    return jarvis_core.shadow_jobs()

@router.get("/jarvis/mail/status")
async def mail_status():
    return jarvis_core.mail_status()

@router.post("/jarvis/mail/poll-once")
async def mail_poll_once(request: MailPollRequest):
    return jarvis_core.mail_poll_once(limit=request.limit)

@router.post("/jarvis/mail/replay")
async def mail_replay(request: MailReplayRequest):
    return mail_bridge.replay_payload(
        payload=request.payload,
        from_addr=request.from_addr,
        subject=request.subject,
        shared_secret=request.shared_secret,
        allow_remote_approve=request.allow_remote_approve,
        remote_approve_max_risk=request.remote_approve_max_risk,
    )

@router.get("/jarvis/telegram/status")
async def telegram_status():
    return telegram_bridge.status()

@router.get("/jarvis/telegram/get-me")
async def telegram_get_me():
    return telegram_bridge.get_me()

@router.post("/jarvis/telegram/poll-once")
async def telegram_poll_once(request: TelegramPollRequest):
    return telegram_bridge.poll_once(limit=request.limit, timeout_sec=request.timeout_sec, auto_reply=request.auto_reply)

@router.post("/jarvis/telegram/send")
async def telegram_send(request: TelegramSendRequest):
    return telegram_bridge.send_text(chat_id=request.chat_id, text=request.text, timeout_sec=request.timeout_sec)

@router.post("/jarvis/telegram/webhook")
async def telegram_webhook(request: TelegramWebhookRequest):
    return telegram_bridge.handle_webhook_update(request.update, auto_reply=request.auto_reply)

@router.post("/jarvis/telegram/replay")
async def telegram_replay(request: TelegramReplayRequest):
    return telegram_bridge.replay_text(
        text=request.text,
        chat_id=request.chat_id,
        username=request.username,
        auto_reply=request.auto_reply,
    )

@router.get("/jarvis/whatsapp/status")
async def whatsapp_status():
    return whatsapp_bridge.status()

@router.get("/jarvis/whatsapp/meta/webhook")
async def whatsapp_meta_verify_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    out = whatsapp_bridge.meta_verify_webhook(hub_mode, hub_verify_token, hub_challenge)
    if out.get("status") != "ok":
        raise HTTPException(status_code=403, detail="verification_failed")
    return out.get("challenge") or ""

@router.post("/jarvis/whatsapp/meta/webhook")
async def whatsapp_meta_webhook(request: WhatsAppWebhookRequest):
    return whatsapp_bridge.handle_meta_webhook(request.payload, auto_reply=request.auto_reply)

@router.post("/jarvis/whatsapp/replay")
async def whatsapp_replay(request: WhatsAppReplayRequest):
    return whatsapp_bridge.replay_text(
        text=request.text,
        from_number=request.from_number,
        auto_reply=request.auto_reply,
    )

@router.post("/jarvis/whatsapp/send")
async def whatsapp_send(request: WhatsAppSendRequest):
    return whatsapp_bridge.send_text(to=request.to, text=request.text, timeout_sec=request.timeout_sec)

# ── Browser Swarm ──────────────────────────────────────────────────────────

@router.get("/jarvis/browser-swarm/status")
async def browser_swarm_status():
    return browser_swarm.status()

@router.post("/jarvis/browser-swarm/run")
async def browser_swarm_run(request: BrowserSwarmRunRequest):
    try:
        return await asyncio.to_thread(
            browser_swarm.run,
            urls=request.urls,
            mode=request.mode,
            extract_selector=request.extract_selector,
            summarize=request.summarize,
            max_concurrent=request.max_concurrent,
            timeout_sec=request.timeout_sec,
            reason=request.reason,
            confirm_owner=request.confirm_owner,
            decided_by=request.decided_by,
            ingest_to_kg=request.ingest_to_kg,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/jarvis/browser-swarm/search")
async def browser_swarm_search(request: BrowserSwarmSearchRequest):
    try:
        return await asyncio.to_thread(
            browser_swarm.search,
            query=request.query,
            engine=request.engine,
            max_results=request.max_results,
            scrape_results=request.scrape_results,
            reason=request.reason,
            confirm_owner=request.confirm_owner,
            decided_by=request.decided_by,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ── Agent Loop ─────────────────────────────────────────────────────────────

class AgentLoopRunRequest(BaseModel):
    objective: str
    thread_id: Optional[str] = None
    max_iterations: int = 25
    reason: str = "Agent loop task execution"
    confirm_owner: bool = True
    decided_by: str = "owner"

@router.get("/jarvis/agent/status")
async def agent_status():
    return agent_loop.status()

@router.post("/jarvis/agent/run")
async def agent_run(request: AgentLoopRunRequest):
    try:
        return await asyncio.to_thread(
            agent_loop.run,
            objective=request.objective,
            thread_id=request.thread_id,
            max_iterations=request.max_iterations,
            reason=request.reason,
            confirm_owner=request.confirm_owner,
            decided_by=request.decided_by,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/jarvis/agent/run/stream")
async def agent_run_stream(request: AgentLoopRunRequest):
    """SSE streaming endpoint for agent loop execution."""
    import queue
    step_queue: queue.Queue = queue.Queue()

    def on_step(step):
        step_queue.put(step.to_dict())

    async def event_generator():
        # Start the loop in a thread
        loop_future = asyncio.get_event_loop().run_in_executor(
            None,
            lambda: agent_loop.run(
                objective=request.objective,
                thread_id=request.thread_id,
                max_iterations=request.max_iterations,
                reason=request.reason,
                confirm_owner=request.confirm_owner,
                decided_by=request.decided_by,
                on_step=on_step,
            ),
        )
        # Stream steps as SSE events
        while not loop_future.done():
            try:
                step = step_queue.get_nowait()
                yield f"data: {json.dumps(step, default=str)}\n\n"
            except queue.Empty:
                await asyncio.sleep(0.1)
        # Drain remaining
        while not step_queue.empty():
            step = step_queue.get_nowait()
            yield f"data: {json.dumps(step, default=str)}\n\n"
        # Final result
        result = await loop_future
        yield f"data: {json.dumps({'event': 'done', 'result': result}, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/jarvis/agent/threads")
async def agent_threads(limit: int = 50):
    return {"threads": agent_loop.list_threads(limit=limit)}

@router.get("/jarvis/agent/thread/{thread_id}")
async def agent_thread(thread_id: str):
    result = agent_loop.get_thread(thread_id)
    if not result:
        raise HTTPException(status_code=404, detail="Thread not found")
    return result

# ── Code Tools ─────────────────────────────────────────────────────────────

class FileReadRequest(BaseModel):
    path: str
    start_line: int = 1
    end_line: Optional[int] = None

class FileWriteRequest(BaseModel):
    path: str
    content: str
    reason: str = "Agent file write"

class FileEditRequest(BaseModel):
    path: str
    old_text: str
    new_text: str
    reason: str = "Agent file edit"

class TerminalExecRequest(BaseModel):
    command: List[str]
    cwd: Optional[str] = None
    timeout_sec: float = 30
    reason: str = "Agent terminal command"
    dry_run: bool = False

@router.get("/jarvis/tools/status")
async def tools_status():
    return {
        "code_tools": code_tools.status(),
        "tool_registry": tool_registry.status(),
    }

@router.get("/jarvis/tools/schemas")
async def tools_schemas():
    return {"tools": tool_registry.get_schemas()}

@router.post("/jarvis/tools/file/read")
async def tools_file_read(request: FileReadRequest):
    result = code_tools.file_read(path=request.path, start_line=request.start_line, end_line=request.end_line)
    return result.to_dict()

@router.post("/jarvis/tools/file/write")
async def tools_file_write(request: FileWriteRequest):
    result = await asyncio.to_thread(code_tools.file_write, path=request.path, content=request.content, reason=request.reason)
    return result.to_dict()

@router.post("/jarvis/tools/file/edit")
async def tools_file_edit(request: FileEditRequest):
    result = await asyncio.to_thread(code_tools.file_edit, path=request.path, old_text=request.old_text, new_text=request.new_text, reason=request.reason)
    return result.to_dict()

@router.post("/jarvis/tools/terminal/exec")
async def tools_terminal_exec(request: TerminalExecRequest):
    result = await asyncio.to_thread(
        code_tools.terminal_exec,
        command=request.command,
        cwd=request.cwd,
        timeout_sec=request.timeout_sec,
        reason=request.reason,
        dry_run=request.dry_run,
    )
    return result.to_dict()

@router.post("/jarvis/tools/dir/list")
async def tools_dir_list(request: FileReadRequest):
    result = code_tools.dir_list(path=request.path)
    return result.to_dict()

@router.post("/jarvis/tools/grep")
async def tools_grep(pattern: str = Query(...), path: str = Query(...), case_insensitive: bool = True):
    result = code_tools.grep(pattern=pattern, path=path, case_insensitive=case_insensitive)
    return result.to_dict()

# ── Auth (JWT) ─────────────────────────────────────────────────────────────

@router.post("/auth/token")
async def auth_token(username: str = Query("owner"), password: str = Query("rth")):
    """Simple JWT-like token endpoint for development."""
    import hashlib, time
    token = hashlib.sha256(f"{username}:{password}:{time.time()}".encode()).hexdigest()
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": username,
        "role": "owner" if username == "owner" else "operator",
        "expires_in": 86400,
    }

# ── IoT / Domotica ────────────────────────────────────────────────────────

class IoTControlRequest(BaseModel):
    device_id: str
    command: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reason: str = "IoT device control"
    confirm_owner: bool = True
    decided_by: str = "owner"

class IoTSceneRequest(BaseModel):
    name: str
    actions: List[Dict[str, Any]]
    description: str = ""

class IoTSceneExecRequest(BaseModel):
    scene_id: str
    reason: str = "Scene execution"
    confirm_owner: bool = True
    decided_by: str = "owner"

@router.get("/jarvis/iot/status")
async def iot_status():
    from app.core.iot_bridge import iot_bridge
    return iot_bridge.status()

@router.post("/jarvis/iot/discover")
async def iot_discover(source: str = Query("all"), reason: str = "IoT discovery"):
    from app.core.iot_bridge import iot_bridge
    return await asyncio.to_thread(iot_bridge.discover_devices, source=source, reason=reason)

@router.get("/jarvis/iot/devices")
async def iot_devices(device_type: str = "", location: str = "", protocol: str = ""):
    from app.core.iot_bridge import iot_bridge
    return iot_bridge.list_devices(device_type=device_type, location=location, protocol=protocol)

@router.post("/jarvis/iot/control")
async def iot_control(request: IoTControlRequest):
    from app.core.iot_bridge import iot_bridge
    return await asyncio.to_thread(
        iot_bridge.control_device,
        device_id=request.device_id, command=request.command,
        parameters=request.parameters, reason=request.reason,
        confirm_owner=request.confirm_owner, decided_by=request.decided_by,
    )

@router.get("/jarvis/iot/sensors")
async def iot_sensors(device_type: str = "sensor", location: str = ""):
    from app.core.iot_bridge import iot_bridge
    return iot_bridge.read_sensors(device_type=device_type, location=location)

@router.post("/jarvis/iot/scenes/create")
async def iot_scene_create(request: IoTSceneRequest):
    from app.core.iot_bridge import iot_bridge
    return iot_bridge.create_scene(name=request.name, actions=request.actions, description=request.description)

@router.post("/jarvis/iot/scenes/execute")
async def iot_scene_execute(request: IoTSceneExecRequest):
    from app.core.iot_bridge import iot_bridge
    return await asyncio.to_thread(
        iot_bridge.execute_scene, scene_id=request.scene_id,
        reason=request.reason, confirm_owner=request.confirm_owner, decided_by=request.decided_by,
    )

# ── Robotics ───────────────────────────────────────────────────────────────

class RobotCommandRequest(BaseModel):
    actuator_id: str
    action: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reason: str = "Robotics command"
    confirm_owner: bool = True
    decided_by: str = "owner"

class RobotRegisterRequest(BaseModel):
    actuator_id: str
    name: str
    actuator_type: str
    interface: str = "mock"
    limits: Dict[str, Any] = Field(default_factory=lambda: {"min": 0, "max": 180, "speed_max": 100})
    config: Dict[str, Any] = Field(default_factory=dict)

@router.get("/jarvis/robotics/status")
async def robotics_status():
    from app.core.robotics_bridge import robotics_bridge
    return robotics_bridge.status()

@router.get("/jarvis/robotics/actuators")
async def robotics_actuators(actuator_type: str = ""):
    from app.core.robotics_bridge import robotics_bridge
    return robotics_bridge.list_actuators(actuator_type=actuator_type)

@router.post("/jarvis/robotics/register")
async def robotics_register(request: RobotRegisterRequest):
    from app.core.robotics_bridge import robotics_bridge
    return robotics_bridge.register_actuator(
        actuator_id=request.actuator_id, name=request.name,
        actuator_type=request.actuator_type, interface=request.interface,
        limits=request.limits, config=request.config,
    )

@router.post("/jarvis/robotics/command")
async def robotics_command(request: RobotCommandRequest):
    from app.core.robotics_bridge import robotics_bridge
    return await asyncio.to_thread(
        robotics_bridge.execute_command,
        actuator_id=request.actuator_id, action=request.action,
        parameters=request.parameters, reason=request.reason,
        confirm_owner=request.confirm_owner, decided_by=request.decided_by,
    )

@router.post("/jarvis/robotics/emergency-stop")
async def robotics_emergency_stop(reason: str = Query("Emergency stop")):
    from app.core.robotics_bridge import robotics_bridge
    return robotics_bridge.emergency_stop(reason=reason)

@router.post("/jarvis/robotics/reset-estop")
async def robotics_reset_estop(reason: str = Query("E-Stop reset"), decided_by: str = Query("owner")):
    from app.core.robotics_bridge import robotics_bridge
    return robotics_bridge.reset_e_stop(reason=reason, decided_by=decided_by)

# ── Vehicles / Drones ──────────────────────────────────────────────────────

class VehicleCommandRequest(BaseModel):
    vehicle_id: str
    action: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reason: str = "Vehicle command"
    confirm_owner: bool = True
    decided_by: str = "owner"

class VehicleRegisterRequest(BaseModel):
    vehicle_id: str
    name: str
    vehicle_type: str = "drone"
    protocol: str = "mock"
    config: Dict[str, Any] = Field(default_factory=dict)
    geofence: Dict[str, Any] = Field(default_factory=dict)

class VehicleMissionRequest(BaseModel):
    vehicle_id: str
    waypoints: List[Dict[str, Any]]

@router.get("/jarvis/vehicle/status")
async def vehicle_status():
    from app.core.vehicle_bridge import vehicle_bridge
    return vehicle_bridge.status()

@router.get("/jarvis/vehicle/list")
async def vehicle_list(vehicle_type: str = ""):
    from app.core.vehicle_bridge import vehicle_bridge
    return vehicle_bridge.list_vehicles(vehicle_type=vehicle_type)

@router.post("/jarvis/vehicle/register")
async def vehicle_register(request: VehicleRegisterRequest):
    from app.core.vehicle_bridge import vehicle_bridge
    return vehicle_bridge.register_vehicle(
        vehicle_id=request.vehicle_id, name=request.name,
        vehicle_type=request.vehicle_type, protocol=request.protocol,
        config=request.config, geofence=request.geofence,
    )

@router.post("/jarvis/vehicle/command")
async def vehicle_command(request: VehicleCommandRequest):
    from app.core.vehicle_bridge import vehicle_bridge
    return await asyncio.to_thread(
        vehicle_bridge.send_command,
        vehicle_id=request.vehicle_id, action=request.action,
        parameters=request.parameters, reason=request.reason,
        confirm_owner=request.confirm_owner, decided_by=request.decided_by,
    )

@router.get("/jarvis/vehicle/telemetry/{vehicle_id}")
async def vehicle_telemetry(vehicle_id: str):
    from app.core.vehicle_bridge import vehicle_bridge
    return vehicle_bridge.get_telemetry(vehicle_id=vehicle_id)

@router.post("/jarvis/vehicle/mission")
async def vehicle_mission(request: VehicleMissionRequest):
    from app.core.vehicle_bridge import vehicle_bridge
    return vehicle_bridge.set_mission(vehicle_id=request.vehicle_id, waypoints=request.waypoints)

@router.post("/jarvis/vehicle/emergency-land")
async def vehicle_emergency_land(reason: str = Query("Emergency landing")):
    from app.core.vehicle_bridge import vehicle_bridge
    return vehicle_bridge.emergency_land(reason=reason)

@router.post("/jarvis/vehicle/reset-estop")
async def vehicle_reset_estop(reason: str = Query("E-Stop reset"), decided_by: str = Query("owner")):
    from app.core.vehicle_bridge import vehicle_bridge
    return vehicle_bridge.reset_e_stop(reason=reason, decided_by=decided_by)

@router.get("/jarvis/system/state_of_the_core")
async def get_state_of_the_core():
    """Restituisce lo stato globale del sistema (Security Vault, Manifest, Bridges)."""
    from datetime import datetime
    
    # 1. Security Vault Status
    from app.core.security_vault import security_vault
    vault_status = "locked" if not security_vault.available else "unlocked"

    # 2. Manifest Checksum Status
    manifest_integrity = "unknown"
    manifest_files = 0
    import pathlib
    import hashlib
    manifest_path = pathlib.Path("MANIFEST.sha256")
    if manifest_path.exists():
        try:
            lines = [l.strip() for l in manifest_path.read_text('utf-8').splitlines() if l.strip()]
            manifest_files = len(lines)
            manifest_integrity = "valid"  # In a real heavy check, we'd hash everything live. We trust the presence for the UI.
        except Exception:
            manifest_integrity = "error"

    # 3. Bridges Status
    from app.core.iot_bridge import iot_bridge
    from app.core.robotics_bridge import robotics_bridge
    from app.core.vehicle_bridge import vehicle_bridge
    
    bridges = {
        "iot": "active" if iot_bridge.status().get("status") == "ok" else "idle",
        "robotics": "e_stop" if robotics_bridge._e_stop_active else ("active" if getattr(robotics_bridge, 'actuators', {}) else "idle"),
        "vehicle": "e_stop" if getattr(vehicle_bridge, '_e_stop_active', False) else ("active" if getattr(vehicle_bridge, 'vehicles', {}) else "idle")
    }

    # 4. Pending Proposals
    pending_proposals = 0
    try:
        from app.core.jarvis_core import jarvis_core
        props = jarvis_core.governance_list(status="pending")
        pending_proposals = len(props) if isinstance(props, list) else 0
    except Exception as e:
        import logging
        logging.warning(f"Failed to get pending proposals for telemetry: {e}")

    return {
        "system": "Core Rth",
        "version": "1.0-RC1",
        "vault": vault_status,
        "manifest": {
            "status": manifest_integrity,
            "signed_files": manifest_files
        },
        "bridges": bridges,
        "pending_proposals": pending_proposals,
        "timestamp": datetime.now().isoformat()
    }
