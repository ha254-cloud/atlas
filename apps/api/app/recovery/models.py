from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base
from app.recovery.opportunities import Priority


class RecoveryLifecycleState(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    PARTIALLY_PAID = "partially_paid"
    OUTSTANDING = "outstanding_balance"
    APPEAL = "appeal"
    RECOVERED = "recovered"
    WRITTEN_OFF = "written_off"
    CLOSED = "closed"


class RecoveryEventType(StrEnum):
    ACCOUNT_OPENED = "account_opened"
    STATE_TRANSITIONED = "state_transitioned"
    PAYMENT_CONFIRMED = "payment_confirmed"
    CONTRACT_ADJUSTMENT = "contract_adjustment"
    WRITE_OFF_APPROVED = "write_off_approved"
    WRITE_OFF_REVERSED = "write_off_reversed"
    RESPONSIBILITY_ASSIGNED = "responsibility_assigned"
    ACCOUNT_CLOSED = "account_closed"
    ACCOUNT_REOPENED = "account_reopened"


class RecoveryAccount(Base, TimestampMixin):
    __tablename__ = "recovery_accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "claim_id", name="uq_recovery_account_org_claim"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    state: Mapped[RecoveryLifecycleState] = mapped_column(
        SqlEnum(RecoveryLifecycleState), nullable=False, default=RecoveryLifecycleState.DRAFT
    )
    assigned_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    claim = relationship("Claim")
    events = relationship(
        "RecoveryLifecycleEvent",
        back_populates="account",
        order_by="RecoveryLifecycleEvent.sequence",
    )


class RecoveryLifecycleEvent(Base, TimestampMixin):
    __tablename__ = "recovery_lifecycle_events"
    __table_args__ = (
        UniqueConstraint("account_id", "sequence", name="uq_recovery_lifecycle_event_sequence"),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_recovery_lifecycle_event_idempotency"
        ),
        CheckConstraint("amount IS NULL OR amount >= 0", name="ck_recovery_lifecycle_event_amount"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("recovery_accounts.id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[RecoveryEventType] = mapped_column(
        SqlEnum(RecoveryEventType), nullable=False, index=True
    )
    from_state: Mapped[RecoveryLifecycleState | None] = mapped_column(
        SqlEnum(RecoveryLifecycleState), nullable=True
    )
    to_state: Mapped[RecoveryLifecycleState] = mapped_column(
        SqlEnum(RecoveryLifecycleState), nullable=False
    )
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False, default="user")
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    account = relationship("RecoveryAccount", back_populates="events")


@dataclass
class RecoveryOpportunity:
    claim_id: int
    score: Decimal
    estimated_recovery: Decimal
    balance: Decimal
    priority: Priority
    next_action: str | None = None
