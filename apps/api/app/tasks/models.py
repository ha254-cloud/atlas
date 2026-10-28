from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class TaskType(StrEnum):
    REVIEW_CLAIM = "review_claim"
    UPLOAD_DOCUMENTS = "upload_documents"
    GENERATE_APPEAL = "generate_appeal"
    APPROVE_APPEAL = "approve_appeal"
    SUBMIT_APPEAL = "submit_appeal"
    CHECK_PAYER_PORTAL = "check_payer_portal"
    CALL_PAYER = "call_payer"
    UPLOAD_PAYMENT_REPORT = "upload_payment_report"
    VERIFY_PAYMENT = "verify_payment"
    RECONCILE_PAYMENT = "reconcile_payment"
    CLOSE_CLAIM = "close_claim"
    ESCALATE = "escalate"
    FOLLOW_UP = "follow_up"
    REQUEST_MISSING_DOCUMENTS = "request_missing_documents"


class TaskStatus(StrEnum):
    NEW = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class TaskDepartment(StrEnum):
    CLAIMS = "claims"
    APPEALS = "appeals"
    FINANCE = "finance"
    REVENUE_MANAGEMENT = "revenue_management"


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "priority_score >= 0 AND priority_score <= 100", name="ck_tasks_priority_score"
        ),
        UniqueConstraint(
            "organization_id", "claim_id", "task_type", "sequence", name="uq_tasks_claim_action"
        ),
        Index(
            "ix_tasks_org_assignee_status_due",
            "organization_id",
            "assigned_to",
            "status",
            "due_date",
        ),
        Index("ix_tasks_org_priority_created", "organization_id", "priority_score", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    payer_id: Mapped[int] = mapped_column(ForeignKey("payers.id"), nullable=False, index=True)
    assigned_to: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    department: Mapped[TaskDepartment] = mapped_column(SqlEnum(TaskDepartment), nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    task_type: Mapped[TaskType] = mapped_column(SqlEnum(TaskType), nullable=False, index=True)
    status: Mapped[TaskStatus] = mapped_column(
        SqlEnum(TaskStatus), nullable=False, default=TaskStatus.NEW, index=True
    )
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    claim = relationship("Claim")
    payer = relationship("Payer")
    assignee = relationship("User", foreign_keys=[assigned_to])
    creator = relationship("User", foreign_keys=[created_by])


class TaskNotification(Base, TimestampMixin):
    __tablename__ = "task_notifications"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "task_id",
            "notification_type",
            "recipient_id",
            "level",
            name="uq_task_notification_delivery",
        ),
        Index("ix_task_notifications_recipient_read", "organization_id", "recipient_id", "read_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task = relationship("Task")
    recipient = relationship("User")


class UserTaskSkill(Base, TimestampMixin):
    __tablename__ = "user_task_skills"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", "skill", name="uq_user_task_skill"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    skill: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    user = relationship("User")


class TaskActivity(Base):
    """Append-only operational audit trail for task mutations."""

    __tablename__ = "task_activities"
    __table_args__ = (
        Index("ix_task_activities_org_task_occurred", "organization_id", "task_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )

    task = relationship("Task")
    actor = relationship("User")
