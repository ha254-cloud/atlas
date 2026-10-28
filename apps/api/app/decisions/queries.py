"""
DecisionQueryService — read-side aggregations over ClaimDecision:

  - get_queue(): "Today's Opportunities" — the latest decision per claim,
    grouped by recommended_action, with dollar totals per bucket.
  - get_executive_forecast(): org-wide recoverable/expected revenue,
    confidence, and average resolution time — the CFO-facing summary.

Deliberately separate from DecisionService (which owns writes/evaluation)
to keep the write path and the read/aggregation path independently
testable, mirroring how app.workflow_engine splits service.py (CRUD) from
its dashboard summary helper.
"""

from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.claim_decision import ClaimDecision, DecisionAction
from app.models.payer import Payer
from app.models.payer_statistics import PayerStatistics

# Conservative fallback when a claim's payer has no PayerStatistics
# snapshot yet (never guessed as "fast" — assume a cautious default).
DEFAULT_RESOLUTION_DAYS = 30.0


class DecisionQueryService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def _latest_decision_ids(self) -> list[int]:
        rows = (
            self.db.query(func.max(ClaimDecision.id))
            .filter(ClaimDecision.organization_id == self.organization_id)
            .group_by(ClaimDecision.claim_id)
            .all()
        )
        return [row[0] for row in rows]

    def _latest_rows(self):
        """Latest ClaimDecision per claim, joined with Claim + Payer.

        Uses a two-step ID lookup (rather than an IN-subquery) — simpler
        to reason about and dashboard-scale, not hot-path traffic.
        """
        latest_ids = self._latest_decision_ids()
        if not latest_ids:
            return []
        return (
            self.db.query(ClaimDecision, Claim, Payer)
            .filter(ClaimDecision.id.in_(latest_ids))
            .join(Claim, Claim.id == ClaimDecision.claim_id)
            .join(Payer, Payer.id == Claim.payer_id)
            .order_by(ClaimDecision.potential_recovery.desc())
            .all()
        )

    def get_queue(self) -> dict:
        buckets: dict = {}
        for decision, claim, payer in self._latest_rows():
            action = decision.recommended_action.value
            bucket = buckets.setdefault(
                action,
                {
                    "recommended_action": action,
                    "total_potential_recovery": Decimal("0"),
                    "count": 0,
                    "claims": [],
                },
            )
            bucket["total_potential_recovery"] += decision.potential_recovery
            bucket["count"] += 1
            bucket["claims"].append(
                {
                    "claim_id": claim.id,
                    "claim_number": claim.claim_number,
                    "payer_name": payer.name,
                    "potential_recovery": float(decision.potential_recovery),
                    "decision_score": float(decision.decision_score),
                    "expected_roi": float(decision.expected_roi)
                    if decision.expected_roi is not None
                    else None,
                    "confidence": float(decision.confidence),
                    "reasoning": decision.reasoning,
                }
            )

        for bucket in buckets.values():
            bucket["total_potential_recovery"] = float(bucket["total_potential_recovery"])

        return {"buckets": list(buckets.values())}

    def get_executive_forecast(self) -> dict:
        rows = self._latest_rows()
        if not rows:
            return {
                "current_recoverable_revenue": 0.0,
                "expected_recovery": 0.0,
                "confidence": 0.0,
                "average_time_days": None,
                "claims_evaluated": 0,
            }

        payer_ids = {payer.id for _, _, payer in rows}
        stats_by_payer = {
            ps.payer_id: ps
            for ps in self.db.query(PayerStatistics).filter(
                PayerStatistics.organization_id == self.organization_id,
                PayerStatistics.payer_id.in_(payer_ids),
            )
        }

        current_recoverable = Decimal("0")
        expected_recovery = Decimal("0")
        confidences = []
        time_estimates = []

        for decision, _claim, payer in rows:
            confidences.append(decision.confidence)
            stats = stats_by_payer.get(payer.id)
            time_estimates.append(
                float(stats.average_payment_time)
                if stats and stats.average_payment_time is not None
                else DEFAULT_RESOLUTION_DAYS
            )
            if decision.recommended_action == DecisionAction.WRITE_OFF:
                continue
            current_recoverable += decision.potential_recovery
            expected_recovery += decision.potential_recovery * (
                decision.decision_score / Decimal("100")
            )

        avg_confidence = sum(confidences) / len(confidences)
        avg_time = sum(time_estimates) / len(time_estimates)

        return {
            "current_recoverable_revenue": float(current_recoverable),
            "expected_recovery": float(expected_recovery),
            "confidence": float(round(avg_confidence, 2)),
            "average_time_days": round(avg_time, 1),
            "claims_evaluated": len(rows),
        }
