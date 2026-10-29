from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class Recovery(Base, TimestampMixin):
    __tablename__ = "recoveries"
    __table_args__ = (
        UniqueConstraint(
            "payment_id",
            "claim_id",
            name="uq_recoveries_payment_claim",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"), nullable=False, index=True
    )
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("appeal_submissions.id"), nullable=True, index=True
    )
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"), nullable=False, index=True
    )
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    recovered_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    recovery_percentage: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    atlas_fee_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    atlas_fee_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    verified_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    claim = relationship("Claim")
    submission = relationship("Submission")
    payment = relationship("Payment", back_populates="recoveries")
    invoice_line = relationship("InvoiceLine", back_populates="recovery", uselist=False)
    attribution_versions = relationship(
        "RecoveryAttributionVersion",
        order_by="RecoveryAttributionVersion.version",
        foreign_keys="RecoveryAttributionVersion.recovery_id",
    )

    @property
    def current_attribution(self):
        return self.attribution_versions[-1] if self.attribution_versions else None
