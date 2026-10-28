from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User
from app.recovery.repository import RecoveryRepository, _priority_from_score
from app.recovery.schemas import (
    BillingReadinessRead,
    FinancialAllocationRequest,
    LifecycleTransitionRequest,
    RecoveryAccountOpenRequest,
    RecoveryForecastRead,
    RecoveryLifecycleRead,
    RecoveryListResponse,
    RecoveryOpportunity,
    RecoveryPortfolioRead,
    ResponsibilityRequest,
)
from app.recovery.service import RevenueRecoveryService
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/recovery", tags=["Recovery"])


def _correlation_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _raise_lifecycle_error(db: Session, exc: ValueError) -> None:
    db.rollback()
    message = str(exc)
    if "version conflict" in message:
        status_code = 409
    elif "not found" in message.lower():
        status_code = 404
    else:
        status_code = 400
    raise HTTPException(status_code=status_code, detail=message) from exc


@router.post(
    "/lifecycle/claims/{claim_id}",
    response_model=RecoveryLifecycleRead,
    status_code=201,
)
def open_recovery_account(
    claim_id: int,
    payload: RecoveryAccountOpenRequest,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    try:
        return RevenueRecoveryService(db, organization_id).open_account(
            claim_id,
            actor_id=current_user.id,
            reason=payload.reason,
            correlation_id=_correlation_id(request),
        )
    except ValueError as exc:
        _raise_lifecycle_error(db, exc)


@router.get("/lifecycle/accounts/{account_id}", response_model=RecoveryLifecycleRead)
def get_recovery_account(
    account_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    try:
        return RevenueRecoveryService(db, organization_id).get(account_id)
    except ValueError as exc:
        _raise_lifecycle_error(db, exc)


@router.post(
    "/lifecycle/accounts/{account_id}/transitions",
    response_model=RecoveryLifecycleRead,
)
def transition_recovery_account(
    account_id: int,
    payload: LifecycleTransitionRequest,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    try:
        return RevenueRecoveryService(db, organization_id).transition(
            account_id,
            payload,
            actor_id=current_user.id,
            correlation_id=_correlation_id(request),
        )
    except ValueError as exc:
        _raise_lifecycle_error(db, exc)


@router.post(
    "/lifecycle/accounts/{account_id}/allocations",
    response_model=RecoveryLifecycleRead,
)
def allocate_recovery_balance(
    account_id: int,
    payload: FinancialAllocationRequest,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return RevenueRecoveryService(db, organization_id).allocate(
            account_id,
            payload,
            actor_id=current_user.id,
            correlation_id=_correlation_id(request),
        )
    except ValueError as exc:
        _raise_lifecycle_error(db, exc)


@router.post(
    "/lifecycle/accounts/{account_id}/responsibility",
    response_model=RecoveryLifecycleRead,
)
def assign_recovery_responsibility(
    account_id: int,
    payload: ResponsibilityRequest,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    try:
        return RevenueRecoveryService(db, organization_id).assign(
            account_id,
            payload,
            actor_id=current_user.id,
            correlation_id=_correlation_id(request),
        )
    except ValueError as exc:
        _raise_lifecycle_error(db, exc)


@router.post(
    "/lifecycle/accounts/{account_id}/synchronize",
    response_model=RecoveryLifecycleRead,
)
def synchronize_recovery_account(
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    try:
        return RevenueRecoveryService(db, organization_id).synchronize(
            account_id,
            actor_id=current_user.id,
            correlation_id=_correlation_id(request),
        )
    except ValueError as exc:
        _raise_lifecycle_error(db, exc)


@router.get("/lifecycle/portfolio", response_model=RecoveryPortfolioRead)
def recovery_portfolio(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return RevenueRecoveryService(db, organization_id).portfolio()


@router.get("/lifecycle/forecast", response_model=RecoveryForecastRead)
def recovery_forecast(
    horizon_days: int = Query(default=90, ge=7, le=365),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return RevenueRecoveryService(db, organization_id).forecast(horizon_days)


@router.get("/lifecycle/billing-readiness", response_model=BillingReadinessRead)
def recovery_billing_readiness(
    period_start: date,
    period_end: date,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.MANAGE_BILLING)),
):
    try:
        return RevenueRecoveryService(db, organization_id).billing_readiness(
            period_start, period_end
        )
    except ValueError as exc:
        _raise_lifecycle_error(db, exc)


@router.get("", response_model=RecoveryListResponse)
def list_opportunities(
    status: str | None = Query(
        None, description="Filter by status: open, in_progress, appealed, recovered, closed"
    ),
    payer_id: int | None = Query(None),
    priority: str | None = Query(None, description="critical | high | medium | low"),
    search: str | None = Query(None, description="Search by claim number"),
    sort_by: str = Query(
        "recovery_score", description="recovery_score | estimated_value | created_at"
    ),
    sort_dir: str = Query("desc", description="asc | desc"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    """
    Paginated, filterable recovery work queue.
    Sorted by recovery score descending by default — highest impact first.
    """
    repo = RecoveryRepository(db, organization_id)
    rows, total = repo.list_opportunities(
        status=status,
        payer_id=payer_id,
        priority=priority,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )

    items = []
    for rc, claim in rows:
        balance = float(claim.billed_amount) - float(claim.paid_amount)
        items.append(
            RecoveryOpportunity(
                id=rc.id,
                claim_id=claim.id,
                claim_number=claim.claim_number,
                payer_id=claim.payer_id,
                patient_id=claim.patient_id,
                recovery_score=float(rc.recovery_score),
                estimated_value=float(rc.estimated_value),
                status=rc.status.value,
                priority=_priority_from_score(rc.recovery_score),
                recommendation=rc.recommendation,
                billed_amount=float(claim.billed_amount),
                paid_amount=float(claim.paid_amount),
                balance=balance,
                created_at=rc.created_at,
            )
        )

    return RecoveryListResponse(items=items, total=total, limit=limit, offset=offset)


@router.patch("/{recovery_id}/status")
def update_status(
    recovery_id: int,
    body: dict,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    _current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    status = body.get("status")
    if not status:
        raise HTTPException(status_code=400, detail="status is required")

    repo = RecoveryRepository(db, organization_id)
    rc = repo.update_status(recovery_id, status)
    if rc is None:
        raise HTTPException(status_code=404, detail="Recovery case not found")

    return {"id": rc.id, "status": rc.status.value}
