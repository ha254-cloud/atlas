from datetime import UTC, datetime
from time import monotonic

from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.workflow_execution import WorkflowExecutionStatus
from app.workflow_engine.conditions import evaluate_condition
from app.workflows.executor import WorkflowExecutor
from app.workflows.models import WorkflowEvent, WorkflowEventStatus
from app.workflows.repository import WorkflowRepository


class WorkflowEventEngine:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id
        self.repository = WorkflowRepository(db, organization_id)

    async def process(self, workflow_event_id: int) -> list[int]:
        event = self.repository.event(workflow_event_id)
        if event is None:
            raise ValueError(f"Workflow event {workflow_event_id} not found")
        if event.status == WorkflowEventStatus.PROCESSED.value:
            return []

        event.status = WorkflowEventStatus.PROCESSING.value
        event.attempts += 1
        self.db.commit()
        execution_ids: list[int] = []
        try:
            for definition in self.repository.matching_definitions(event.event_type):
                context = self._event_context(event)
                if definition.trigger_conditions and not evaluate_condition(
                    definition.trigger_conditions,
                    context,
                ):
                    continue
                existing = self.repository.execution_for_event(
                    definition.id,
                    event.event_id,
                )
                if existing is not None:
                    execution_ids.append(existing.id)
                    continue
                claim_id = self._claim_id(event.payload)
                started = monotonic()
                execution = await WorkflowExecutor(self.db, self.organization_id).start(
                    definition.id,
                    claim_id,
                    trigger_event=event.event_type,
                    trigger_event_id=event.event_id,
                    trigger_payload=event.payload,
                )
                execution.duration_ms = round((monotonic() - started) * 1000)
                self.db.commit()
                execution_ids.append(execution.id)
                if execution.status == WorkflowExecutionStatus.FAILED:
                    raise RuntimeError(
                        execution.error_message or f"Workflow {definition.id} failed"
                    )
            event.status = WorkflowEventStatus.PROCESSED.value
            event.processed_at = datetime.now(UTC)
            event.last_error = None
            self.db.commit()
            return execution_ids
        except Exception as exc:
            self.db.rollback()
            event = self.repository.event(workflow_event_id)
            if event is not None:
                event.status = WorkflowEventStatus.PENDING.value
                event.last_error = str(exc)
                self.db.commit()
            raise

    def dead_letter(self, workflow_event_id: int, error: str) -> None:
        event = self.repository.event(workflow_event_id)
        if event is None:
            return
        event.status = WorkflowEventStatus.DEAD_LETTER.value
        event.last_error = error
        event.processed_at = datetime.now(UTC)
        self.db.commit()

    def _event_context(self, event: WorkflowEvent) -> dict:
        context = {"event": event.payload}
        claim_id = self._claim_id(event.payload)
        if claim_id is not None:
            claim = (
                self.db.query(Claim)
                .filter(
                    Claim.id == claim_id,
                    Claim.organization_id == self.organization_id,
                )
                .first()
            )
            if claim is not None:
                context["claim"] = WorkflowExecutor(
                    self.db,
                    self.organization_id,
                )._claim_snapshot(claim)
        return context

    @staticmethod
    def _claim_id(payload: dict) -> int | None:
        value = payload.get("claim_id")
        return int(value) if value is not None else None
