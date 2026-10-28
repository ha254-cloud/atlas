from sqlalchemy.orm import Session

from app.models.workflow_definition import WorkflowDefinition
from app.models.workflow_execution import WorkflowExecution
from app.workflows.models import WorkflowEvent, WorkflowEventStatus


class WorkflowRepository:
    def __init__(self, db: Session, organization_id: int) -> None:
        self.db = db
        self.organization_id = organization_id

    def matching_definitions(self, event_type: str) -> list[WorkflowDefinition]:
        return (
            self.db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.organization_id == self.organization_id,
                WorkflowDefinition.trigger_event == event_type,
                WorkflowDefinition.is_active.is_(True),
            )
            .order_by(WorkflowDefinition.id)
            .all()
        )

    def event_by_external_id(self, event_id: str) -> WorkflowEvent | None:
        return (
            self.db.query(WorkflowEvent)
            .filter(
                WorkflowEvent.organization_id == self.organization_id,
                WorkflowEvent.event_id == event_id,
            )
            .first()
        )

    def event(self, workflow_event_id: int) -> WorkflowEvent | None:
        return (
            self.db.query(WorkflowEvent)
            .filter(
                WorkflowEvent.id == workflow_event_id,
                WorkflowEvent.organization_id == self.organization_id,
            )
            .first()
        )

    def pending_events(self, limit: int = 100) -> list[WorkflowEvent]:
        return (
            self.db.query(WorkflowEvent)
            .filter(
                WorkflowEvent.organization_id == self.organization_id,
                WorkflowEvent.status == WorkflowEventStatus.PENDING.value,
            )
            .order_by(WorkflowEvent.received_at)
            .limit(limit)
            .all()
        )

    def execution_for_event(
        self,
        workflow_id: int,
        event_id: str,
    ) -> WorkflowExecution | None:
        return (
            self.db.query(WorkflowExecution)
            .filter(
                WorkflowExecution.organization_id == self.organization_id,
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.trigger_event_id == event_id,
            )
            .first()
        )

    def history(self, limit: int = 100) -> list[WorkflowExecution]:
        return (
            self.db.query(WorkflowExecution)
            .filter(WorkflowExecution.organization_id == self.organization_id)
            .order_by(WorkflowExecution.started_at.desc())
            .limit(limit)
            .all()
        )
