"""
WorkflowService — the orchestrator for claim movement through the Recovery
Workflow Engine. This is the only place `ClaimWorkflow.state` should be
mutated; routers/services elsewhere call `transition()` rather than
touching the row directly.

Note on automatic actions: this service does NOT itself dispatch new
background/Celery work (e.g. auto-triggering AI analysis) — that dispatch
already exists at its established call sites (the import pipeline's
`_dispatch_ai`, and the on-demand "run analysis" flow) and is left alone
here to avoid adding new synchronous `.delay()` calls to a hot, frequently
-exercised path like claim creation (Celery's connection-retry backoff
when no broker is reachable is slow — see test_import_pipeline.py).
Instead, WorkflowService reacts to the *results* of those existing actions
(e.g. once analysis completes, it decides the next workflow state) and
performs same-process, no-I/O auto-transitions (e.g. SUBMITTED -> PENDING_PAYER).
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.claims.timeline import ClaimTimeline
from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.claim import Claim
from app.models.claim_event import ClaimEventType
from app.models.claim_workflow import TERMINAL_STATES, ClaimWorkflow
from app.models.claim_workflow import ClaimWorkflowState as S
from app.models.denial import Denial
from app.models.user import UserRole
from app.repositories.denial_code_repository import DenialCodeRepository
from app.workflows.priority import compute_priority_score
from app.workflows.sla import compute_due_at
from app.workflows.transitions import WorkflowTransitionError, validate_transition

logger = logging.getLogger(__name__)

_ACTIVE_STATES: list[S] = [s for s in S if s not in TERMINAL_STATES]

# States relevant to each role's work queue, plus a human-facing label.
QUEUE_DEFINITIONS: dict[UserRole, tuple[str, list[S]]] = {
    UserRole.BILLER: ("Needs Review", [S.WAITING_FOR_DOCUMENTS, S.PENDING_PAYER]),
    UserRole.REVENUE_ANALYST: (
        "Needs Review",
        [S.ANALYZED, S.WAITING_FOR_DOCUMENTS, S.READY_FOR_APPEAL],
    ),
    UserRole.APPEALS_SPECIALIST: (
        "Needs Review",
        [S.READY_FOR_APPEAL, S.APPEAL_GENERATED, S.UNDER_REVIEW],
    ),
    UserRole.MANAGER: ("Waiting Approval", [S.UNDER_REVIEW, S.APPROVED]),
    UserRole.AUDITOR: ("Audit Queue", [S.SUBMITTED, S.PENDING_PAYER, S.RECOVERED]),
    UserRole.ADMIN: ("High Value Claims", _ACTIVE_STATES),
    UserRole.OWNER: ("High Value Claims", _ACTIVE_STATES),
    UserRole.VIEWER: ("All Active Claims", _ACTIVE_STATES),
}

# Only the executive-facing queues additionally filter to big-dollar claims.
HIGH_VALUE_THRESHOLD = 10_000
HIGH_VALUE_ROLES = {UserRole.ADMIN, UserRole.OWNER}


class WorkflowService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.timeline = ClaimTimeline(db)
        self.publisher = EventPublisher()

    # ------------------------------------------------------------------
    # Core lifecycle
    # ------------------------------------------------------------------

    def get_workflow(self, claim_id: int) -> ClaimWorkflow | None:
        return (
            self.db.query(ClaimWorkflow)
            .filter(
                ClaimWorkflow.claim_id == claim_id,
                ClaimWorkflow.organization_id == self.organization_id,
            )
            .first()
        )

    def start_workflow(self, claim: Claim, actor_id: int | None = None) -> ClaimWorkflow:
        """Create the workflow row for a newly-created claim at IMPORTED,
        then immediately advance it to VALIDATED — the claim already passed
        `validate_create()` before this is ever called."""
        existing = self.get_workflow(claim.id)
        if existing is not None:
            return existing

        now = datetime.utcnow()
        workflow = ClaimWorkflow(
            organization_id=self.organization_id,
            claim_id=claim.id,
            state=S.IMPORTED,
            state_entered_at=now,
            due_at=compute_due_at(S.IMPORTED, now),
        )
        self.db.add(workflow)
        self.db.flush()

        return self.transition(
            claim.id,
            S.VALIDATED,
            actor_id=actor_id,
            reason="Claim payload validated at creation",
        )

    def transition(
        self,
        claim_id: int,
        to_state: S,
        actor_id: int | None = None,
        reason: str | None = None,
        force: bool = False,
    ) -> ClaimWorkflow:
        workflow = self.get_workflow(claim_id)
        if workflow is None:
            raise WorkflowTransitionError(f"No workflow exists for claim {claim_id}")

        validate_transition(workflow.state, to_state, force=force)

        from_state = workflow.state
        now = datetime.utcnow()
        workflow.previous_state = from_state
        workflow.state = to_state
        workflow.state_entered_at = now
        workflow.due_at = compute_due_at(to_state, now)
        workflow.escalated = False

        claim = self.db.query(Claim).filter(Claim.id == claim_id).first()
        if claim is not None:
            workflow.priority_score = compute_priority_score(
                claim.billed_amount,
                claim.recovery_probability,
                workflow.due_at,
                now,
            )

        self.db.flush()

        description = reason or f"Workflow moved from {from_state.value} to {to_state.value}"
        self.timeline.record(
            organization_id=self.organization_id,
            claim_id=claim_id,
            event_type=ClaimEventType.STATUS_CHANGED,
            description=description,
            actor_id=actor_id,
            metadata={"workflow_from": from_state.value, "workflow_to": to_state.value},
        )
        if actor_id is not None:
            AuditService(self.db).log(
                organization_id=self.organization_id,
                user_id=actor_id,
                action=AuditAction.WORKFLOW_TRANSITIONED,
                entity="claim_workflow",
                entity_id=workflow.id,
                metadata={"from": from_state.value, "to": to_state.value, "reason": reason},
            )
        self.publisher.publish(
            EventType.WORKFLOW_TRANSITIONED,
            {
                "claim_id": claim_id,
                "from": from_state.value,
                "to": to_state.value,
                "organization_id": self.organization_id,
            },
            organization_id=self.organization_id,
        )
        self.db.commit()
        self.db.refresh(workflow)

        self._dispatch_auto_transition(workflow)
        return workflow

    def _dispatch_auto_transition(self, workflow: ClaimWorkflow) -> None:
        """Same-process, no-I/O follow-up transitions that don't require a
        human decision or new background dispatch."""
        if workflow.state == S.ANALYZED:
            next_state = (
                S.WAITING_FOR_DOCUMENTS
                if self._needs_documents(workflow.claim_id)
                else S.READY_FOR_APPEAL
            )
            self.transition(
                workflow.claim_id,
                next_state,
                reason="Auto-routed based on required-document check",
            )
        elif workflow.state == S.SUBMITTED:
            self.transition(
                workflow.claim_id,
                S.PENDING_PAYER,
                reason="Appeal submitted — awaiting payer response",
            )

    def _needs_documents(self, claim_id: int) -> bool:
        denial = (
            self.db.query(Denial)
            .filter(Denial.claim_id == claim_id, Denial.organization_id == self.organization_id)
            .order_by(Denial.id.desc())
            .first()
        )
        if denial is None:
            return False
        entry = DenialCodeRepository(self.db).get_by_code(denial.denial_code)
        return bool(entry and entry.required_documents)

    def try_transition(
        self,
        claim_id: int,
        to_state: S,
        actor_id: int | None = None,
        reason: str | None = None,
    ) -> ClaimWorkflow | None:
        """Best-effort variant of `transition()` for call sites (appeal
        generation/review/submission, payment recording, etc.) that should
        keep working even if the claim has no workflow row (e.g. seeded
        directly in a test) or is in an unexpected state — logs and moves
        on rather than blocking the primary operation that already
        succeeded."""
        if self.get_workflow(claim_id) is None:
            return None
        try:
            return self.transition(claim_id, to_state, actor_id=actor_id, reason=reason)
        except WorkflowTransitionError:
            logger.warning(
                "Skipped workflow transition for claim %s to %s (not a valid transition from current state)",
                claim_id,
                to_state.value,
            )
            return None

    # ------------------------------------------------------------------
    # Work queues / SLA views
    # ------------------------------------------------------------------

    def queue_for_user(
        self,
        role: UserRole,
        user_id: int,
    ) -> tuple[str, list[ClaimWorkflow]]:
        label, states = QUEUE_DEFINITIONS.get(role, ("All Active Claims", _ACTIVE_STATES))
        query = (
            self.db.query(ClaimWorkflow)
            .join(Claim, Claim.id == ClaimWorkflow.claim_id)
            .filter(
                ClaimWorkflow.organization_id == self.organization_id,
                ClaimWorkflow.state.in_(states),
            )
        )
        if role in HIGH_VALUE_ROLES:
            query = query.filter(Claim.billed_amount >= HIGH_VALUE_THRESHOLD)
        if role not in {UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER}:
            query = query.filter(Claim.assigned_user_id == user_id)

        workflows = query.order_by(ClaimWorkflow.priority_score.desc()).all()
        return label, workflows

    def queue_summary(self) -> dict[str, int]:
        now = datetime.utcnow()
        base = (
            self.db.query(ClaimWorkflow)
            .join(Claim, Claim.id == ClaimWorkflow.claim_id)
            .filter(
                ClaimWorkflow.organization_id == self.organization_id,
                Claim.organization_id == self.organization_id,
            )
        )
        active = base.filter(ClaimWorkflow.state.notin_(list(TERMINAL_STATES)))
        return {
            "assigned": active.filter(Claim.assigned_user_id.isnot(None)).count(),
            "pending": active.count(),
            "completed": base.filter(ClaimWorkflow.state.in_(list(TERMINAL_STATES))).count(),
            "overdue": active.filter(
                ClaimWorkflow.due_at.isnot(None),
                ClaimWorkflow.due_at < now,
            ).count(),
        }

    def list_overdue(self) -> list[ClaimWorkflow]:
        now = datetime.utcnow()
        return (
            self.db.query(ClaimWorkflow)
            .filter(
                ClaimWorkflow.organization_id == self.organization_id,
                ClaimWorkflow.due_at.isnot(None),
                ClaimWorkflow.due_at < now,
                ClaimWorkflow.state.notin_(list(TERMINAL_STATES)),
            )
            .all()
        )
