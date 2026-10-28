from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class RecoveryStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    APPEALED = "appealed"
    RECOVERED = "recovered"
    CLOSED = "closed"


class AIReviewDecision(str, Enum):
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


class RecoveryCase(Base, TimestampMixin):
    __tablename__ = "recovery_cases"

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

    recovery_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )

    estimated_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    status: Mapped[RecoveryStatus] = mapped_column(
        SqlEnum(RecoveryStatus),
        default=RecoveryStatus.OPEN,
        nullable=False,
    )

    recommendation: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    # --- Human review of AI recommendation ---
    ai_review: Mapped[AIReviewDecision | None] = mapped_column(
        SqlEnum(AIReviewDecision),
        nullable=True,
    )

    ai_review_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # --- Outcome tracking (success fee model) ---
    recovered_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    atlas_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    payment_received_at: Mapped[object | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    invoice_generated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    claim = relationship("Claim", back_populates="recovery_cases")
