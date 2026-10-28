"""
Transition graph for the Recovery Workflow Engine — the rules that decide
what state a claim is allowed to move to next. Enforced by
`WorkflowService.transition()`; nothing should mutate `ClaimWorkflow.state`
directly outside that method.
"""

from app.models.claim_workflow import ClaimWorkflowState as S


class WorkflowTransitionError(ValueError):
    """Raised when a requested state transition isn't allowed."""


# Forward edges of the claim recovery lifecycle. CLOSED is reachable from
# any non-terminal state as an explicit administrative override (a claim
# can always be written off / closed early) — see `validate_transition`.
ALLOWED_TRANSITIONS: dict[S, set[S]] = {
    S.IMPORTED: {S.VALIDATED},
    S.VALIDATED: {S.ANALYZED},
    S.ANALYZED: {S.WAITING_FOR_DOCUMENTS, S.READY_FOR_APPEAL, S.CLOSED},
    S.WAITING_FOR_DOCUMENTS: {S.READY_FOR_APPEAL},
    S.READY_FOR_APPEAL: {S.APPEAL_GENERATED},
    S.APPEAL_GENERATED: {S.UNDER_REVIEW},
    # A rejected appeal sends the claim back to be reworked, not forward.
    S.UNDER_REVIEW: {S.APPROVED, S.READY_FOR_APPEAL},
    S.APPROVED: {S.SUBMITTED},
    S.SUBMITTED: {S.PENDING_PAYER},
    S.PENDING_PAYER: {S.RECOVERED, S.CLOSED},
    S.RECOVERED: {S.CLOSED},
    S.CLOSED: set(),
}


def validate_transition(from_state: S, to_state: S, force: bool = False) -> None:
    """Raise WorkflowTransitionError unless `to_state` is a legal next step
    from `from_state`. `force=True` additionally allows an early close from
    any non-terminal state (administrative write-off/cancellation)."""
    if to_state in ALLOWED_TRANSITIONS.get(from_state, set()):
        return
    if force and to_state == S.CLOSED and from_state != S.CLOSED:
        return
    raise WorkflowTransitionError(
        f"Cannot move claim workflow from '{from_state.value}' to "
        f"'{to_state.value}' (allowed: "
        f"{sorted(s.value for s in ALLOWED_TRANSITIONS.get(from_state, set()))})"
    )
