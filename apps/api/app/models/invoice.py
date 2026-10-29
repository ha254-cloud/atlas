from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    DDL,
    JSON,
    CheckConstraint,
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


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    VOID = "void"


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "period_start",
            "period_end",
            name="uq_invoices_organization_period",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        SqlEnum(InvoiceStatus), default=InvoiceStatus.DRAFT, nullable=False, index=True
    )
    total_recovered_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_fee_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    vat_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    billing_name: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_email: Mapped[str] = mapped_column(String(255), nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lines = relationship(
        "InvoiceLine",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.id",
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id"), nullable=False, index=True
    )
    recovery_id: Mapped[int] = mapped_column(
        ForeignKey("recoveries.id"), nullable=False, unique=True, index=True
    )
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"), nullable=False, index=True
    )
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"), nullable=False, index=True
    )
    attribution_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("recovery_attribution_versions.id"),
        nullable=True,
        unique=True,
        index=True,
    )
    recovered_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fee_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)

    invoice = relationship("Invoice", back_populates="lines")
    recovery = relationship("Recovery", back_populates="invoice_line")
    payment = relationship("Payment")
    claim = relationship("Claim")
    attribution_version = relationship("RecoveryAttributionVersion")


class InvoiceCreditNote(Base):
    """Immutable credit evidence created from an invoiced reversal or refund."""

    __tablename__ = "invoice_credit_notes"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "payment_allocation_id",
            name="uq_invoice_credit_notes_org_allocation",
        ),
        UniqueConstraint(
            "organization_id",
            "attribution_resolution_id",
            name="uq_invoice_credit_notes_org_attribution_resolution",
        ),
        CheckConstraint(
            "(payment_allocation_id IS NOT NULL) <> "
            "(attribution_resolution_id IS NOT NULL)",
            name="ck_invoice_credit_notes_single_source",
        ),
        UniqueConstraint(
            "organization_id",
            "credit_note_number",
            name="uq_invoice_credit_notes_org_number",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id"), nullable=False, index=True
    )
    invoice_line_id: Mapped[int] = mapped_column(
        ForeignKey("invoice_lines.id"), nullable=False, index=True
    )
    payment_allocation_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_allocations.id"), nullable=True, index=True
    )
    attribution_resolution_id: Mapped[int | None] = mapped_column(
        ForeignKey("recovery_attribution_dispute_resolutions.id"),
        nullable=True,
        index=True,
    )
    credit_note_number: Mapped[str] = mapped_column(String(50), nullable=False)
    adjustment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    recovered_adjustment_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    fee_adjustment_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    vat_adjustment_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    total_credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    issued_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    invoice = relationship("Invoice")
    invoice_line = relationship("InvoiceLine")
    payment_allocation = relationship("PaymentAllocation")
    attribution_resolution = relationship("RecoveryAttributionDisputeResolution")


class InvoiceReconciliationRun(Base):
    """Immutable independent recomputation of one recovery invoice."""

    __tablename__ = "invoice_reconciliation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_payment_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    expected_recovered_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    actual_recovered_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    expected_fee_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    actual_fee_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    expected_vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    actual_vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    credit_note_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    expected_net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    actual_net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discrepancy_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    discrepancy_count: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    run_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    invoice = relationship("Invoice")


event.listen(
    InvoiceCreditNote.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER invoice_credit_notes_no_update BEFORE UPDATE ON "
        "invoice_credit_notes BEGIN SELECT RAISE(ABORT, "
        "'invoice credit notes are immutable'); END"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    InvoiceReconciliationRun.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER invoice_reconciliation_runs_no_update BEFORE UPDATE ON "
        "invoice_reconciliation_runs BEGIN SELECT RAISE(ABORT, "
        "'invoice reconciliation runs are immutable'); END"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    InvoiceReconciliationRun.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER invoice_reconciliation_runs_no_delete BEFORE DELETE ON "
        "invoice_reconciliation_runs BEGIN SELECT RAISE(ABORT, "
        "'invoice reconciliation runs are immutable'); END"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    InvoiceCreditNote.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER invoice_credit_notes_no_delete BEFORE DELETE ON "
        "invoice_credit_notes BEGIN SELECT RAISE(ABORT, "
        "'invoice credit notes are immutable'); END"
    ).execute_if(dialect="sqlite"),
)
