from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.db.base import TimestampMixin
from app.db.database import Base


class Denial(Base, TimestampMixin):
    __tablename__ = "denials"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    denied_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    claim = relationship("Claim", back_populates="denials")
