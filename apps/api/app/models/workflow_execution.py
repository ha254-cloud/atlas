from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class WorkflowExecutionStatus(str, Enum):
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING = "waiting"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkflowExecution(Base, TimestampMixin):
    """
    One row per (workflow_definition, claim) run — the Workflow Engine's
    "process instance". `context` accumulates every completed step's
    output (e.g. `context["ai_analysis"]` after an AI_ANALYSIS step runs)
    so later CONDITION steps, and the API response, can read prior
    results.
    """

    __tablename__ = "workflow_executions"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "trigger_event_id",
            name="uq_workflow_executions_workflow_trigger_event",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_definitions.id"), nullable=False, index=True
    )
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("claims.id"), nullable=True, index=True)
    trigger_event: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    trigger_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    trigger_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[WorkflowExecutionStatus] = mapped_column(
        SqlEnum(WorkflowExecutionStatus, name="workflowexecutionstatus"),
        default=WorkflowExecutionStatus.RUNNING,
        nullable=False,
        index=True,
    )

    current_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_steps.id"), nullable=True
    )

    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow = relationship("WorkflowDefinition")
    claim = relationship("Claim")
    step_executions = relationship(
        "WorkflowStepExecution",
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="WorkflowStepExecution.id",
    )


class WorkflowStepExecutionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    WAITING = "waiting"
    SKIPPED = "skipped"


class WorkflowStepExecution(Base, TimestampMixin):
    """Audit-trail row for one attempt of one step within one execution —
    the "Workflow History" the Sprint 5 spec calls for (mirrors the
    AgentExecutionLog pattern introduced for Sprint 4)."""

    __tablename__ = "workflow_step_executions"

    id: Mapped[int] = mapped_column(primary_key=True)

    execution_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_executions.id"), nullable=False, index=True
    )
    step_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_steps.id"), nullable=False, index=True
    )

    status: Mapped[WorkflowStepExecutionStatus] = mapped_column(
        SqlEnum(WorkflowStepExecutionStatus, name="workflowstepexecutionstatus"),
        nullable=False,
    )
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    execution = relationship("WorkflowExecution", back_populates="step_executions")
    step = relationship("WorkflowStep")
