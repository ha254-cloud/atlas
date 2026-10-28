from enum import Enum

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class DenialType(str, Enum):
    ELIGIBILITY = "eligibility"
    CODING = "coding"
    DUPLICATE = "duplicate"
    PRIOR_AUTH = "prior_authorization"
    TIMELY_FILING = "timely_filing"
    MEDICAL_NECESSITY = "medical_necessity"
    DOCUMENTATION = "documentation"
    MODIFIER_ERROR = "modifier_error"
    NON_COVERED_SERVICE = "non_covered_service"
    COORDINATION_OF_BENEFITS = "coordination_of_benefits"
    OTHER = "other"


class Denial(Base, TimestampMixin):
    __tablename__ = "denials"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"),
        nullable=False,
    )

    denial_code: Mapped[str] = mapped_column(String(30))

    denial_type: Mapped[DenialType] = mapped_column(SqlEnum(DenialType))

    description: Mapped[str] = mapped_column(String(1000))

    claim = relationship(
        "Claim",
        back_populates="denials",
    )
