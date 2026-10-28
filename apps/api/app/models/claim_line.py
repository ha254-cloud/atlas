from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class ClaimLine(Base, TimestampMixin):
    """A single billed procedure on a claim (one row per CPT/HCPCS line item)."""

    __tablename__ = "claim_lines"

    id: Mapped[int] = mapped_column(primary_key=True)

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"),
        nullable=False,
        index=True,
    )

    cpt_code: Mapped[str] = mapped_column(
        String(20),
    )

    modifier: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    units: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    charge_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
    )

    allowed_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    paid_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    claim = relationship("Claim", back_populates="claim_lines")
