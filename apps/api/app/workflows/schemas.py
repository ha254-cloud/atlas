from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.claim_workflow import ClaimWorkflowState


class ClaimWorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    state: ClaimWorkflowState
    previous_state: ClaimWorkflowState | None = None
    state_entered_at: datetime
    due_at: datetime | None = None
    is_overdue: bool = False
    priority_score: Decimal | None = None
    escalated: bool = False


class TransitionRequest(BaseModel):
    to_state: ClaimWorkflowState
    reason: str | None = None
    # Administrative override — allows closing a claim early from any
    # non-terminal state, bypassing the normal forward-only transition graph.
    force: bool = False


class WorkQueueItem(BaseModel):
    claim_id: int
    claim_number: str | None = None
    assigned_user_id: int | None = None
    state: ClaimWorkflowState
    priority_score: Decimal | None = None
    recovery_probability: Decimal | None = None
    due_at: datetime | None = None
    is_overdue: bool = False
    billed_amount: Decimal | None = None


class WorkQueueResponse(BaseModel):
    label: str
    count: int
    items: list[WorkQueueItem]


class WorkQueueSummary(BaseModel):
    assigned: int
    pending: int
    completed: int
    overdue: int
