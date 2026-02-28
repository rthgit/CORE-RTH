"""
Public plugin ecosystem endpoints (registry + manifest validation + compatibility matrix).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from app.core.plugin_registry_public import plugin_registry_public

router = APIRouter()


class PluginManifestValidateRequest(BaseModel):
    manifest: Dict[str, Any]


class PluginManifestRegisterRequest(BaseModel):
    manifest: Dict[str, Any]
    reason: str = "Register public plugin manifest"
    confirm_owner: bool = True
    decided_by: str = "owner"


class PluginManifestDeleteRequest(BaseModel):
    plugin_id: str
    reason: str = "Delete public plugin manifest"
    confirm_owner: bool = True
    decided_by: str = "owner"


class PluginHealthcheckRequest(BaseModel):
    plugin_id: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None
    timeout_sec: float = Field(default=2.5, ge=0.2, le=15.0)
    reason: str = "Run plugin healthcheck"
    confirm_owner: bool = True
    decided_by: str = "owner"


class PluginHealthcheckBatchRequest(BaseModel):
    plugin_ids: Optional[List[str]] = None
    priority_only: bool = False
    category: Optional[str] = None
    pack: Optional[str] = None
    tier: Optional[str] = None
    install_state: Optional[str] = None
    enabled_only: bool = False
    include_not_configured: bool = False
    limit: int = Field(default=20, ge=1, le=100)
    timeout_sec: float = Field(default=2.5, ge=0.2, le=15.0)
    reason: str = "Run plugin healthcheck batch"
    confirm_owner: bool = True
    decided_by: str = "owner"


class PluginStateSetRequest(BaseModel):
    plugin_id: str
    enabled: Optional[bool] = None
    install_state: Optional[str] = None
    reason: str = "Update plugin install state"
    confirm_owner: bool = True
    decided_by: str = "owner"


class PluginDriverActionRequest(BaseModel):
    plugin_id: str
    action: str  # install|enable|disable
    timeout_sec: float = Field(default=6.0, ge=0.2, le=120.0)
    reason: str = "Run plugin driver action"
    confirm_owner: bool = True
    decided_by: str = "owner"


@router.get("/status")
async def plugins_status():
    return plugin_registry_public.status()


@router.get("/catalog")
async def plugins_catalog():
    return plugin_registry_public.catalog()


@router.get("/compatibility-matrix")
async def plugins_compatibility_matrix():
    return plugin_registry_public.compatibility_matrix()


@router.get("/schema")
async def plugins_schema():
    return plugin_registry_public.schema_document()


@router.post("/validate")
async def plugins_validate(request: PluginManifestValidateRequest):
    return plugin_registry_public.validate_manifest(request.manifest)


@router.post("/register")
async def plugins_register(request: PluginManifestRegisterRequest):
    try:
        return plugin_registry_public.register_manifest(
            payload=request.manifest,
            reason=request.reason,
            confirm_owner=request.confirm_owner,
            decided_by=request.decided_by,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/delete")
async def plugins_delete(request: PluginManifestDeleteRequest):
    try:
        return plugin_registry_public.delete_manifest(
            plugin_id=request.plugin_id,
            reason=request.reason,
            confirm_owner=request.confirm_owner,
            decided_by=request.decided_by,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/healthcheck")
async def plugins_healthcheck(request: PluginHealthcheckRequest):
    try:
        return plugin_registry_public.healthcheck_plugin(
            plugin_id=request.plugin_id or "",
            manifest=request.manifest,
            timeout_sec=request.timeout_sec,
            reason=request.reason,
            confirm_owner=request.confirm_owner,
            decided_by=request.decided_by,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/healthcheck/batch")
async def plugins_healthcheck_batch(request: PluginHealthcheckBatchRequest):
    try:
        return plugin_registry_public.healthcheck_batch(
            plugin_ids=request.plugin_ids,
            priority_only=request.priority_only,
            category=request.category or "",
            pack=request.pack or "",
            tier=request.tier or "",
            install_state=request.install_state or "",
            enabled_only=request.enabled_only,
            include_not_configured=request.include_not_configured,
            limit=request.limit,
            timeout_sec=request.timeout_sec,
            reason=request.reason,
            confirm_owner=request.confirm_owner,
            decided_by=request.decided_by,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/state/set")
async def plugins_state_set(request: PluginStateSetRequest):
    try:
        return plugin_registry_public.set_plugin_state(
            plugin_id=request.plugin_id,
            enabled=request.enabled,
            install_state=request.install_state,
            reason=request.reason,
            confirm_owner=request.confirm_owner,
            decided_by=request.decided_by,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/driver/action")
async def plugins_driver_action(request: PluginDriverActionRequest):
    try:
        return plugin_registry_public.driver_action(
            plugin_id=request.plugin_id,
            action=request.action,
            timeout_sec=request.timeout_sec,
            reason=request.reason,
            confirm_owner=request.confirm_owner,
            decided_by=request.decided_by,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
