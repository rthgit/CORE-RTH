"""
Secrets API (local secret store v0).
Returns metadata/masked values only.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os

from app.core.permissions import permission_gate, Capability, RiskLevel
from app.core.secret_store import secret_store

router = APIRouter()


class SecretSetRequest(BaseModel):
    name: str
    value: str
    reason: str = "Store local secret"
    confirm_owner: bool = True
    decided_by: str = "owner"


class SecretDeleteRequest(BaseModel):
    name: str
    reason: str = "Delete local secret"
    confirm_owner: bool = True
    decided_by: str = "owner"


class SecretRotateRequest(BaseModel):
    name: str
    new_value: str
    keep_previous: bool = True
    reason: str = "Rotate local secret"
    confirm_owner: bool = True
    decided_by: str = "owner"


class SecretResolveRequest(BaseModel):
    env_name: str
    secret_name: str
    default: str = ""


class SecretExportRequest(BaseModel):
    include_values: bool = False
    reason: str = "Export secret store bundle"
    confirm_owner: bool = True
    decided_by: str = "owner"


class SecretImportRequest(BaseModel):
    bundle: dict
    import_values: bool = True
    on_conflict: str = "overwrite"
    reason: str = "Import secret store bundle"
    confirm_owner: bool = True
    decided_by: str = "owner"


class SecretAuditRequest(BaseModel):
    limit: int = 100


@router.get("/status")
async def secrets_status():
    return secret_store.status()


@router.post("/set")
async def secrets_set(request: SecretSetRequest):
    req = permission_gate.propose(
        capability=Capability.FILESYSTEM_WRITE,
        action="secret_store_set",
        scope={"secret_name": request.name, "target_path": secret_store.status().get("meta_path")},
        reason=request.reason,
        risk=RiskLevel.HIGH,
    )
    out = {"proposal": req.to_dict()}
    if not request.confirm_owner:
        out["status"] = "proposal_only"
        return out
    dec = permission_gate.approve(req.request_id, decided_by=request.decided_by)
    out["decision"] = dec.to_dict()
    if dec.decision.value != "approved":
        out["status"] = "denied"
        return out
    out["result"] = secret_store.set(request.name, request.value, actor=request.decided_by, reason=request.reason)
    out["status"] = out["result"].get("status", "ok")
    return out


@router.post("/delete")
async def secrets_delete(request: SecretDeleteRequest):
    req = permission_gate.propose(
        capability=Capability.FILESYSTEM_WRITE,
        action="secret_store_delete",
        scope={"secret_name": request.name, "target_path": secret_store.status().get("meta_path")},
        reason=request.reason,
        risk=RiskLevel.HIGH,
    )
    out = {"proposal": req.to_dict()}
    if not request.confirm_owner:
        out["status"] = "proposal_only"
        return out
    dec = permission_gate.approve(req.request_id, decided_by=request.decided_by)
    out["decision"] = dec.to_dict()
    if dec.decision.value != "approved":
        out["status"] = "denied"
        return out
    out["result"] = secret_store.delete(request.name, actor=request.decided_by, reason=request.reason)
    out["status"] = out["result"].get("status", "ok")
    return out


@router.post("/rotate")
async def secrets_rotate(request: SecretRotateRequest):
    req = permission_gate.propose(
        capability=Capability.FILESYSTEM_WRITE,
        action="secret_store_rotate",
        scope={"secret_name": request.name, "target_path": secret_store.status().get("meta_path"), "keep_previous": bool(request.keep_previous)},
        reason=request.reason,
        risk=RiskLevel.HIGH,
    )
    out = {"proposal": req.to_dict()}
    if not request.confirm_owner:
        out["status"] = "proposal_only"
        return out
    dec = permission_gate.approve(req.request_id, decided_by=request.decided_by)
    out["decision"] = dec.to_dict()
    if dec.decision.value != "approved":
        out["status"] = "denied"
        return out
    out["result"] = secret_store.rotate(request.name, request.new_value, keep_previous=request.keep_previous, actor=request.decided_by, reason=request.reason)
    out["status"] = out["result"].get("status", "ok")
    return out


@router.post("/resolve")
async def secrets_resolve(request: SecretResolveRequest):
    # Returns presence/masked only, not plaintext.
    value = secret_store.resolve_env(request.env_name, request.secret_name, default=request.default)
    return {
        "status": "ok",
        "env_name": request.env_name,
        "secret_name": request.secret_name,
        "resolved": bool(value),
        "source": "env" if request.env_name and bool(os.getenv(request.env_name)) else ("secret_store" if secret_store.has(request.secret_name) else "default"),
        "masked": (("*" * 8) if value else ""),
    }


@router.post("/export")
async def secrets_export(request: SecretExportRequest):
    # Treat export as high-risk filesystem read because it can include secret material (encrypted payload).
    req = permission_gate.propose(
        capability=Capability.FILESYSTEM_READ,
        action="secret_store_export",
        scope={"target_path": secret_store.status().get("meta_path"), "include_values": bool(request.include_values)},
        reason=request.reason,
        risk=RiskLevel.HIGH if request.include_values else RiskLevel.MEDIUM,
    )
    out = {"proposal": req.to_dict()}
    if not request.confirm_owner:
        out["status"] = "proposal_only"
        return out
    dec = permission_gate.approve(req.request_id, decided_by=request.decided_by)
    out["decision"] = dec.to_dict()
    if dec.decision.value != "approved":
        out["status"] = "denied"
        return out
    out["result"] = secret_store.export_bundle(include_values=request.include_values, actor=request.decided_by, reason=request.reason)
    out["status"] = out["result"].get("status", "ok")
    return out


@router.post("/import")
async def secrets_import(request: SecretImportRequest):
    req = permission_gate.propose(
        capability=Capability.FILESYSTEM_WRITE,
        action="secret_store_import",
        scope={"target_path": secret_store.status().get("meta_path"), "import_values": bool(request.import_values), "on_conflict": request.on_conflict},
        reason=request.reason,
        risk=RiskLevel.HIGH if request.import_values else RiskLevel.MEDIUM,
    )
    out = {"proposal": req.to_dict()}
    if not request.confirm_owner:
        out["status"] = "proposal_only"
        return out
    dec = permission_gate.approve(req.request_id, decided_by=request.decided_by)
    out["decision"] = dec.to_dict()
    if dec.decision.value != "approved":
        out["status"] = "denied"
        return out
    out["result"] = secret_store.import_bundle(
        request.bundle,
        import_values=request.import_values,
        on_conflict=request.on_conflict,
        actor=request.decided_by,
        reason=request.reason,
    )
    out["status"] = out["result"].get("status", "ok")
    return out


@router.get("/audit")
async def secrets_audit(limit: int = 100):
    return secret_store.audit(limit=limit)
