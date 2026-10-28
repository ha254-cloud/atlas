from decimal import Decimal

_ZERO = Decimal("0")


def money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def percentage(numerator: Decimal, denominator: Decimal) -> float:
    if denominator <= _ZERO:
        return 0.0
    return round(float(numerator / denominator * Decimal(100)), 1)


def outstanding(billed: Decimal, paid: Decimal) -> Decimal:
    return max(billed - paid, _ZERO)


def revenue_health_score(
    collection_rate_pct: float,
    denial_rate_pct: float,
    average_payment_days: float,
) -> float:
    collection_component = max(0.0, min(collection_rate_pct, 100.0))
    denial_component = max(0.0, 100.0 - min(denial_rate_pct, 100.0))
    timeliness_component = max(0.0, 100.0 - min(average_payment_days / 60 * 100, 100.0))
    return round(
        collection_component * 0.5 + denial_component * 0.25 + timeliness_component * 0.25,
        1,
    )
