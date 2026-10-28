from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class ClaimValidationIssue(Base, TimestampMixin):
    """
    A non-blocking finding from the pre-submission ValidationEngine
    (e.g. missing modifier, overpayment, timely filing risk). Blocking
    ("error" severity) issues reject the claim outright and are never
    persisted here — only rows the claim actually made it past.
    """

    __tablename__ = "claim_validation_issues"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(String(50))

    severity: Mapped[str] = mapped_column(String(20))

    field: Mapped[str] = mapped_column(String(100))

    message: Mapped[str] = mapped_column(String(500))

    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    claim = relationship("Claim", back_populates="validation_issues")
