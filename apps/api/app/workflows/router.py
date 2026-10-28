from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.claim_workflow import ClaimWorkflow
from app.models.user import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.workflows.escalation import run_escalation_sweep
from app.workflows.schemas import (
    ClaimWorkflowRead,
    TransitionRequest,
    WorkQueueItem,
    WorkQueueResponse,
    WorkQueueSummary,
)
from app.workflows.service import WorkflowService
from app.workflows.sla import is_overdue
from app.workflows.transitions import WorkflowTransitionError

router = APIRouter(prefix="/workflows", tags=["Workflows"])


def _to_read(workflow: ClaimWorkflow) -> ClaimWorkflowRead:
    data = ClaimWorkflowRead.model_validate(workflow)
    data.is_overdue = is_overdue(workflow.due_at)
    return data


@router.get("/queue", response_model=WorkQueueResponse)
def get_work_queue(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    """Role-specific work queue — what should this user work on next,
    ordered by priority score (highest first)."""
    label, workflows = WorkflowService(db, organization_id).queue_for_user(
        current_user.role,
        current_user.id,
    )
    now = datetime.utcnow()
    items = [
        WorkQueueItem(
            claim_id=w.claim_id,
            claim_number=w.claim.claim_number if w.claim else None,
            assigned_user_id=w.claim.assigned_user_id if w.claim else None,
            state=w.state,
            priority_score=w.priority_score,
            recovery_probability=w.claim.recovery_probability if w.claim else None,
            due_at=w.due_at,
            is_overdue=is_overdue(w.due_at, now),
            billed_amount=w.claim.billed_amount if w.claim else None,
        )
        for w in workflows
    ]
    return WorkQueueResponse(label=label, count=len(items), items=items)


@router.get("/queue/summary", response_model=WorkQueueSummary)
def get_work_queue_summary(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_USERS)),
) -> WorkQueueSummary:
    return WorkQueueSummary(**WorkflowService(db, organization_id).queue_summary())


@router.get("/overdue", response_model=list[ClaimWorkflowRead])
def get_overdue_workflows(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    """Every claim currently past its stage's SLA deadline, for this org."""
    workflows = WorkflowService(db, organization_id).list_overdue()
    return [_to_read(w) for w in workflows]


@router.post("/escalate-sweep")
def trigger_escalation_sweep(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_USERS)),
):
    """Manually run the escalation sweep for this org (no Celery Beat
    schedule is configured yet to run this automatically)."""
    escalated = run_escalation_sweep(db, organization_id)
    return {"escalated_count": len(escalated), "claim_ids": [w.claim_id for w in escalated]}


@router.get("/{claim_id}", response_model=ClaimWorkflowRead)
def get_claim_workflow(
    claim_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    workflow = WorkflowService(db, organization_id).get_workflow(claim_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="No workflow found for this claim")
    return _to_read(workflow)


@router.post("/{claim_id}/transition", response_model=ClaimWorkflowRead)
def transition_claim_workflow(
    claim_id: int,
    payload: TransitionRequest,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.EDIT_CLAIMS)),
):
    try:
        workflow = WorkflowService(db, organization_id).transition(
            claim_id,
            payload.to_state,
            actor_id=current_user.id,
            reason=payload.reason,
            force=payload.force,
        )
    except WorkflowTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _to_read(workflow)
