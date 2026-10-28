from decimal import Decimal


class RecoveryCalculator:
    def estimate(
        self,
        balance: Decimal,
        probability: Decimal,
    ):

        return balance * probability / Decimal("100")
