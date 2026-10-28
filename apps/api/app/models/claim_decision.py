"""
ClaimDecision — the output of the Decision Intelligence engine (Sprint 6).

This is deliberately NOT an AI analysis record (see ClaimAnalysis) — it is
the downstream, explainable business decision computed FROM AI analysis
plus historical/payer/effort signals: a 0-100 decision_score, a projected
expected_roi, an economically rational recommended_action (may be
"write_off" even when AI confidence is high — see
app.decisions.scoring.DecisionEngine), and a human-readable reasoning
trail so the recommendation can be trusted rather than displayed as a
bare number.

One claim can accumulate multiple ClaimDecision rows over time (each
evaluation run inserts a new row, mirroring the AgentExecutionLog /
AICallLog audit-trail convention used elsewhere) rather than upserting in
place — this preserves a history of how the decision changed as new
information arrived. Callers that only want the *current* decision should
query the latest row per claim_id (see DecisionService.get_latest_for_claim
/ the decision queue query).
"""

from decimal import Decimal
from enum import Enum

from sqlalchemy import JSON, ForeignKey, Numeric
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin
from app.db.database import Base


class DecisionAction(str, Enum):
    APPEAL = "appeal"
    UPLOAD_DOCUMENTATION = "upload_documentation"
    AWAIT_AUTHORIZATION = "await_authorization"
    MONITOR = "monitor"
    WRITE_OFF = "write_off"


class ClaimDecision(Base, TimestampMixin):
    __tablename__ = "claim_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"),
        nullable=False,
        index=True,
    )

    decision_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    # Potential recovery / estimated effort cost, expressed as a multiple
    # (e.g. 40.00 == "40x"). Null when effort cost is zero/unknown.
    expected_roi: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # The two raw dollar figures expected_roi was derived from — kept as
    # their own columns (not just folded into expected_roi) so the
    # dashboard/explainability UI can show "Recoverable $X - Cost $Y"
    # instead of only the ratio.
    potential_recovery: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    estimated_effort_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )

    recommended_action: Mapped[DecisionAction] = mapped_column(
        SqlEnum(DecisionAction),
        nullable=False,
        index=True,
    )

    # List[str] of plain-English "why" bullets (filing deadline, recovery
    # rate, missing documents, ROI, etc.) — see the product requirement
    # that decisions must never be displayed as a bare score.
    reasoning: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    claim = relationship("Claim")
