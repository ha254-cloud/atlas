"""
Handlers for each executable WorkflowStepType. Every handler has the
signature `async def handler(db, organization_id, execution, step) -> dict`
— it does the step's real work and returns a JSON-serializable dict that
the engine merges into `execution.context` under the step's type name.

Raise a plain Exception (or a more specific one) on failure — the engine
catches it, retries up to `step.max_retries`, and finally routes to
`step.failure_step_id` (or fails the whole execution if there isn't one).

Step types intentionally NOT implemented here (see engine.py's
_UNIMPLEMENTED_STEP_TYPES): UPLOAD_DOCUMENT, CALL_API, LOOP. In
particular, CALL_API — letting an org admin configure an arbitrary URL for
Atlas to call — is a real SSRF risk without an egress allowlist, which is
out of scope for this round; it's deliberately left unimplemented (fails
clearly) rather than silently built unsafely.
"""

from app.agents.orchestrator import AgentOrchestrator
from app.api.v1.notifications import publish_notification
from app.appeals.service import AppealService
from app.events.publisher import EventPublisher
from app.models.claim import Claim
from app.models.workflow_execution import WorkflowExecution
from app.services.email_service import EmailService


async def handle_ai_analysis(db, organization_id: int, execution: WorkflowExecution, step) -> dict:
    """Calls the Sprint 4 multi-agent orchestrator — the exact integration
    point described in the Sprint 5 spec ("Workflow -> AI Analysis Step ->
    Orchestrator -> ... -> Workflow Continues")."""
    result = await AgentOrchestrator(db, organization_id).run(execution.claim_id)
    return {
        "agent_outputs": result["agent_outputs"],
        "final_decision": result["final_decision"],
        "conflicts": result["conflicts"],
    }


async def handle_generate_appeal(
    db, organization_id: int, execution: WorkflowExecution, step
) -> dict:
    appeal = await AppealService(db, organization_id).generate_appeal(execution.claim_id)
    return {"appeal_id": appeal.id, "status": appeal.status.value, "summary": appeal.summary}


async def handle_assign_user(db, organization_id: int, execution: WorkflowExecution, step) -> dict:
    config = step.configuration or {}
    user_id = config.get("user_id")
    if not user_id:
        raise ValueError("ASSIGN_USER step requires a 'user_id' in its configuration.")

    claim = (
        db.query(Claim)
        .filter(Claim.id == execution.claim_id, Claim.organization_id == organization_id)
        .first()
    )
    if claim is None:
        raise ValueError(f"Claim {execution.claim_id} not found.")

    claim.assigned_user_id = user_id
    db.commit()
    return {"assigned_user_id": user_id}


async def handle_email(db, organization_id: int, execution: WorkflowExecution, step) -> dict:
    config = step.configuration or {}

    claim = (
        db.query(Claim)
        .filter(Claim.id == execution.claim_id, Claim.organization_id == organization_id)
        .first()
    )

    to_email = config.get("to_email")
    if not to_email and claim is not None and claim.assigned_user is not None:
        to_email = claim.assigned_user.email
    if not to_email:
        raise ValueError(
            "EMAIL step has no resolvable recipient — set 'to_email' in the "
            "step configuration or assign the claim to a user first."
        )

    claim_label = claim.claim_number if claim is not None else str(execution.claim_id)
    subject = config.get("subject", f"Atlas workflow update — claim {claim_label}")
    body = config.get("body", "A workflow step for this claim requires your attention.")

    EmailService().send_custom(to_email, subject, body)
    return {"sent_to": to_email}


async def handle_notification(db, organization_id: int, execution: WorkflowExecution, step) -> dict:
    config = step.configuration or {}
    message = config.get("message", "A workflow step completed.")
    publish_notification(
        organization_id,
        "workflow.notification",
        {"claim_id": execution.claim_id, "message": message},
    )
    return {"message": message}


async def handle_publish_event(
    db, organization_id: int, execution: WorkflowExecution, step
) -> dict:
    config = step.configuration or {}
    event_type = config.get("event_type")
    if not event_type or not isinstance(event_type, str):
        raise ValueError("PUBLISH_EVENT step requires an 'event_type'")
    payload = dict(config.get("payload") or {})
    if execution.claim_id is not None:
        payload.setdefault("claim_id", execution.claim_id)
    EventPublisher().publish(event_type, payload, organization_id=organization_id)
    return {"event_type": event_type, "payload": payload}
