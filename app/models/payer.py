from typing import Optional
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class Payer(Base, TimestampMixin):
    __tablename__ = "payers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    payer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    contacts = relationship("PayerContact", back_populates="payer", cascade="all, delete-orphan")
