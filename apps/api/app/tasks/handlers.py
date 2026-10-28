import logging

from app.db.database import SessionLocal
from app.events.event_types import EventType
from app.tasks.models import TaskType
from app.tasks.service import TaskService

logger = logging.getLogger(__name__)

EVENT_TASKS = {
    EventType.CLAIM_ANALYZED.value: TaskType.REVIEW_CLAIM,
    EventType.APPEAL_GENERATED.value: TaskType.APPROVE_APPEAL,
    EventType.APPEAL_APPROVED.value: TaskType.SUBMIT_APPEAL,
    EventType.PAYMENT_RECEIVED.value: TaskType.VERIFY_PAYMENT,
    EventType.PAYMENT_VERIFIED.value: TaskType.RECONCILE_PAYMENT,
}


class TaskEventHandler:
    def __call__(self, event_type: str, payload: dict, organization_id: int | None) -> None:
        task_type = EVENT_TASKS.get(event_type)
        claim_id = payload.get("claim_id")
        if task_type is None or organization_id is None or claim_id is None:
            return
        db = SessionLocal()
        try:
            service = TaskService(db, organization_id)
            if service.settings.auto_create_tasks:
                service.create_for_claim(
                    int(claim_id),
                    task_type,
                    reason=f"Created automatically from {event_type}",
                    correlation_id=payload.get("correlation_id") or payload.get("event_id"),
                )
        except Exception:
            db.rollback()
            logger.exception("Task event handling failed for %s", event_type)
        finally:
            db.close()
