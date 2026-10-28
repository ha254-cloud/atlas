"""
Integration management API — the backend for the Integration Health
Dashboard and connect/sync/disconnect actions.

This wires up infrastructure that already existed (IntegrationManager,
IntegrationRegistry, the Integration model, token encryption, the Celery
sync job) but had no HTTP surface at all — organizations could not list,
create, sync, or disconnect an integration through the API.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.integrations.exceptions import ConnectorNotFoundError, IntegrationError
from app.integrations.manager import IntegrationManager
from app.integrations.registry import registry
from app.integrations.schemas import (
    IntegrationCreate,
    IntegrationCredentialRotate,
    IntegrationCredentialVersionRead,
    IntegrationHealth,
    IntegrationRead,
)
from app.integrations.service import IntegrationService
from app.models.integration import Integration, IntegrationStatus
from app.models.user import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/integrations", tags=["Integrations"])


@router.get("/providers", response_model=list[str])
def list_providers():
    """Every connector Atlas can currently talk to — drives the
    "connect a new integration" picker on the frontend."""
    return registry.list_providers()


@router.get("", response_model=list[IntegrationRead])
def list_integrations(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
):
    """Every integration this organization has configured — the data
    source for the Integration Health Dashboard."""
    return (
        db.query(Integration)
        .filter(Integration.organization_id == organization_id)
        .order_by(Integration.created_at.desc())
        .all()
    )


@router.post("", response_model=IntegrationRead, status_code=201)
def create_integration(
    payload: IntegrationCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    """Connect a new integration. Tokens (if supplied) are encrypted
    before storage and never returned in any response."""
    if payload.provider.lower() not in registry.list_providers():
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown provider '{payload.provider}'. "
                f"Supported providers: {registry.list_providers()}"
            ),
        )

    try:
        return IntegrationService(db, organization_id).create(
            provider=payload.provider,
            settings=payload.settings,
            credentials=payload.credential_contract(),
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
    except (IntegrationError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{integration_id}", response_model=IntegrationRead)
def get_integration(
    integration_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
):
    row = (
        db.query(Integration)
        .filter(Integration.id == integration_id, Integration.organization_id == organization_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    return row


@router.get("/{integration_id}/health", response_model=IntegrationHealth)
async def check_integration_health(
    integration_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
):
    """Live connection check — powers the "Connected ✅ / Authentication
    Expired, Reconnect" state on the health dashboard."""
    row = (
        db.query(Integration)
        .filter(Integration.id == integration_id, Integration.organization_id == organization_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    try:
        result = await IntegrationManager(db).health_check(
            integration_id,
            organization_id,
            correlation_id=getattr(request.state, "request_id", None),
        )
    except (IntegrationError, ConnectorNotFoundError) as exc:
        result = {"connected": False, "latency_ms": None}
        row.last_error = str(exc)
        db.commit()

    return IntegrationHealth(
        connected=bool(result.get("connected", False)),
        latency_ms=result.get("latency_ms"),
        provider=row.provider,
        status=row.status,
        last_sync_at=row.last_sync_at,
        last_error=row.last_error,
    )


@router.post(
    "/{integration_id}/credentials/rotate",
    response_model=IntegrationCredentialVersionRead,
)
def rotate_integration_credentials(
    integration_id: int,
    payload: IntegrationCredentialRotate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    try:
        return IntegrationService(db, organization_id).rotate_credentials(
            integration_id,
            payload.credentials,
            actor_id=current_user.id,
            reason=payload.reason,
            correlation_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as exc:
        db.rollback()
        status_code = 404 if str(exc) == "Integration not found" else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except IntegrationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{integration_id}/credentials/versions",
    response_model=list[IntegrationCredentialVersionRead],
)
def list_integration_credential_versions(
    integration_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    try:
        return IntegrationService(db, organization_id).list_credential_versions(integration_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{integration_id}/sync", status_code=202)
def trigger_sync(
    integration_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    """Manually trigger a sync now, rather than waiting for the next
    scheduled run. Runs on the Celery worker; this endpoint only enqueues."""
    row = (
        db.query(Integration)
        .filter(Integration.id == integration_id, Integration.organization_id == organization_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    from app.workers.tasks import sync_integration

    sync_integration.delay(
        integration_id,
        organization_id,
        getattr(request.state, "request_id", None),
    )

    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.INTEGRATION_SYNC_TRIGGERED,
        entity="integration",
        entity_id=row.id,
        ip_address=request.client.host if request.client else None,
        metadata={
            "provider": row.provider,
            "correlation_id": getattr(request.state, "request_id", None),
        },
    )
    db.commit()

    return {"status": "queued", "integration_id": integration_id}


@router.post("/{integration_id}/disconnect", response_model=IntegrationRead)
def disconnect_integration(
    integration_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    """Disconnect an integration — clears stored credentials but keeps the
    row (and its sync history) so it can be reconnected later."""
    row = (
        db.query(Integration)
        .filter(Integration.id == integration_id, Integration.organization_id == organization_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    row.status = IntegrationStatus.DISCONNECTED
    row.encrypted_access_token = None
    row.encrypted_refresh_token = None

    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.INTEGRATION_DISCONNECTED,
        entity="integration",
        entity_id=row.id,
        ip_address=request.client.host if request.client else None,
        metadata={"provider": row.provider},
    )
    db.commit()
    db.refresh(row)
    return row
