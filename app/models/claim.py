from typing import Optional
from sqlalchemy import String, Integer, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.db.base import TimestampMixin
from app.db.database import Base


class Claim(Base, TimestampMixin):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    payer_id: Mapped[int] = mapped_column(ForeignKey("payers.id"), nullable=False)

    provider_npi: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    claim_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    amount_billed: Mapped[Optional[float]] = mapped_column(Numeric(12,2), nullable=True)
    amount_paid: Mapped[Optional[float]] = mapped_column(Numeric(12,2), nullable=True)

    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    denial_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    submission_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_update: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    claim_lines = relationship("ClaimLine", back_populates="claim", cascade="all, delete-orphan")
    denials = relationship("Denial", back_populates="claim", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="claim", cascade="all, delete-orphan")

    patient = relationship("Patient", back_populates="claims")
    payer = relationship("Payer")
