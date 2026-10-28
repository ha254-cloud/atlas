from decimal import Decimal

from app.finance.schemas import ReconciliationSummary


def build_reconciliation_summary(
    payments: list[tuple[int | None, Decimal, str]],
    *,
    overpaid_claim_count: int,
) -> ReconciliationSummary:
    unmatched = [payment for payment in payments if payment[0] is None]
    matched = [payment for payment in payments if payment[0] is not None]
    return ReconciliationSummary(
        unmatched_payment_count=len(unmatched),
        unmatched_payment_amount=float(sum((row[1] for row in unmatched), Decimal(0))),
        matched_payment_count=len(matched),
        matched_payment_amount=float(sum((row[1] for row in matched), Decimal(0))),
        overpaid_claim_count=overpaid_claim_count,
        currencies=sorted({row[2] for row in payments}),
    )
