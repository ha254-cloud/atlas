from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    DDL,
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base

LEGACY_PAYMENT_TERMS_DAYS = 30


class PaymentSource(StrEnum):
    ERA_835 = "era_835"
    API = "api"
    SFTP = "sftp"
    CSV = "csv"
    EXCEL = "excel"
    PORTAL_EXPORT = "portal_export"
    EMAIL_REPORT = "email_report"
    MANUAL = "manual"
    WEBHOOK = "webhook"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    DENIED = "denied"
    VOIDED = "voided"
    REVERSED = "reversed"


class PaymentAllocationType(StrEnum):
    ALLOCATION = "allocation"
    REVERSAL = "reversal"
    REFUND = "refund"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "source",
            "payment_reference",
            name="uq_payments_org_source_reference",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    claim_id: Mapped[int | None] = mapped_column(
        ForeignKey("claims.id"), nullable=True, index=True
    )
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("appeal_submissions.id"), nullable=True, index=True
    )
    payer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    adjustment_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal(0)
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=LEGACY_PAYMENT_TERMS_DAYS,
    )
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[PaymentStatus] = mapped_column(
        SqlEnum(PaymentStatus), nullable=False, index=True
    )
    source: Mapped[PaymentSource] = mapped_column(
        SqlEnum(PaymentSource), nullable=False, index=True
    )
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    matched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    matched_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    matching_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    matching_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    correlation_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True
    )

    claim = relationship("Claim")
    submission = relationship("Submission")
    matched_by = relationship("User", foreign_keys=[matched_by_id])
    recoveries = relationship("Recovery", back_populates="payment")
    settlement_evidence = relationship(
        "PaymentSettlementEvidence",
        back_populates="payment",
        order_by="PaymentSettlementEvidence.id",
    )
    allocations = relationship(
        "PaymentAllocation",
        back_populates="payment",
        foreign_keys="PaymentAllocation.payment_id",
        order_by="PaymentAllocation.id",
    )

    @property
    def recovery(self):
        return self.recoveries[0] if self.recoveries else None

    @property
    def allocated_amount(self) -> Decimal:
        return sum(
            (
                allocation.amount
                if allocation.allocation_type == PaymentAllocationType.ALLOCATION
                else -allocation.amount
                for allocation in self.allocations
            ),
            Decimal("0"),
        )

    @property
    def unallocated_amount(self) -> Decimal:
        originally_allocated = sum(
            (
                allocation.amount
                for allocation in self.allocations
                if allocation.allocation_type == PaymentAllocationType.ALLOCATION
            ),
            Decimal("0"),
        )
        return max(self.paid_amount - originally_allocated, Decimal("0"))


class PaymentSettlementEvidence(Base):
    """Append-only evidence that a payer settlement was received."""

    __tablename__ = "payment_settlement_evidence"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_payment_settlement_evidence_org_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"), nullable=False, index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    settlement_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    payment = relationship("Payment", back_populates="settlement_evidence")


class PaymentAllocation(Base):
    """Append-only allocation or compensating reversal/refund."""

    __tablename__ = "payment_allocations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_payment_allocations_org_idempotency",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"), nullable=False, index=True
    )
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"), nullable=False, index=True
    )
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("appeal_submissions.id"), nullable=True, index=True
    )
    parent_allocation_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_allocations.id"), nullable=True, index=True
    )
    allocation_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    item_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    payment = relationship(
        "Payment",
        back_populates="allocations",
        foreign_keys=[payment_id],
    )
    claim = relationship("Claim")
    submission = relationship("Submission")
    parent_allocation = relationship(
        "PaymentAllocation",
        remote_side=[id],
        foreign_keys=[parent_allocation_id],
    )


for _table in (
    PaymentSettlementEvidence.__table__,
    PaymentAllocation.__table__,
):
    event.listen(
        _table,
        "after_create",
        DDL(
            f"CREATE TRIGGER {_table.name}_no_update BEFORE UPDATE ON {_table.name} "
            "BEGIN SELECT RAISE(ABORT, 'payment ledgers are immutable'); END"
        ).execute_if(dialect="sqlite"),
    )
    event.listen(
        _table,
        "after_create",
        DDL(
            f"CREATE TRIGGER {_table.name}_no_delete BEFORE DELETE ON {_table.name} "
            "BEGIN SELECT RAISE(ABORT, 'payment ledgers are immutable'); END"
        ).execute_if(dialect="sqlite"),
    )
