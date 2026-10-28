from decimal import ROUND_HALF_UP, Decimal

from app.recovery.schemas import FinancialPositionRead, RecoveryOpportunityRead

_MONEY = Decimal("0.01")


class RecoveryOpportunityScorer:
    def __init__(
        self,
        *,
        estimated_cost: Decimal,
        critical_expected_amount: Decimal,
        high_expected_amount: Decimal,
    ) -> None:
        self.estimated_cost = estimated_cost
        self.critical_expected_amount = critical_expected_amount
        self.high_expected_amount = high_expected_amount

    def score(self, position: FinancialPositionRead) -> RecoveryOpportunityRead:
        expected = position.expected_recovery_amount
        net_benefit = (expected - self.estimated_cost).quantize(_MONEY, rounding=ROUND_HALF_UP)
        if position.outstanding_amount == 0:
            priority = "low"
            recommendation = "close"
            rationale = "Every shilling is allocated to cash, adjustment, or approved write-off."
        elif net_benefit <= 0:
            priority = "low"
            recommendation = "consider_write_off"
            rationale = "Estimated recovery does not exceed the configured recovery cost."
        elif expected >= self.critical_expected_amount:
            priority = "critical"
            recommendation = "appeal_immediately"
            rationale = "Expected recovery exceeds the configured critical-value threshold."
        elif expected >= self.high_expected_amount:
            priority = "high"
            recommendation = "appeal_immediately"
            rationale = "Expected recovery exceeds the configured high-value threshold."
        elif position.recovery_probability_pct >= Decimal("50"):
            priority = "medium"
            recommendation = "pursue"
            rationale = (
                "Expected recovery is positive and historical recovery probability is at least 50%."
            )
        else:
            priority = "low"
            recommendation = "monitor"
            rationale = "Recovery remains possible, but the current evidence has lower confidence."
        return RecoveryOpportunityRead(
            claim_id=position.claim_id,
            account_id=position.account_id,
            outstanding_amount=position.outstanding_amount,
            recovery_probability_pct=position.recovery_probability_pct,
            expected_recovery_amount=expected,
            estimated_cost_to_recover=self.estimated_cost.quantize(_MONEY),
            expected_net_benefit=net_benefit,
            priority=priority,
            recommendation=recommendation,
            rationale=rationale,
        )
