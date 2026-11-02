import logging
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.db.database import SessionLocal
from app.workflows.events import SUPPORTED_WORKFLOW_TRIGGERS
from app.workflows.models import WorkflowEvent, WorkflowEventStatus
from app.workflows.repository import WorkflowRepository

logger = logging.getLogger(__name__)


class WorkflowTriggerHandler:
    def __call__(
        self,
        event_type: str,
        payload: dict,
        organization_id: int | None,
    ) -> None:
        if event_type not in SUPPORTED_WORKFLOW_TRIGGERS or organization_id is None:
            return
        event_id = str(payload.get("event_id") or uuid4())
        correlation_id = str(payload.get("correlation_id") or event_id)
        db = SessionLocal()
        try:
            repository = WorkflowRepository(db, organization_id)
            existing = repository.event_by_external_id(event_id)
            if existing is not None:
                return
            event = WorkflowEvent(
                organization_id=organization_id,
                event_id=event_id,
                event_type=event_type,
                payload=dict(payload),
                status=WorkflowEventStatus.PENDING.value,
                correlation_id=correlation_id,
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            self._dispatch(event.id, organization_id)
        except IntegrityError:
            db.rollback()
        finally:
            db.close()

    @staticmethod
    def _dispatch(workflow_event_id: int, organization_id: int) -> None:
        try:
            from app.workers.tasks import process_workflow_event

            process_workflow_event.delay(workflow_event_id, organization_id)
        except Exception:
            logger.exception(
                "Workflow event %s persisted but could not be queued",
                workflow_event_id,
            )
