from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class ClaimWorkflowState(str, Enum):
    IMPORTED = "imported"
    VALIDATED = "validated"
    ANALYZED = "analyzed"
    WAITING_FOR_DOCUMENTS = "waiting_for_documents"
    READY_FOR_APPEAL = "ready_for_appeal"
    APPEAL_GENERATED = "appeal_generated"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    PENDING_PAYER = "pending_payer"
    RECOVERED = "recovered"
    CLOSED = "closed"


# States considered "done" for the purposes of work queues / overdue sweeps.
TERMINAL_STATES = {ClaimWorkflowState.RECOVERED, ClaimWorkflowState.CLOSED}


class ClaimWorkflow(Base, TimestampMixin):
    """
    The single source of truth for where a claim sits in Atlas' end-to-end
    recovery lifecycle (the Recovery Workflow Engine). One row per claim
    (one-to-one).

    This is deliberately separate from — and orchestrates, rather than
    replaces — the narrower existing sub-lifecycles: `Claim.status` (a
    loose, informal billing-facing field), `Appeal.status` (the appeal
    draft/review/submit state machine), and `RecoveryCase.status`
    (recovery outcome tracking). Those keep working exactly as before;
    this table adds the missing "what stage of the overall recovery
    process is this claim in, and is it overdue" view on top.
    """

    __tablename__ = "claim_workflows"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    state: Mapped[ClaimWorkflowState] = mapped_column(
        SqlEnum(ClaimWorkflowState, name="claimworkflowstate"),
        default=ClaimWorkflowState.IMPORTED,
        nullable=False,
        index=True,
    )

    previous_state: Mapped[ClaimWorkflowState | None] = mapped_column(
        SqlEnum(ClaimWorkflowState, name="claimworkflowstate"),
        nullable=True,
    )

    state_entered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    # SLA deadline for the *current* state — recomputed on every transition
    # from workflows/sla.py's SLA_MINUTES map. Null for terminal states.
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    priority_score: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    # Set once an overdue stage has triggered an escalation notification,
    # so the sweep doesn't re-notify on every run.
    escalated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    claim = relationship("Claim")
