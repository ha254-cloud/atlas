"""
Escalation policy for stages where a breached SLA should proactively notify
someone, rather than just showing up as "overdue" in a queue. Covers the
two examples in the workflow spec (review sitting too long -> notify
manager; approved-but-not-submitted sitting too long -> escalate to a
director-level role) — deliberately narrow rather than escalating every
overdue stage, since not every delay needs a human ping.

`run_escalation_sweep` is idempotent per state-entry: once a workflow row
has been escalated it won't fire again until it moves to a new state
(`ClaimWorkflow.escalated` is reset on every transition).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.claims.timeline import ClaimTimeline
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.claim_event import ClaimEventType
from app.models.claim_workflow import ClaimWorkflow
from app.models.claim_workflow import ClaimWorkflowState as S
from app.models.user import UserRole

# state -> role whose queue should be notified when this stage is overdue.
# No literal "Director" role exists on Atlas today — OWNER is the closest
# equivalent for the highest-severity escalation.
ESCALATION_RULES: dict[S, UserRole] = {
    S.UNDER_REVIEW: UserRole.MANAGER,
    S.APPROVED: UserRole.OWNER,
}


def run_escalation_sweep(db: Session, organization_id: int) -> list[ClaimWorkflow]:
    """Find overdue, not-yet-escalated workflows in an escalation-eligible
    state for this org, mark them escalated, and emit a timeline entry +
    event. Returns the list of newly-escalated ClaimWorkflow rows."""
    now = datetime.utcnow()
    publisher = EventPublisher()
    timeline = ClaimTimeline(db)
    escalated: list[ClaimWorkflow] = []

    candidates = (
        db.query(ClaimWorkflow)
        .filter(
            ClaimWorkflow.organization_id == organization_id,
            ClaimWorkflow.escalated.is_(False),
            ClaimWorkflow.due_at.isnot(None),
            ClaimWorkflow.due_at < now,
            ClaimWorkflow.state.in_(list(ESCALATION_RULES.keys())),
        )
        .all()
    )

    for workflow in candidates:
        escalate_to = ESCALATION_RULES[workflow.state]
        workflow.escalated = True

        timeline.record(
            organization_id=organization_id,
            claim_id=workflow.claim_id,
            event_type=ClaimEventType.STATUS_CHANGED,
            description=(
                f"Workflow stage '{workflow.state.value}' breached its SLA "
                f"— escalated to {escalate_to.value}"
            ),
            metadata={"escalated_to_role": escalate_to.value, "state": workflow.state.value},
        )
        publisher.publish(
            EventType.WORKFLOW_ESCALATED,
            {
                "claim_id": workflow.claim_id,
                "state": workflow.state.value,
                "escalate_to_role": escalate_to.value,
                "organization_id": organization_id,
            },
            organization_id=organization_id,
        )
        escalated.append(workflow)

    if escalated:
        db.commit()

    return escalated
