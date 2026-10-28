from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base


class AICallLog(Base, TimestampMixin):
    """
    One row per AI Gateway call — the "meter" for the AI layer.

    Deliberately separate from `AIAnalysis` (which stores the actual
    per-claim analysis *result*, one row per claim) — this table logs
    every gateway call across every AI feature (claim analysis, appeal
    generation, document summarization, and anything built on top of the
    gateway later) purely for usage/cost observability. `organization_id`
    is mandatory and comes from `app.ai.cost_tracking.ai_call_context`;
    unattributed calls are never persisted as tenant usage.
    """

    __tablename__ = "ai_call_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    claim_id: Mapped[int | None] = mapped_column(
        ForeignKey("claims.id"),
        nullable=True,
        index=True,
    )

    task: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    # Approximate — derived from a static per-model $/1K-token rate table
    # (app/ai/cost_tracking.py) rather than real provider billing data.
    cost_usd: Mapped[Numeric | None] = mapped_column(Numeric(10, 6), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
