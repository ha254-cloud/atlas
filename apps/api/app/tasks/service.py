from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.events.event_types import EventType
from app.events.publisher import EventPublisher
from app.models.claim import Claim
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.organizations.schemas import OrganizationSettings
from app.tasks.assignment import assign_least_loaded
from app.tasks.models import (
    Task,
    TaskActivity,
    TaskDepartment,
    TaskNotification,
    TaskStatus,
    TaskType,
)
from app.tasks.priority import calculate_priority_score
from app.tasks.repository import TaskRepository
from app.tasks.sla import due_date_for

DEPARTMENT_BY_TYPE = {
    TaskType.GENERATE_APPEAL: TaskDepartment.APPEALS,
    TaskType.APPROVE_APPEAL: TaskDepartment.APPEALS,
    TaskType.SUBMIT_APPEAL: TaskDepartment.APPEALS,
    TaskType.UPLOAD_PAYMENT_REPORT: TaskDepartment.FINANCE,
    TaskType.VERIFY_PAYMENT: TaskDepartment.FINANCE,
    TaskType.RECONCILE_PAYMENT: TaskDepartment.FINANCE,
    TaskType.ESCALATE: TaskDepartment.REVENUE_MANAGEMENT,
}
NEXT_TASK = {
    TaskType.REVIEW_CLAIM: TaskType.GENERATE_APPEAL,
    TaskType.GENERATE_APPEAL: TaskType.APPROVE_APPEAL,
    TaskType.APPROVE_APPEAL: TaskType.SUBMIT_APPEAL,
    TaskType.SUBMIT_APPEAL: TaskType.FOLLOW_UP,
    TaskType.VERIFY_PAYMENT: TaskType.RECONCILE_PAYMENT,
    TaskType.RECONCILE_PAYMENT: TaskType.CLOSE_CLAIM,
}
TRANSITIONS = {
    TaskStatus.NEW: {TaskStatus.ASSIGNED, TaskStatus.CANCELLED},
    TaskStatus.ASSIGNED: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.WAITING,
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.IN_PROGRESS: {TaskStatus.WAITING, TaskStatus.COMPLETED, TaskStatus.CANCELLED},
    TaskStatus.WAITING: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.COMPLETED,
        TaskStatus.OVERDUE,
        TaskStatus.CANCELLED,
    },
    TaskStatus.OVERDUE: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.WAITING,
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}


class TaskService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id
        self.repository = TaskRepository(db, organization_id)
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if organization is None:
            raise ValueError("Organization not found")
        self.settings = OrganizationSettings.model_validate(
            organization.settings or {}
        ).task_intelligence

    def create_for_claim(
        self,
        claim_id: int,
        task_type: TaskType,
        *,
        actor_id: int | None = None,
        reason: str,
        due_date: datetime | None = None,
        assigned_to: int | None = None,
        notes: str | None = None,
        sequence: int = 1,
        correlation_id: str | None = None,
    ) -> Task:
        existing = self.repository.existing(claim_id, task_type, sequence)
        if existing:
            return existing
        claim = (
            self.db.query(Claim)
            .filter(Claim.id == claim_id, Claim.organization_id == self.organization_id)
            .first()
        )
        if claim is None:
            raise HTTPException(status_code=404, detail="Claim not found")
        department = DEPARTMENT_BY_TYPE.get(task_type, TaskDepartment.CLAIMS)
        now = datetime.utcnow()
        assignee = None
        if assigned_to is not None:
            assignee = self._valid_user(assigned_to)
        elif self.settings.auto_assign_tasks:
            assignee = assign_least_loaded(
                self.db,
                organization_id=self.organization_id,
                department=department,
                billed_amount=claim.billed_amount,
                payer_code=claim.payer.payer_code,
                payer_name=claim.payer.name,
                settings=self.settings,
            )
        task = Task(
            organization_id=self.organization_id,
            claim_id=claim.id,
            payer_id=claim.payer_id,
            assigned_to=assignee.id if assignee else None,
            department=department,
            priority_score=calculate_priority_score(
                billed_amount=claim.billed_amount,
                recovery_probability=claim.recovery_probability,
                service_date=claim.service_date,
            ),
            task_type=task_type,
            status=TaskStatus.ASSIGNED if assignee else TaskStatus.NEW,
            due_date=due_date
            or due_date_for(
                payer_code=claim.payer.payer_code,
                payer_name=claim.payer.name,
                settings=self.settings,
                now=now,
            ),
            notes=notes,
            created_by=actor_id,
            sequence=sequence,
        )
        self.db.add(task)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            existing = self.repository.existing(claim_id, task_type, sequence)
            if existing:
                return existing
            raise
        self._activity(task, "task.created", None, reason, actor_id, correlation_id)
        if assignee:
            self._notify(
                task,
                assignee.id,
                "task.assigned",
                "New task assigned",
                f"{task_type.value.replace('_', ' ').title()} for claim {claim.claim_number}",
                0,
            )
        self.db.commit()
        self.db.refresh(task)
        EventPublisher().publish(
            EventType.TASK_CREATED,
            {
                "task_id": task.id,
                "claim_id": claim.id,
                "assigned_to": task.assigned_to,
                "correlation_id": correlation_id,
            },
            self.organization_id,
        )
        return task

    def transition(
        self,
        task_id: int,
        status: TaskStatus,
        *,
        actor: User,
        reason: str,
        notes: str | None = None,
    ) -> Task:
        task = self._authorized_task(task_id, actor)
        if status not in TRANSITIONS[task.status]:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot transition task from {task.status.value} to {status.value}",
            )
        before = self._snapshot(task)
        task.status = status
        if notes is not None:
            task.notes = notes
        if status == TaskStatus.COMPLETED:
            task.completed_at = datetime.utcnow()
        self._activity(task, f"task.{status.value}", before, reason, actor.id, None)
        self.db.commit()
        self.db.refresh(task)
        if status == TaskStatus.COMPLETED:
            EventPublisher().publish(
                EventType.TASK_COMPLETED,
                {"task_id": task.id, "claim_id": task.claim_id},
                self.organization_id,
            )
            next_type = NEXT_TASK.get(task.task_type)
            if next_type:
                self.create_for_claim(
                    task.claim_id,
                    next_type,
                    actor_id=actor.id,
                    reason=f"Created after completing task {task.id}",
                    sequence=task.sequence,
                )
        return task

    def assign(self, task_id: int, user_id: int, *, actor_id: int, reason: str) -> Task:
        task = self.repository.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        user = self._valid_user(user_id)
        before = self._snapshot(task)
        task.assigned_to = user.id
        if task.status == TaskStatus.NEW:
            task.status = TaskStatus.ASSIGNED
        self._activity(task, "task.assigned", before, reason, actor_id, None)
        self._notify(
            task,
            user.id,
            "task.assigned",
            "Task assigned",
            f"{task.task_type.value.replace('_', ' ').title()} is now in your queue",
            task.escalation_level,
        )
        self.db.commit()
        self.db.refresh(task)
        EventPublisher().publish(
            EventType.TASK_ASSIGNED,
            {"task_id": task.id, "claim_id": task.claim_id, "assigned_to": user.id},
            self.organization_id,
        )
        return task

    def _authorized_task(self, task_id: int, actor: User) -> Task:
        task = self.repository.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if (
            actor.role not in {UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER}
            and task.assigned_to != actor.id
        ):
            raise HTTPException(status_code=403, detail="Task is not assigned to this user")
        return task

    def _valid_user(self, user_id: int) -> User:
        user = (
            self.db.query(User)
            .filter(
                User.id == user_id,
                User.organization_id == self.organization_id,
                User.is_active.is_(True),
            )
            .first()
        )
        if user is None:
            raise HTTPException(
                status_code=422, detail="Assignee is not an active user in this organization"
            )
        return user

    def _activity(
        self,
        task: Task,
        action: str,
        before: dict | None,
        reason: str,
        actor_id: int | None,
        correlation_id: str | None,
    ) -> None:
        self.repository.add_activity(
            TaskActivity(
                organization_id=self.organization_id,
                task_id=task.id,
                claim_id=task.claim_id,
                actor_id=actor_id,
                action=action,
                before=before,
                after=self._snapshot(task),
                reason=reason,
                correlation_id=correlation_id or str(uuid4()),
            )
        )

    def _notify(
        self,
        task: Task,
        recipient_id: int,
        notification_type: str,
        title: str,
        message: str,
        level: int,
    ) -> None:
        self.db.add(
            TaskNotification(
                organization_id=self.organization_id,
                task_id=task.id,
                recipient_id=recipient_id,
                notification_type=notification_type,
                title=title,
                message=message,
                level=level,
            )
        )

    @staticmethod
    def _snapshot(task: Task) -> dict:
        return {
            "status": task.status.value,
            "assigned_to": task.assigned_to,
            "priority_score": task.priority_score,
            "due_date": task.due_date.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "escalation_level": task.escalation_level,
        }
