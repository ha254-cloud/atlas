from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.mcp.auth import create_api_key
from app.mcp.dependencies import get_mcp_context
from app.mcp.registry import registry
from app.mcp.schemas.requests import (
    AnalyzeClaimRequest,
    CheckStatusRequest,
    ClassifyDenialRequest,
    EstimateRecoveryRequest,
    GenerateAppealRequest,
    ReconcilePaymentRequest,
    SyncClaimsRequest,
)
from app.mcp.schemas.responses import (
    APIKeyCreateResponse,
    APIKeyResponse,
    MCPResponse,
)
from app.mcp.tools.analyze_claim import AnalyzeClaimTool
from app.mcp.tools.check_status import CheckStatusTool
from app.mcp.tools.classify_denial import ClassifyDenialTool
from app.mcp.tools.estimate_recovery import EstimateRecoveryTool
from app.mcp.tools.generate_appeal import GenerateAppealTool
from app.mcp.tools.reconcile_payment import ReconcilePaymentTool
from app.mcp.tools.sync_claims import SyncClaimsTool
from app.models.api_key import APIKey
from app.models.user import User
from app.security.dependencies import get_current_user

# ---------------------------------------------------------------------------
# Register all tools once at import time.
# Adding a new tool in future = instantiate + register — nothing else changes.
# ---------------------------------------------------------------------------
registry.register(AnalyzeClaimTool())
registry.register(EstimateRecoveryTool())
registry.register(GenerateAppealTool())
registry.register(ClassifyDenialTool())
registry.register(CheckStatusTool())
registry.register(SyncClaimsTool())
registry.register(ReconcilePaymentTool())

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/mcp", tags=["MCP"])


# --- Tool discovery --------------------------------------------------------


@router.get("/tools", summary="List available MCP tools")
def list_tools() -> dict[str, Any]:
    return {"tools": registry.list_tools()}


# --- Tool execution --------------------------------------------------------


@router.post("/tools/analyze_claim", response_model=MCPResponse)
async def analyze_claim(
    payload: AnalyzeClaimRequest,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_mcp_context),
):
    return await registry.get("analyze_claim").execute(
        db=db,
        organization_id=api_key.organization_id,
        claim_id=payload.claim_id,
    )


@router.post("/tools/estimate_recovery", response_model=MCPResponse)
async def estimate_recovery(
    payload: EstimateRecoveryRequest,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_mcp_context),
):
    return await registry.get("estimate_recovery").execute(
        db=db,
        organization_id=api_key.organization_id,
        claim_id=payload.claim_id,
        denial_probability=payload.denial_probability,
        claim_age_days=payload.claim_age_days,
    )


@router.post("/tools/generate_appeal", response_model=MCPResponse)
async def generate_appeal(
    payload: GenerateAppealRequest,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_mcp_context),
):
    return await registry.get("generate_appeal").execute(
        db=db,
        organization_id=api_key.organization_id,
        claim_id=payload.claim_id,
    )


@router.post("/tools/classify_denial", response_model=MCPResponse)
async def classify_denial(
    payload: ClassifyDenialRequest,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_mcp_context),
):
    return await registry.get("classify_denial").execute(
        db=db,
        organization_id=api_key.organization_id,
        claim_id=payload.claim_id,
    )


@router.post("/tools/check_status", response_model=MCPResponse)
async def check_status(
    payload: CheckStatusRequest,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_mcp_context),
):
    return await registry.get("check_status").execute(
        db=db,
        organization_id=api_key.organization_id,
        claim_id=payload.claim_id,
    )


@router.post("/tools/sync_claims", response_model=MCPResponse)
async def sync_claims(
    payload: SyncClaimsRequest,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_mcp_context),
):
    return await registry.get("sync_claims").execute(
        db=db,
        organization_id=api_key.organization_id,
        connector=payload.connector,
        since_days=payload.since_days,
    )


@router.post("/tools/reconcile_payment", response_model=MCPResponse)
async def reconcile_payment(
    payload: ReconcilePaymentRequest,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(get_mcp_context),
):
    return await registry.get("reconcile_payment").execute(
        db=db,
        organization_id=api_key.organization_id,
        claim_id=payload.claim_id,
        payment_amount=payload.payment_amount,
        payment_reference=payload.payment_reference,
    )


# --- API Key management (requires JWT auth, not MCP key) ------------------


class APIKeyCreateRequest(BaseModel):
    name: str
    expires_at: datetime | None = None


@router.post(
    "/keys",
    response_model=APIKeyCreateResponse,
    summary="Create an MCP API key for your organization",
)
def create_key(
    payload: APIKeyCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
):
    api_key_row, raw_key = create_api_key(
        db=db,
        organization_id=organization_id,
        name=payload.name,
        expires_at=payload.expires_at,
    )
    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.API_KEY_CREATED,
        entity="api_key",
        entity_id=api_key_row.id,
        ip_address=request.client.host if request.client else None,
        metadata={"name": api_key_row.name},
    )
    db.commit()
    return APIKeyCreateResponse(
        id=api_key_row.id,
        name=api_key_row.name,
        raw_key=raw_key,
        key_prefix=api_key_row.key_prefix,
    )


@router.get(
    "/keys",
    response_model=list[APIKeyResponse],
    summary="List API keys for your organization",
)
def list_keys(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
):
    return db.query(APIKey).filter(APIKey.organization_id == organization_id).all()


@router.delete(
    "/keys/{key_id}",
    summary="Revoke an API key",
)
def revoke_key(
    key_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(get_current_user),
):
    api_key = (
        db.query(APIKey)
        .filter(
            APIKey.id == key_id,
            APIKey.organization_id == organization_id,
        )
        .first()
    )

    if api_key is None:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False
    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.API_KEY_REVOKED,
        entity="api_key",
        entity_id=api_key.id,
        ip_address=request.client.host if request.client else None,
        metadata={"name": api_key.name},
    )
    db.commit()
    return {"revoked": True}
