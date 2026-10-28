from typing import Optional
from sqlalchemy import Numeric, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.db.base import TimestampMixin
from app.db.database import Base


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False)
    amount: Mapped[Optional[float]] = mapped_column(Numeric(12,2), nullable=True)
    paid_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    claim = relationship("Claim", back_populates="payments")
