from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class SHAExchange(Base, TimestampMixin):
    __tablename__ = "sha_eclaim_exchanges"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_sha_eclaim_exchanges_org_idempotency",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_sha_eclaim_exchanges_id_org",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id"), nullable=False, index=True)
    integration_id: Mapped[int] = mapped_column(
        ForeignKey("integrations.id"), nullable=False, index=True
    )
    initiated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    ig_version: Mapped[str] = mapped_column(String(20), nullable=False)
    bundle_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    bundle_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    claim_response_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    workflow_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    response_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events = relationship(
        "SHAExchangeEvent",
        back_populates="exchange",
        cascade="all, delete-orphan",
        order_by="SHAExchangeEvent.id",
    )


class SHAExchangeEvent(Base):
    __tablename__ = "sha_eclaim_exchange_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["exchange_id", "organization_id"],
            ["sha_eclaim_exchanges.id", "sha_eclaim_exchanges.organization_id"],
            name="fk_sha_exchange_events_exchange_org",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exchange_id: Mapped[int] = mapped_column(nullable=False, index=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    workflow_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    exchange = relationship("SHAExchange", back_populates="events")
