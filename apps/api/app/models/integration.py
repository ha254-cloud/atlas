from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base


class IntegrationStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SYNCING = "syncing"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class Integration(Base, TimestampMixin):
    """
    Stores the configuration and (encrypted) credentials for one external
    integration belonging to an organization.

    Security contract:
      - access_token and refresh_token are NEVER stored in plaintext.
      - They are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) using
        the INTEGRATION_ENCRYPTION_KEY environment variable before insert.
      - The plain values are only available in memory during a sync cycle.
    """

    __tablename__ = "integrations"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    status: Mapped[IntegrationStatus] = mapped_column(
        SqlEnum(IntegrationStatus),
        default=IntegrationStatus.PENDING,
        nullable=False,
    )

    # Encrypted tokens — never plaintext
    encrypted_access_token: Mapped[Optional[str]] = mapped_column(
        String(2048),
        nullable=True,
    )

    encrypted_refresh_token: Mapped[Optional[str]] = mapped_column(
        String(2048),
        nullable=True,
    )

    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_sync_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Set whenever a sync fails, cleared on the next successful sync —
    # surfaced on the Integration Health Dashboard so admins see WHY a
    # connection is broken (e.g. "Authentication Expired") without digging
    # through logs.
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Running lifetime total of claims imported through this integration —
    # a cheap counter (incremented by SyncOrchestrator on every successful
    # sync) rather than a COUNT(*) query, since the source claims aren't
    # tagged with the integration_id that produced them.
    claims_imported_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Arbitrary provider-specific settings (client_id, base_url, etc.)
    settings: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )


class IntegrationCredentialVersion(Base):
    __tablename__ = "integration_credential_versions"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "version",
            name="uq_integration_credential_versions_integration_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    integration_id: Mapped[int] = mapped_column(
        ForeignKey("integrations.id"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    credential_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    fingerprints: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class IntegrationMappingProfile(Base):
    __tablename__ = "integration_mapping_profiles"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "version",
            name="uq_integration_mapping_profiles_integration_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    integration_id: Mapped[int] = mapped_column(
        ForeignKey("integrations.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_format: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IntegrationMappingField(Base):
    __tablename__ = "integration_mapping_fields"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "target_field",
            name="uq_integration_mapping_fields_profile_target",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("integration_mapping_profiles.id"), nullable=False, index=True
    )
    source_field: Mapped[str] = mapped_column(String(200), nullable=False)
    target_field: Mapped[str] = mapped_column(String(100), nullable=False)
    transform: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class IntegrationSyncRun(Base):
    __tablename__ = "integration_sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    integration_id: Mapped[int] = mapped_column(
        ForeignKey("integrations.id"), nullable=False, index=True
    )
    mapping_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("integration_mapping_profiles.id"), nullable=True
    )
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    records_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    initiated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationSyncError(Base):
    __tablename__ = "integration_sync_errors"

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_run_id: Mapped[int] = mapped_column(
        ForeignKey("integration_sync_runs.id"), nullable=False, index=True
    )
    row_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_field: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    error_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
