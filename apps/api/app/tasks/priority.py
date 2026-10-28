from datetime import date
from decimal import Decimal


def calculate_priority_score(
    *,
    billed_amount: Decimal,
    recovery_probability: Decimal | None,
    service_date: date,
    today: date | None = None,
) -> int:
    """Return an explainable 0-100 score weighted by cash, probability, and age."""
    today = today or date.today()
    probability = max(Decimal("0"), min(recovery_probability or Decimal("50"), Decimal("100")))
    amount = max(Decimal("0"), billed_amount)
    days_outstanding = max(0, (today - service_date).days)
    score = (
        probability * Decimal("0.60")
        + min(amount / Decimal("1000000"), Decimal("1")) * Decimal("25")
        + min(Decimal(days_outstanding) / Decimal("60"), Decimal("1")) * Decimal("15")
    )
    if probability >= 90 and amount >= Decimal("500000") and days_outstanding >= 30:
        score += Decimal("5")
    return int(min(Decimal("100"), score).quantize(Decimal("1")))
