from decimal import Decimal


class RecoveryScorer:
    def score(
        self,
        balance: Decimal,
        denial_probability: float,
    ) -> Decimal:

        amount_factor = min(balance / Decimal("1000"), Decimal("1"))

        probability_factor = Decimal(str(denial_probability))

        score = amount_factor * probability_factor * Decimal("100")

        return score.quantize(Decimal("0.01"))
