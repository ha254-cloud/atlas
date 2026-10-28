"""
ClaimAnalysis — one structured, queryable AI-analysis record per claim.

`AIAnalysis` (app/models/ai_analysis.py) remains the raw audit log of every
individual provider call (one row per analysis run, opaque JSON payload).
This table is the derived, structured, *current* view of that analysis —
upserted in place each time a claim is re-analyzed — with real typed
columns so dashboards/reporting/automation can filter and aggregate on
denial_category, recovery_probability, etc. without parsing JSON.
"""

from enum import Enum

from sqlalchemy import JSON, Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ClaimAnalysis(Base, TimestampMixin):
    __tablename__ = "claim_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    # One claim -> one (current) analysis. Re-analysis upserts this row
    # rather than inserting a new one; historical raw responses still live
    # in AIAnalysis if a full audit trail across re-analyses is ever needed.
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        SqlEnum(AnalysisStatus),
        default=AnalysisStatus.PENDING,
        nullable=False,
    )

    denial_category: Mapped[str] = mapped_column(String(50), nullable=True)
    root_cause: Mapped[str] = mapped_column(String(100), nullable=True)
    recovery_probability: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    estimated_recovery_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    ai_summary: Mapped[str] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=True)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=True)
    required_documents: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=True)

    # True when the AI response was still invalid/unusable after one
    # automatic retry (see ClaimAnalyzer._is_invalid_raw) — the row still
    # gets the safe FALLBACK_RESULT values so downstream code always has
    # something to read, but this flag tells a human not to trust them.
    needs_review: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    # Full structured output of a Sprint 4 multi-agent orchestration run
    # (per-agent outputs, detected conflicts, final decision, run_id) —
    # separate from the 8 typed columns above, which remain populated by
    # the single-call ClaimAnalyzer pipeline for backward compatibility.
    # Nullable: most claims are still only ever analyzed the "classic" way.
    multi_agent_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    claim = relationship("Claim", back_populates="analysis")
    appeals = relationship("Appeal", back_populates="analysis")
