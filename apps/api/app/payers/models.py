from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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
