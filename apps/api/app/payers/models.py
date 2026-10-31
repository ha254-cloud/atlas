from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base

#: Payer profile/configuration approval lifecycle. A payer always starts as
#: a draft; it must be explicitly submitted and approved by a second,
#: different actor (maker/checker) before it is considered governance-approved.
#: This tracks approval of the *configuration*, independent of `is_active`.
PAYER_APPROVAL_STATUSES = ("draft", "pending_approval", "approved", "rejected")

#: Live connectivity health, reusing the Integration Health Dashboard's
#: health-check behavior for payers bound to an integration connector.
PAYER_HEALTH_STATUSES = ("not_configured", "healthy", "unhealthy")


class Payer(Base, TimestampMixin):
    __tablename__ = "payers"
    __table_args__ = (UniqueConstraint("id", "organization_id", name="uq_payers_id_org"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    payer_code: Mapped[str] = mapped_column(String(50), nullable=False)
    country: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        default="KE",
        server_default="KE",
    )
    submission_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    status_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="manual",
        server_default="manual",
    )
    payment_method: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="report",
        server_default="report",
    )
    portal_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    api_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    submission_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    supports_api: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    supports_sftp: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    supports_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    supports_manual: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    connector_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    integration_id: Mapped[int | None] = mapped_column(
        ForeignKey("integrations.id"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # --- Approval workflow (maker/checker over payer configuration) ---
    approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        # Existing rows created before this workflow existed are treated as
        # already approved so they keep working without a disruptive backfill.
        server_default="approved",
        index=True,
    )
    submitted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- Connectivity monitoring (delegates the live check to the bound
    # Integration when `integration_id` is set; "not_configured" otherwise) ---
    last_health_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_health_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_health_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_check_failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )


POLICY_SOURCE_STATUSES = (
    "draft",
    "pending_approval",
    "approved",
    "rejected",
    "retired",
)


class PayerPolicySource(Base, TimestampMixin):
    __tablename__ = "payer_policy_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["payer_id", "organization_id"],
            ["payers.id", "payers.organization_id"],
            name="fk_policy_source_payer_org",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id",
            "payer_id",
            "policy_code",
            "version",
            name="uq_policy_source_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    payer_id: Mapped[int] = mapped_column(nullable=False, index=True)
    policy_code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        default="KE",
        server_default="KE",
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default="draft",
        index=True,
    )
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    denial_categories: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    procedure_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    change_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
