from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User
from app.payers.monitoring import PayerMonitoringService
from app.payers.policies import PayerPolicyService
from app.payers.schemas import (
    PayerCreate,
    PayerHealthCheckResult,
    PayerRead,
    PayerRejection,
    PayerUpdate,
    PolicySourceCreate,
    PolicySourceRead,
    PolicySourceRejection,
)
from app.payers.service import PayerService
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/payers", tags=["Payer Registry"])


@router.get("/{payer_id}/policy-sources", response_model=list[PolicySourceRead])
def list_policy_sources(
    payer_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    try:
        return PayerPolicyService(db, organization_id).list(payer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{payer_id}/policy-sources", response_model=PolicySourceRead, status_code=201)
def create_policy_source(
    payer_id: int,
    payload: PolicySourceCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    try:
        return PayerPolicyService(db, organization_id).create_version(
            payer_id,
            payload,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as exc:
        db.rollback()
        status_code = 404 if str(exc) == "Payer not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post(
    "/{payer_id}/policy-sources/{source_id}/submit-for-approval",
    response_model=PolicySourceRead,
)
def submit_policy_source(
    payer_id: int,
    source_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    try:
        return PayerPolicyService(db, organization_id).submit_for_approval(
            payer_id,
            source_id,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as exc:
        db.rollback()
        status_code = 404 if str(exc) in {"Payer not found", "Policy source not found"} else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post(
    "/{payer_id}/policy-sources/{source_id}/approve",
    response_model=PolicySourceRead,
)
def approve_policy_source(
    payer_id: int,
    source_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.APPROVE_PAYERS)),
):
    try:
        return PayerPolicyService(db, organization_id).approve(
            payer_id,
            source_id,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as exc:
        db.rollback()
        status_code = 404 if str(exc) in {"Payer not found", "Policy source not found"} else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post(
    "/{payer_id}/policy-sources/{source_id}/reject",
    response_model=PolicySourceRead,
)
def reject_policy_source(
    payer_id: int,
    source_id: int,
    payload: PolicySourceRejection,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.APPROVE_PAYERS)),
):
    try:
        return PayerPolicyService(db, organization_id).reject(
            payer_id,
            source_id,
            reason=payload.reason,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as exc:
        db.rollback()
        status_code = 404 if str(exc) in {"Payer not found", "Policy source not found"} else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("", response_model=list[PayerRead])
def list_payers(
    active_only: bool = True,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    return PayerService(db, organization_id).list(active_only=active_only)


@router.get("/{payer_id}", response_model=PayerRead)
def get_payer(
    payer_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    try:
        return PayerService(db, organization_id).get(payer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=PayerRead, status_code=201)
def create_payer(
    payload: PayerCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    try:
        return PayerService(db, organization_id).create(
            payload,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{payer_id}", response_model=PayerRead)
def update_payer(
    payer_id: int,
    payload: PayerUpdate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    try:
        return PayerService(db, organization_id).update(
            payer_id,
            payload,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as exc:
        db.rollback()
        status_code = 404 if str(exc) == "Payer not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{payer_id}/submit-for-approval", response_model=PayerRead)
def submit_payer_for_approval(
    payer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    try:
        return PayerService(db, organization_id).submit_for_approval(
            payer_id,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as exc:
        db.rollback()
        status_code = 404 if str(exc) == "Payer not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{payer_id}/approve", response_model=PayerRead)
def approve_payer(
    payer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.APPROVE_PAYERS)),
):
    try:
        return PayerService(db, organization_id).approve(
            payer_id,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as exc:
        db.rollback()
        status_code = 404 if str(exc) == "Payer not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{payer_id}/reject", response_model=PayerRead)
def reject_payer(
    payer_id: int,
    payload: PayerRejection,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.APPROVE_PAYERS)),
):
    try:
        return PayerService(db, organization_id).reject(
            payer_id,
            reason=payload.reason,
            actor_id=current_user.id,
            correlation_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
    except ValueError as exc:
        db.rollback()
        status_code = 404 if str(exc) == "Payer not found" else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/{payer_id}/health-check", response_model=PayerHealthCheckResult)
async def check_payer_health(
    payer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    """Live connectivity check for the payer's bound connector, or
    "not_configured" for manual/portal/email payers with no integration."""
    try:
        outcome = await PayerMonitoringService(db, organization_id).check_health(
            payer_id,
            correlation_id=getattr(request.state, "request_id", None),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    payer = outcome.payer
    return PayerHealthCheckResult(
        payer_id=payer.id,
        status=payer.last_health_status,
        checked_at=payer.last_health_checked_at,
        error=payer.last_health_error,
        failure_count=payer.health_check_failure_count,
        latency_ms=outcome.latency_ms,
    )
