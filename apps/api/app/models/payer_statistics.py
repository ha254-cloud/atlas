"""
PayerStatistics — one row per (organization, payer), refreshed from this
organization's OWN claims/appeals/recovery-case history (never guessed or
hardcoded) via app.decisions.payer_stats_service.PayerStatisticsService.

This is intentionally a persisted snapshot, not a live query like
AnalyticsRepository.payer_performance() — the Decision Engine reads it on
every single claim evaluation, so it needs to be cheap. Call
PayerStatisticsService.refresh_all()/refresh_payer() periodically (e.g. a
future Celery Beat job) or on-demand via
POST /decisions/payer-statistics/refresh to recompute it.
"""

from decimal import Decimal

from sqlalchemy import Float, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class PayerStatistics(Base, TimestampMixin):
    __tablename__ = "payer_statistics"
    __table_args__ = (
        UniqueConstraint("organization_id", "payer_id", name="uq_payer_statistics_org_payer"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    payer_id: Mapped[int] = mapped_column(
        ForeignKey("payers.id"),
        nullable=False,
        index=True,
    )

    # Average days from case open to payment received, for RECOVERED cases.
    average_payment_time: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Percentage (0-100) of terminal appeals (accepted/rejected/denied)
    # that were accepted.
    appeal_success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    average_recovery: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Percentage (0-100) of this payer's appeals generated with no
    # documentation gaps flagged by the Evidence Collector.
    documentation_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Percentage (0-100) of this payer's claims that were denied.
    average_denial_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Average typical_resolution_days (from the denial-code knowledge
    # base) across this payer's actual denials.
    timely_filing_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # How many claims fed this snapshot — lets the UI flag low-confidence
    # statistics (e.g. a single claim) instead of presenting them as
    # equally reliable to a payer with hundreds.
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    payer = relationship("Payer")
