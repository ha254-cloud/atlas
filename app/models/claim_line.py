from typing import Optional
from sqlalchemy import String, Integer, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class ClaimLine(Base, TimestampMixin):
    __tablename__ = "claim_lines"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    procedure_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    charge_amount: Mapped[Optional[float]] = mapped_column(Numeric(12,2), nullable=True)

    claim = relationship("Claim", back_populates="claim_lines")
