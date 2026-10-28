from typing import Optional
from sqlalchemy import String, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dob: Mapped[Optional[str]] = mapped_column(Date, nullable=True)
    mrn: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    claims = relationship("Claim", back_populates="patient")
