from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    DDL,
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
    recovered_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fee_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)

    invoice = relationship("Invoice", back_populates="lines")
    recovery = relationship("Recovery", back_populates="invoice_line")
    payment = relationship("Payment")
    claim = relationship("Claim")


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
    payment_allocation_id: Mapped[int] = mapped_column(
        ForeignKey("payment_allocations.id"), nullable=False, index=True
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
    InvoiceCreditNote.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER invoice_credit_notes_no_delete BEFORE DELETE ON "
        "invoice_credit_notes BEGIN SELECT RAISE(ABORT, "
        "'invoice credit notes are immutable'); END"
    ).execute_if(dialect="sqlite"),
)
