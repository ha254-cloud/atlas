from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ClaimEventType(str, Enum):
    CREATED = "claim.created"
    IMPORTED = "claim.imported"
    ANALYSIS_STARTED = "claim.analysis_started"
    ANALYZED = "claim.analyzed"
    AI_ANALYSIS_FAILED = "claim.ai_analysis_failed"
    DENIAL_RECORDED = "claim.denial_recorded"
    RECOVERY_CREATED = "claim.recovery_created"
    APPEAL_GENERATED = "claim.appeal_generated"
    APPEAL_SUBMITTED = "claim.appeal_submitted"
    APPEAL_STATUS_UPDATED = "claim.appeal_status_updated"
    DOCUMENT_UPLOADED = "claim.document_uploaded"
    PAYMENT_RECEIVED = "claim.payment_received"
    STATUS_CHANGED = "claim.status_changed"
    RECOVERY_CLOSED = "claim.recovery_closed"
    DECISION_GENERATED = "claim.decision_generated"


class ClaimEvent(Base):
    """
    Immutable audit trail for every action taken on a claim.

    Records are never updated or deleted—they are only appended.
    Used for compliance, debugging, and the claim timeline UI.
    """

    __tablename__ = "claim_events"

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

    event_type: Mapped[ClaimEventType] = mapped_column(
        SqlEnum(ClaimEventType),
        nullable=False,
        index=True,
    )

    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # "metadata" is reserved by SQLAlchemy.
    # The Python attribute is renamed, but the database column
    # remains "metadata".
    event_metadata: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
