from decimal import Decimal

from app.recovery.calculator import RecoveryCalculator
from app.recovery.models import RecoveryOpportunity
from app.recovery.opportunities import Priority
from app.recovery.rules import RecoveryRules
from app.recovery.scorer import RecoveryScorer


class RecoveryEngine:
    def __init__(self):
        self.rules = RecoveryRules()
        self.scorer = RecoveryScorer()
        self.calculator = RecoveryCalculator()

    def analyze(
        self,
        claim,
        denial_probability: float,
        claim_age_days: int,
    ):

        balance = claim.billed_amount - claim.paid_amount

        if not self.rules.should_recover(
            balance,
            claim_age_days,
        ):
            return None

        score = self.scorer.score(
            balance,
            denial_probability,
        )

        estimated = self.calculator.estimate(
            balance,
            score,
        )

        priority = self._determine_priority(
            score,
            balance,
            claim_age_days,
        )

        return RecoveryOpportunity(
            claim_id=claim.id,
            score=score,
            estimated_recovery=estimated,
            balance=balance,
            priority=priority,
            next_action="Review denial category and evaluate appeal readiness",
        )

    def _determine_priority(
        self,
        score: Decimal,
        balance: Decimal,
        claim_age_days: int,
    ) -> Priority:

        if score >= Decimal("90") or balance >= Decimal("5000"):
            return Priority.CRITICAL

        if score >= Decimal("70") or balance >= Decimal("2500"):
            return Priority.HIGH

        if score >= Decimal("40") or claim_age_days >= 180:
            return Priority.MEDIUM

        return Priority.LOW
