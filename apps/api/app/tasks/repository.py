from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.tasks.models import Task, TaskActivity, TaskNotification, TaskStatus, UserTaskSkill

OPEN_STATUSES = (
    TaskStatus.NEW,
    TaskStatus.ASSIGNED,
    TaskStatus.IN_PROGRESS,
    TaskStatus.WAITING,
    TaskStatus.OVERDUE,
)


class TaskRepository:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def get(self, task_id: int) -> Task | None:
        return (
            self.db.query(Task)
            .options(joinedload(Task.claim), joinedload(Task.payer), joinedload(Task.assignee))
            .filter(Task.id == task_id, Task.organization_id == self.organization_id)
            .first()
        )

    def existing(self, claim_id: int, task_type, sequence: int) -> Task | None:
        return (
            self.db.query(Task)
            .filter(
                Task.organization_id == self.organization_id,
                Task.claim_id == claim_id,
                Task.task_type == task_type,
                Task.sequence == sequence,
            )
            .first()
        )

    def queue(
        self,
        *,
        user_id: int | None,
        manager_view: bool,
        status: TaskStatus | None = None,
        payer_id: int | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
    ) -> list[Task]:
        query = (
            self.db.query(Task)
            .options(joinedload(Task.claim), joinedload(Task.payer), joinedload(Task.assignee))
            .filter(Task.organization_id == self.organization_id)
        )
        if not manager_view:
            query = query.filter(Task.assigned_to == user_id)
        if status:
            query = query.filter(Task.status == status)
        if payer_id:
            query = query.filter(Task.payer_id == payer_id)
        if due_from:
            query = query.filter(Task.due_date >= datetime.combine(due_from, time.min))
        if due_to:
            query = query.filter(
                Task.due_date < datetime.combine(due_to + timedelta(days=1), time.min)
            )
        return query.order_by(Task.priority_score.desc(), Task.due_date.asc(), Task.id.asc()).all()

    def due_tasks(self, now: datetime) -> list[Task]:
        return (
            self.db.query(Task)
            .filter(
                Task.organization_id == self.organization_id,
                Task.status.in_(OPEN_STATUSES),
                Task.due_date < now,
            )
            .all()
        )

    def add_activity(self, activity: TaskActivity) -> None:
        self.db.add(activity)

    def notifications(self, recipient_id: int, unread_only: bool) -> list[TaskNotification]:
        query = self.db.query(TaskNotification).filter(
            TaskNotification.organization_id == self.organization_id,
            TaskNotification.recipient_id == recipient_id,
        )
        if unread_only:
            query = query.filter(TaskNotification.read_at.is_(None))
        return query.order_by(TaskNotification.created_at.desc()).all()

    def activities(self, claim_id: int) -> list[TaskActivity]:
        return (
            self.db.query(TaskActivity)
            .filter(
                TaskActivity.organization_id == self.organization_id,
                TaskActivity.claim_id == claim_id,
            )
            .order_by(TaskActivity.occurred_at.asc(), TaskActivity.id.asc())
            .all()
        )

    def replace_skills(self, user_id: int, skills: list[str]) -> None:
        self.db.query(UserTaskSkill).filter(
            UserTaskSkill.organization_id == self.organization_id,
            UserTaskSkill.user_id == user_id,
        ).delete(synchronize_session=False)
        self.db.add_all(
            UserTaskSkill(organization_id=self.organization_id, user_id=user_id, skill=skill)
            for skill in skills
        )

    def manager_metrics(self, now: datetime) -> dict:
        start = datetime.combine(now.date(), time.min)
        open_count = (
            self.db.query(func.count(Task.id))
            .filter(Task.organization_id == self.organization_id, Task.status.in_(OPEN_STATUSES))
            .scalar()
            or 0
        )
        completed_today = (
            self.db.query(func.count(Task.id))
            .filter(Task.organization_id == self.organization_id, Task.completed_at >= start)
            .scalar()
            or 0
        )
        overdue = (
            self.db.query(func.count(Task.id))
            .filter(Task.organization_id == self.organization_id, Task.status == TaskStatus.OVERDUE)
            .scalar()
            or 0
        )
        completed = (
            self.db.query(Task.created_at, Task.completed_at)
            .filter(
                Task.organization_id == self.organization_id,
                Task.completed_at.is_not(None),
            )
            .all()
        )
        durations = [
            (completed_at - created_at).total_seconds() / 3600
            for created_at, completed_at in completed
        ]
        average_hours = sum(durations) / len(durations) if durations else 0
        return {
            "open_tasks": open_count,
            "completed_today": completed_today,
            "overdue_tasks": overdue,
            "average_completion_hours": round(average_hours, 2),
        }

    def staff_metrics(self) -> list[dict]:
        completed = (
            self.db.query(Task)
            .options(joinedload(Task.assignee), joinedload(Task.claim))
            .filter(
                Task.organization_id == self.organization_id,
                Task.status == TaskStatus.COMPLETED,
                Task.assigned_to.is_not(None),
            )
            .all()
        )
        grouped: dict[int, dict] = {}
        for task in completed:
            row = grouped.setdefault(
                task.assigned_to,
                {
                    "user_id": task.assigned_to,
                    "user_name": f"{task.assignee.first_name} {task.assignee.last_name}",
                    "role": task.assignee.role.value,
                    "completed_tasks": 0,
                    "total_hours": 0.0,
                    "total_priority": 0,
                    "total_claim_value": 0.0,
                },
            )
            row["completed_tasks"] += 1
            row["total_hours"] += (task.completed_at - task.created_at).total_seconds() / 3600
            row["total_priority"] += task.priority_score
            row["total_claim_value"] += float(task.claim.billed_amount)
        return [
            {
                "user_id": row["user_id"],
                "user_name": row["user_name"],
                "role": row["role"],
                "completed_tasks": row["completed_tasks"],
                "average_completion_hours": round(row["total_hours"] / row["completed_tasks"], 2),
                "average_priority": round(row["total_priority"] / row["completed_tasks"], 1),
                "total_claim_value": round(row["total_claim_value"], 2),
            }
            for row in sorted(
                grouped.values(), key=lambda item: (-item["completed_tasks"], item["user_name"])
            )
        ]
