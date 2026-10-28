from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.recovery_case import AIReviewDecision
from app.models.user import User
from app.recovery_workspace.schemas import WorkspaceResponse
from app.recovery_workspace.service import RecoveryWorkspaceService
from app.security.dependencies import require_permission
from app.security.permissions import Permission

router = APIRouter(prefix="/recovery-workspace", tags=["Recovery Workspace"])


@router.get("", response_model=WorkspaceResponse)
def get_workspace(
    priority: str | None = Query(None, description="critical | high | medium | low"),
    status: str | None = Query(None, description="open | in_progress | appealed"),
    search: str | None = Query(None),
    limit: int = Query(100, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
) -> WorkspaceResponse:
    """
    Primary endpoint for the Recovery Workspace screen.
    Returns summary metrics + ordered work queue in one call.
    """
    status_filter = [status] if status else None
    return RecoveryWorkspaceService(db, organization_id).get_workspace(
        status_filter=status_filter,
        priority_filter=priority,
        search=search,
        limit=limit,
        offset=offset,
    )


class AIReviewRequest(BaseModel):
    recovery_case_id: int
    decision: str  # accepted | edited | rejected
    reason: str | None = None


@router.post("/ai-review")
def submit_ai_review(
    payload: AIReviewRequest,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    """
    Record the specialist's decision on an AI recommendation.
    Accepted / Edited / Rejected — this feedback becomes ML training data.
    """
    from app.models.recovery_case import RecoveryCase

    rc = (
        db.query(RecoveryCase)
        .filter(
            RecoveryCase.id == payload.recovery_case_id,
            RecoveryCase.organization_id == organization_id,
        )
        .first()
    )

    if rc is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Recovery case not found")

    rc.ai_review = AIReviewDecision(payload.decision)
    rc.ai_review_reason = payload.reason
    db.commit()

    return {"id": rc.id, "ai_review": rc.ai_review.value}


class OutcomeRequest(BaseModel):
    recovery_case_id: int
    recovered_amount: float
    atlas_fee_pct: float = 5.0  # default 5%


@router.post("/record-outcome")
def record_outcome(
    payload: OutcomeRequest,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Direct recovery outcome recording is disabled. Ingest or reconcile "
            "payment evidence through /api/v1/payments, then verify the generated recovery."
        ),
    )
