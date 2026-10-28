from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import app.integrations.mock  # noqa: F401
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.integrations.registry import submission_registry
from app.models.submission import SubmissionStatus
from app.models.user import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.submissions.schemas import (
    SubmissionRead,
    SubmissionRequest,
)
from app.submissions.service import SubmissionService

router = APIRouter(tags=["Submission Engine"])


@router.get("/submission-connectors", response_model=list[str])
def list_submission_connectors(
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    return submission_registry.list_providers()


@router.post("/appeals/{appeal_id}/submissions", response_model=SubmissionRead)
async def submit_appeal(
    appeal_id: int,
    payload: SubmissionRequest,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.SUBMIT_APPEALS)),
):
    try:
        return await SubmissionService(db, organization_id).submit(
            appeal_id,
            connector=payload.connector,
            integration_id=payload.integration_id,
            submitted_by=current_user.id,
            connector_options=payload.connector_options,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/submissions", response_model=list[SubmissionRead])
def list_submissions(
    status: SubmissionStatus | None = None,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    return SubmissionService(db, organization_id).list(status)


@router.get("/submissions/{submission_id}", response_model=SubmissionRead)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    try:
        return SubmissionService(db, organization_id).get(submission_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/submissions/{submission_id}/refresh", response_model=SubmissionRead)
async def refresh_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.SUBMIT_APPEALS)),
):
    try:
        return await SubmissionService(db, organization_id).status(submission_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/submissions/{submission_id}/cancel", response_model=SubmissionRead)
async def cancel_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.SUBMIT_APPEALS)),
):
    try:
        return await SubmissionService(db, organization_id).cancel(submission_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
