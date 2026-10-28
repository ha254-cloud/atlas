from decimal import Decimal


class RecoveryRules:
    MINIMUM_BALANCE = Decimal("25.00")

    HIGH_VALUE = Decimal("1000.00")

    MAX_CLAIM_AGE_DAYS = 365

    def should_recover(
        self,
        balance: Decimal,
        age_days: int,
    ) -> bool:

        if balance < self.MINIMUM_BALANCE:
            return False

        if age_days > self.MAX_CLAIM_AGE_DAYS:
            return False

        return True
