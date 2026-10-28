from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.db.base import TimestampMixin
from app.db.database import Base


class RecoveryCase(Base, TimestampMixin):
    __tablename__ = "recovery_cases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    priority: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    claim = relationship("Claim")
    assigned_to = relationship("User")
