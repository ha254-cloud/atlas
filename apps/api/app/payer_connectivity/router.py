from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.core.config import settings
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.appeal_submission import AppealSubmissionStatus
from app.models.user import User
from app.payer_connectivity.analytics import PayerConnectivityAnalytics
from app.payer_connectivity.registry import registry
from app.payer_connectivity.schemas import (
    AppealSubmissionDetail,
    AppealSubmissionRead,
    ElectronicSubmissionRequest,
)
from app.payer_connectivity.service import PayerSubmissionService
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/payer-connectivity", tags=["Payer Connectivity"])


@router.get("/connectors", response_model=list[str])
def list_connectors(
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    connectors = registry.list()
    if settings.test_connectors_allowed:
        return connectors
    return [name for name in connectors if name not in {"mock", "sandbox"}]


@router.post("/appeals/{appeal_id}/submit", response_model=AppealSubmissionRead)
async def submit_appeal_electronically(
    appeal_id: int,
    payload: ElectronicSubmissionRequest,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.SUBMIT_APPEALS)),
):
    try:
        submission = await PayerSubmissionService(db, organization_id).submit(
            appeal_id=appeal_id,
            connector=payload.connector,
            integration_id=payload.integration_id,
            submitted_by=current_user.id,
            connector_options=payload.connector_options,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    AuditService(db).log(
        organization_id=organization_id,
        user_id=current_user.id,
        action=AuditAction.APPEAL_SUBMITTED,
        entity="appeal_submission",
        entity_id=submission.id,
        ip_address=request.client.host if request.client else None,
        metadata={"connector": submission.connector, "appeal_id": appeal_id},
    )
    db.commit()
    return submission


@router.get("/submissions", response_model=list[AppealSubmissionRead])
def list_submissions(
    status: AppealSubmissionStatus | None = None,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    return PayerSubmissionService(db, organization_id).list(status)


@router.get("/submissions/{submission_id}", response_model=AppealSubmissionDetail)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    try:
        return PayerSubmissionService(db, organization_id).get(submission_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/submissions/{submission_id}/refresh", response_model=AppealSubmissionRead)
async def refresh_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.SUBMIT_APPEALS)),
):
    try:
        return await PayerSubmissionService(db, organization_id).refresh(submission_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/analytics/executive-summary")
def payer_connectivity_summary(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)),
):
    return PayerConnectivityAnalytics(db, organization_id).executive_summary()
