from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class ClaimDiagnosis(Base, TimestampMixin):
    """A single ICD-10 diagnosis code attached to a claim."""

    __tablename__ = "claim_diagnoses"

    id: Mapped[int] = mapped_column(primary_key=True)

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"),
        nullable=False,
        index=True,
    )

    icd_code: Mapped[str] = mapped_column(
        String(20),
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    claim = relationship("Claim", back_populates="diagnoses")
