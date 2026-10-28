"""
AgentExecutionLog — one row per agent per multi-agent orchestration run.

This is the "audit trail" the Sprint 4 design calls for: which agent ran,
how long it took, whether it succeeded/failed/was skipped, grouped by
`run_id` so a single orchestration invocation's full timeline can be
reconstructed for debugging/performance tuning.

Deliberately separate from AICallLog (app.models.ai_call_log): AICallLog
meters raw AI Gateway provider calls (tokens/cost) regardless of which
agent (if any) made them; this table tracks the agent layer itself,
including agents that make no AI call at all (Documentation, Recovery)
and one that's conditionally skipped (Appeal).
"""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base


class AgentExecutionLog(Base, TimestampMixin):
    __tablename__ = "agent_execution_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True,
    )
    claim_id: Mapped[int | None] = mapped_column(
        ForeignKey("claims.id"), nullable=True, index=True,
    )

    # Groups every agent row produced by one orchestrator.run() call.
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # succeeded | failed | skipped
    duration_ms: Mapped[int] = mapped_column(nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
