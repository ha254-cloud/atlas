from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base


class ConsentPurpose(StrEnum):
    RESEARCH = "research"
    AI_PROCESSING = "ai_processing"
    DATA_SHARING = "data_sharing"
    RETENTION = "retention"


class ConsentDecision(StrEnum):
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"


class RetentionDisposition(StrEnum):
    ARCHIVE = "archive"
    DELETE = "delete"


class RetentionEnforcementMode(StrEnum):
    REPORT_ONLY = "report_only"
    ENFORCE = "enforce"


class PatientConsent(Base):
    """Append-only, directly tenant-owned patient consent decision."""

    __tablename__ = "patient_consents"
    __table_args__ = (
        UniqueConstraint(
            "patient_id", "purpose", "version", name="uq_patient_consents_patient_purpose_version"
        ),
        Index("ix_patient_consents_org_purpose", "organization_id", "purpose"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    retention_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RetentionPolicy(Base):
    """Append-only, directly tenant-owned retention policy version."""

    __tablename__ = "retention_policies"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "resource_type",
            "version",
            name="uq_retention_policies_org_resource_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False)
    disposition: Mapped[str] = mapped_column(String(20), nullable=False)
    legal_hold_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enforcement_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="report_only")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserSession(Base, TimestampMixin):
    """Revocable, directly tenant-owned authenticated user session."""

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("ix_user_sessions_org_active", "organization_id", "revoked_at", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    device: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
