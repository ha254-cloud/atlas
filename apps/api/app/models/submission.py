from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.db.base import TimestampMixin
from app.db.database import Base


class SubmissionStatus(StrEnum):
    PENDING = "pending"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    DENIED = "denied"
    PAID = "paid"
    FAILED = "failed"

    # Compatibility states used by the existing payer-connectivity API.
    UNDER_REVIEW = "under_review"
    ADDITIONAL_INFO_REQUIRED = "additional_info_required"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Submission(Base, TimestampMixin):
    __tablename__ = "appeal_submissions"
    __table_args__ = (
        UniqueConstraint("appeal_id", name="uq_appeal_submissions_appeal_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    claim_id: Mapped[int | None] = mapped_column(
        ForeignKey("claims.id"), nullable=True, index=True
    )
    appeal_id: Mapped[int] = mapped_column(
        ForeignKey("appeals.id"), nullable=False, index=True
    )
    integration_id: Mapped[int | None] = mapped_column(
        ForeignKey("integrations.id"), nullable=True, index=True
    )
    connector: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_tracking_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    external_reference = synonym("external_tracking_id")
    status: Mapped[SubmissionStatus] = mapped_column(
        SqlEnum(SubmissionStatus, name="appealsubmissionstatus"),
        default=SubmissionStatus.PENDING,
        nullable=False,
        index=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason = synonym("last_error")

    claim = relationship("Claim")
    appeal = relationship("Appeal")
    integration = relationship("Integration")
    events = relationship(
        "SubmissionEvent",
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="SubmissionEvent.occurred_at",
    )


class SubmissionEvent(Base):
    __tablename__ = "appeal_submission_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("appeal_submissions.id"), nullable=False, index=True
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        SqlEnum(SubmissionStatus, name="appealsubmissionstatus"),
        nullable=False,
        index=True,
    )
    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )

    submission = relationship("Submission", back_populates="events")


AppealSubmission = Submission
AppealSubmissionEvent = SubmissionEvent
AppealSubmissionStatus = SubmissionStatus
