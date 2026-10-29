from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    DDL,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class InterventionType(StrEnum):
    CORRECTED_RESUBMISSION = "corrected_resubmission"
    APPEAL_SUBMISSION = "appeal_submission"
    MISSING_DOCUMENT_RESPONSE = "missing_document_response"
    UNDERPAYMENT_CHALLENGE = "underpayment_challenge"
    DOCUMENTED_FOLLOW_UP = "documented_follow_up"


class AttributionStatus(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    DISPUTED = "disputed"


class PaymentEvidenceState(StrEnum):
    ADVISED = "advised"
    POSTED = "posted"
    CASH_CONFIRMED = "cash_confirmed"
    REVERSED = "reversed"
    UNMATCHED = "unmatched"


class AttributionDisputeOutcome(StrEnum):
    UPHELD = "upheld"
    PARTIALLY_UPHELD = "partially_upheld"
    ACCEPTED = "accepted"


class RecoveryIntervention(Base):
    """Append-only evidence of an Atlas-assisted recovery action."""

    __tablename__ = "recovery_interventions"
    __table_args__ = (
        UniqueConstraint(
            "submission_id",
            "intervention_type",
            name="uq_recovery_interventions_submission_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("appeal_submissions.id"), nullable=True, index=True
    )
    intervention_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecoveryAttributionVersion(Base):
    """Append-only success-fee eligibility decision and contract snapshot."""

    __tablename__ = "recovery_attribution_versions"
    __table_args__ = (
        UniqueConstraint(
            "recovery_id", "version", name="uq_recovery_attribution_versions_recovery_version"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    recovery_id: Mapped[int] = mapped_column(
        ForeignKey("recoveries.id"), nullable=False, index=True
    )
    intervention_id: Mapped[int | None] = mapped_column(
        ForeignKey("recovery_interventions.id"), nullable=True, index=True
    )
    previous_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("recovery_attribution_versions.id"), nullable=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    evidence_state: Mapped[str] = mapped_column(String(30), nullable=False)
    confirmed_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    excluded_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reversal_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    eligible_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fee_schedule_id: Mapped[int] = mapped_column(
        ForeignKey("recovery_fee_schedules.id"), nullable=False
    )
    fee_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    vat_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False)
    dispute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    recovery = relationship("Recovery")
    intervention = relationship("RecoveryIntervention")


class RecoveryAttributionDispute(Base):
    """Append-only challenge to one disputed attribution version."""

    __tablename__ = "recovery_attribution_disputes"
    __table_args__ = (
        UniqueConstraint(
            "attribution_version_id",
            name="uq_recovery_attribution_disputes_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    recovery_id: Mapped[int] = mapped_column(
        ForeignKey("recoveries.id"), nullable=False, index=True
    )
    attribution_version_id: Mapped[int] = mapped_column(
        ForeignKey("recovery_attribution_versions.id"), nullable=False, index=True
    )
    opened_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    attribution_version = relationship("RecoveryAttributionVersion")
    resolution = relationship(
        "RecoveryAttributionDisputeResolution",
        back_populates="dispute",
        uselist=False,
    )


class RecoveryAttributionDisputeResolution(Base):
    """Append-only maker-checker resolution of an attribution dispute."""

    __tablename__ = "recovery_attribution_dispute_resolutions"
    __table_args__ = (
        UniqueConstraint(
            "dispute_id",
            name="uq_recovery_attribution_dispute_resolutions_dispute",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    dispute_id: Mapped[int] = mapped_column(
        ForeignKey("recovery_attribution_disputes.id"), nullable=False, index=True
    )
    outcome: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    eligible_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    resolved_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    dispute = relationship("RecoveryAttributionDispute", back_populates="resolution")


for _table in (
    RecoveryIntervention.__table__,
    RecoveryAttributionVersion.__table__,
    RecoveryAttributionDispute.__table__,
    RecoveryAttributionDisputeResolution.__table__,
):
    event.listen(
        _table,
        "after_create",
        DDL(
            f"CREATE TRIGGER {_table.name}_no_update BEFORE UPDATE ON {_table.name} "
            "BEGIN SELECT RAISE(ABORT, 'revenue attribution ledgers are immutable'); END"
        ).execute_if(dialect="sqlite"),
    )
    event.listen(
        _table,
        "after_create",
        DDL(
            f"CREATE TRIGGER {_table.name}_no_delete BEFORE DELETE ON {_table.name} "
            "BEGIN SELECT RAISE(ABORT, 'revenue attribution ledgers are immutable'); END"
        ).execute_if(dialect="sqlite"),
    )
