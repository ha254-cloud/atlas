"""
Priority scoring for the work-queue views — deliberately simple, explicit,
and easy to reason about rather than a black-box model. Higher score =
work on this claim first.

score = (billed_amount / $1,000) x recovery_probability x urgency_multiplier

- `recovery_probability` is stored on Claim as a 0-100 scale; treated as
  0.5 (unknown/neutral) if the claim hasn't been AI-analyzed yet.
- `urgency_multiplier` boosts claims whose current stage is overdue or
  close to its SLA deadline, so a big claim that's about to breach SLA
  jumps ahead of an equally large claim with time to spare.
"""

from datetime import datetime
from decimal import Decimal


def compute_priority_score(
    billed_amount: Decimal | None,
    recovery_probability: Decimal | None,
    due_at: datetime | None,
    now: datetime | None = None,
) -> Decimal:
    now = now or datetime.utcnow()

    amount_factor = float(billed_amount or 0) / 1000.0
    probability_factor = (
        (float(recovery_probability) / 100.0) if recovery_probability is not None else 0.5
    )

    urgency_multiplier = 1.0
    if due_at is not None:
        hours_remaining = (due_at - now).total_seconds() / 3600.0
        if hours_remaining <= 0:
            urgency_multiplier = 2.0  # already overdue
        elif hours_remaining < 24:
            urgency_multiplier = 1.5  # due soon

    score = amount_factor * probability_factor * urgency_multiplier
    return Decimal(str(round(min(score, 999.99), 2)))
