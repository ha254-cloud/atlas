from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.db.base import TimestampMixin
from app.db.database import Base

_JSON = JSON().with_variant(JSONB(), "postgresql")


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    organization_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, default="KE")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Africa/Nairobi")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    subscription_plan: Mapped[str] = mapped_column(
        "plan",
        String(50),
        nullable=False,
        default="trial",
    )
    plan = synonym("subscription_plan")
    success_fee_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal(0),
    )
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    settings: Mapped[dict[str, Any]] = mapped_column(
        _JSON,
        nullable=False,
        default=dict,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    users = relationship("User", back_populates="organization")
    appeals = relationship("Appeal", back_populates="organization")
    setting_versions = relationship(
        "OrganizationSettingsVersion",
        cascade="all, delete-orphan",
        order_by="OrganizationSettingsVersion.version",
    )


class OrganizationSettingsVersion(Base):
    __tablename__ = "organization_settings_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "version",
            name="uq_organization_settings_versions_org_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
