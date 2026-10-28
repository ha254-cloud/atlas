from datetime import datetime

from sqlalchemy.orm import Session

from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.user import User, UserRole
from app.tasks.models import TaskActivity, TaskNotification, TaskStatus
from app.tasks.repository import TaskRepository
from app.tasks.service import TaskService
from app.tasks.sla import escalation_level

ESCALATION_ROLES = (UserRole.MANAGER, UserRole.OWNER, UserRole.OWNER)


def run_task_sla_sweep(db: Session, organization_id: int, now: datetime | None = None) -> list[int]:
    now = now or datetime.utcnow()
    service = TaskService(db, organization_id)
    repository = TaskRepository(db, organization_id)
    escalated: list[int] = []
    for task in repository.due_tasks(now):
        previous = service._snapshot(task)
        level = escalation_level(
            due_date=task.due_date,
            current_level=task.escalation_level,
            thresholds=service.settings.escalation_after_days,
            now=now,
        )
        task.status = TaskStatus.OVERDUE
        if level <= task.escalation_level:
            continue
        task.escalation_level = level
        role = ESCALATION_ROLES[min(level, len(ESCALATION_ROLES)) - 1]
        recipients = (
            db.query(User)
            .filter(
                User.organization_id == organization_id, User.is_active.is_(True), User.role == role
            )
            .all()
        )
        for recipient in recipients:
            db.add(
                TaskNotification(
                    organization_id=organization_id,
                    task_id=task.id,
                    recipient_id=recipient.id,
                    notification_type="task.escalated",
                    title=f"Level {level} task escalation",
                    message=f"Task {task.id} for claim {task.claim_id} exceeded its SLA",
                    level=level,
                )
            )
        db.add(
            TaskActivity(
                organization_id=organization_id,
                task_id=task.id,
                claim_id=task.claim_id,
                action="task.escalated",
                before=previous,
                after=service._snapshot(task),
                reason=f"SLA escalation level {level}",
                correlation_id=f"sla-{task.id}-{level}",
            )
        )
        escalated.append(task.id)
    db.commit()
    for task_id in escalated:
        EventPublisher().publish(EventType.TASK_ESCALATED, {"task_id": task_id}, organization_id)
    return escalated
