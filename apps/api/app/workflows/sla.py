"""
SLA targets for each workflow stage — how long a claim should reasonably
sit in a given state before it's considered overdue. Purely a Python
mapping (matches the codebase's existing enum-driven-lookup convention),
not an admin-editable table yet.
"""

from datetime import UTC, datetime, timedelta

from app.models.claim_workflow import ClaimWorkflowState as S

# Target completion time for the *current* state, in minutes.
# Terminal states (RECOVERED, CLOSED) have no SLA.
SLA_MINUTES: dict[S, int] = {
    S.IMPORTED: 15,
    S.VALIDATED: 5,
    S.ANALYZED: 2,
    S.WAITING_FOR_DOCUMENTS: 3 * 24 * 60,
    S.READY_FOR_APPEAL: 60,
    S.APPEAL_GENERATED: 60,
    S.UNDER_REVIEW: 24 * 60,
    S.APPROVED: 4 * 60,
    S.SUBMITTED: 60,
    S.PENDING_PAYER: 30 * 24 * 60,
}


def compute_due_at(state: S, entered_at: datetime | None = None) -> datetime | None:
    """The deadline for the given state, or None if the state has no SLA."""
    minutes = SLA_MINUTES.get(state)
    if minutes is None:
        return None
    return (entered_at or datetime.utcnow()) + timedelta(minutes=minutes)


def is_overdue(due_at: datetime | None, now: datetime | None = None) -> bool:
    if due_at is None:
        return False
    comparison_now = now or datetime.now(UTC)
    if comparison_now.tzinfo is None:
        comparison_now = comparison_now.replace(tzinfo=UTC)
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    return comparison_now > due_at
