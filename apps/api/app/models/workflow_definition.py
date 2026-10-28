from enum import Enum

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class WorkflowStepType(str, Enum):
    AI_ANALYSIS = "ai_analysis"
    GENERATE_APPEAL = "generate_appeal"
    CONDITION = "condition"
    HUMAN_APPROVAL = "human_approval"
    WAIT = "wait"
    EMAIL = "email"
    NOTIFICATION = "notification"
    PUBLISH_EVENT = "publish_event"
    ASSIGN_USER = "assign_user"
    UPLOAD_DOCUMENT = "upload_document"
    CALL_API = "call_api"
    LOOP = "loop"
    END = "end"


class WorkflowDefinition(Base, TimestampMixin):
    """
    An organization-authored, configurable business-process automation —
    the Sprint 5 "Workflow Engine". Deliberately separate from
    `ClaimWorkflow` (the existing hardcoded per-claim SLA/state tracker in
    `app/workflows/`, which keeps working unchanged): that system answers
    "what stage is this claim in", while this one lets each organization
    define its own ordered sequence of automated actions (call the AI
    orchestrator, generate an appeal, branch on a condition, wait, ask a
    human for approval, notify someone, etc.) instead of Atlas hardcoding
    one process for everyone.
    """

    __tablename__ = "workflow_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional domain event that starts this graph automatically. Null keeps
    # the definition manual/API-triggered only.
    trigger_event: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    trigger_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    steps = relationship(
        "WorkflowStep",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.step_order",
    )


class WorkflowStep(Base, TimestampMixin):
    __tablename__ = "workflow_steps"

    id: Mapped[int] = mapped_column(primary_key=True)

    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_definitions.id"),
        nullable=False,
        index=True,
    )

    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[WorkflowStepType] = mapped_column(
        SqlEnum(WorkflowStepType, name="workflowsteptype"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Step-type-specific settings — e.g. {"expression": "..."} for
    # CONDITION, {"duration_days": 30} for WAIT, {"to_email": "...",
    # "subject": "..."} for EMAIL, {"user_id": 5} for ASSIGN_USER. See
    # app/workflow_engine/step_handlers.py for exactly what each handler
    # reads from this field.
    configuration: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Success path — also the TRUE branch for CONDITION steps. Null means
    # "workflow completes" once this step succeeds (equivalent to an
    # explicit END step).
    next_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_steps.id"),
        nullable=True,
    )
    # Failure / retries-exhausted path — also the FALSE branch for
    # CONDITION steps. Null means "fail the whole execution" if this step
    # fails.
    failure_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_steps.id"),
        nullable=True,
    )

    max_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    workflow = relationship("WorkflowDefinition", back_populates="steps")
