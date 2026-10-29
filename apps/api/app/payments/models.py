from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


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
    recovery = relationship("Recovery", back_populates="payment", uselist=False)
