from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.db.base import TimestampMixin
from app.db.database import Base


class Appeal(Base, TimestampMixin):
    __tablename__ = "appeals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    submitted_on: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    claim = relationship("Claim")
