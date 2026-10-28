from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.finance.models import ForecastMethod
from app.finance.schemas import CashForecast


def build_cash_forecast(
    cases: list[tuple[Decimal, Decimal]],
    *,
    currency: str,
    days: int,
) -> CashForecast:
    expected = sum(
        (
            amount * max(Decimal(0), min(score, Decimal(100))) / Decimal(100)
            for amount, score in cases
        ),
        Decimal(0),
    )
    weighted_confidence = (
        sum((score for _, score in cases), Decimal(0)) / len(cases) if cases else Decimal(0)
    )
    now = datetime.now(UTC)
    return CashForecast(
        generated_at=now,
        through_date=date.today() + timedelta(days=days),
        currency=currency,
        expected_collections=float(expected.quantize(Decimal("0.01"))),
        confidence_pct=round(float(weighted_confidence), 1),
        case_count=len(cases),
        method=ForecastMethod.OPEN_CASE_PROBABILITY_WEIGHTED,
        assumptions=[
            "Uses currently open recovery cases and their recorded recovery scores.",
            "Does not guarantee collection timing or payer settlement.",
        ],
    )
