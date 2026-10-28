from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base
from app.models.invoice import Invoice, InvoiceLine, InvoiceStatus


class RecoveryFeeSchedule(Base, TimestampMixin):
    __tablename__ = "recovery_fee_schedules"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "effective_from",
            name="uq_recovery_fee_schedules_org_effective_from",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    fee_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    vat_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0")
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False)
    dispute_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)


__all__ = ["Invoice", "InvoiceLine", "InvoiceStatus", "RecoveryFeeSchedule"]
