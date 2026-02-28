"""
Model control plane endpoints (providers, routing, presets, chat routing simulation).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from app.core.model_control_plane import model_control_plane

router = APIRouter()


class ProviderModelRow(BaseModel):
    model_id: str
    label: Optional[str] = None
    enabled: bool = True
    cost_tier: Optional[str] = None
    latency_tier: Optional[str] = None
    strengths: List[str] = Field(default_factory=list)
    task_classes: List[str] = Field(default_factory=list)
    supports_vision: bool = False
    supports_tools: bool = True
    supports_reasoning: bool = True
    context_tokens: int = 0
    tags: List[str] = Field(default_factory=list)
    notes: str = ""


class ProviderUpsertRequest(BaseModel):
    provider_id: str
    label: Optional[str] = None
    provider_type: str = "openai"
    enabled: bool = True
    local_endpoint: Optional[bool] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    notes: str = ""
    models: List[Any] = Field(default_factory=list)
    reason: str = "Update model provider configuration"
    confirm_owner: bool = True
    decided_by: str = "owner"


class ProviderDeleteRequest(BaseModel):
    provider_id: str
    reason: str = "Delete model provider configuration"
    confirm_owner: bool = True
    decided_by: str = "owner"


class ProviderTestRequest(BaseModel):
    provider_id: Optional[str] = None
    provider: Optional[Dict[str, Any]] = None
    timeout_sec: float = 2.5


class RoutingPolicySetRequest(BaseModel):
    policy: Dict[str, Any]
    reason: str = "Update model routing policy"
    confirm_owner: bool = True
    decided_by: str = "owner"


class PresetApplyRequest(BaseModel):
    preset_id: str
    reason: str = "Apply model routing preset"
    confirm_owner: bool = True
    decided_by: str = "owner"


class RouteExplainRequest(BaseModel):
    task_class: str = "chat_general"
    message: Optional[str] = None
    prompt: Optional[str] = None
    privacy_mode: Optional[str] = None
    max_cost_tier: Optional[str] = None
    difficulty: str = "normal"
    reasoning_level: Optional[str] = None
    require_vision: bool = False
    require_tools: bool = False
    token_estimate: Optional[int] = None


class ChatSimulateRequest(BaseModel):
    message: str
    task_class: str = "chat_general"
    privacy_mode: Optional[str] = None
    difficulty: str = "normal"
    reasoning_level: Optional[str] = None


class ChatRunRequest(BaseModel):
    message: str
    task_class: str = "chat_general"
    privacy_mode: Optional[str] = None
    difficulty: str = "normal"
    reasoning_level: Optional[str] = None
    require_vision: bool = False
    require_tools: bool = False
    max_tokens: int = 800
    temperature: float = 0.2
    timeout_sec: float = 60.0
    allow_fallbacks: bool = True
    system_prompt: Optional[str] = None
    confirm_owner: bool = True
    decided_by: str = "owner"
    reason: str = "UI/API live chat execution"


class ModelsReloadRequest(BaseModel):
    reselect_path: bool = False


class VillagePlanRequest(BaseModel):
    prompt: str
    mode: str = "brainstorm"
    privacy_mode: str = "allow_cloud"
    budget_cap: float = 10.0
    roles: List[str] = Field(default_factory=list)


class VillageRunRequest(BaseModel):
    prompt: str
    mode: str = "brainstorm"
    privacy_mode: str = "allow_cloud"
    budget_cap: float = 10.0
    roles: List[str] = Field(default_factory=list)
    allow_budget_overrun: bool = True
    max_roles: int = 8
    role_max_tokens: int = 700
    synthesis_max_tokens: int = 1000
    timeout_sec: float = 120.0
    per_role_timeout_sec: float = 60.0
    confirm_owner: bool = True
    decided_by: str = "owner"
    reason: str = "UI/API AI Village live execution"


@router.get("/status")
async def models_status():
    return model_control_plane.status()


@router.get("/providers")
async def providers_list():
    return model_control_plane.list_providers()


@router.post("/providers/upsert")
async def providers_upsert(request: ProviderUpsertRequest):
    return model_control_plane.upsert_provider(
        payload=request.dict(exclude={"reason", "confirm_owner", "decided_by"}),
        reason=request.reason,
        confirm_owner=request.confirm_owner,
        decided_by=request.decided_by,
    )


@router.post("/providers/delete")
async def providers_delete(request: ProviderDeleteRequest):
    return model_control_plane.delete_provider(
        provider_id=request.provider_id,
        reason=request.reason,
        confirm_owner=request.confirm_owner,
        decided_by=request.decided_by,
    )


@router.post("/providers/test")
async def providers_test(request: ProviderTestRequest):
    return model_control_plane.test_provider(
        provider_id=request.provider_id or "",
        payload=request.provider,
        timeout_sec=request.timeout_sec,
    )


@router.get("/catalog")
async def models_catalog():
    return model_control_plane.get_catalog()


@router.get("/routing-policy")
async def routing_policy_get():
    return model_control_plane.get_routing_policy()


@router.post("/routing-policy")
async def routing_policy_set(request: RoutingPolicySetRequest):
    return model_control_plane.set_routing_policy(
        payload=request.policy,
        reason=request.reason,
        confirm_owner=request.confirm_owner,
        decided_by=request.decided_by,
    )


@router.post("/presets/apply")
async def preset_apply(request: PresetApplyRequest):
    return model_control_plane.apply_preset(
        preset_id=request.preset_id,
        reason=request.reason,
        confirm_owner=request.confirm_owner,
        decided_by=request.decided_by,
    )


@router.post("/route/explain")
async def route_explain(request: RouteExplainRequest):
    return model_control_plane.route_explain(request.dict())


@router.post("/chat/simulate")
async def chat_simulate(request: ChatSimulateRequest):
    return model_control_plane.chat_simulate(request.dict())


@router.post("/chat/run")
async def chat_run(request: ChatRunRequest):
    return model_control_plane.chat_execute(request.dict())


@router.post("/reload")
async def models_reload(request: ModelsReloadRequest):
    return model_control_plane.reload_state(reselect_path=request.reselect_path)


@router.post("/village/plan")
async def village_plan(request: VillagePlanRequest):
    try:
        return model_control_plane.village_plan(request.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/village/run")
async def village_run(request: VillageRunRequest):
    try:
        return model_control_plane.village_run(request.dict())
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
