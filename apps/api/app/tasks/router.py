from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User, UserRole
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.tasks.models import Task, TaskNotification, TaskStatus
from app.tasks.repository import TaskRepository
from app.tasks.scheduler import run_task_sla_sweep
from app.tasks.schemas import (
    ManagerTaskDashboard,
    TaskActivityRead,
    TaskAssignmentRequest,
    TaskCreateRequest,
    TaskNotificationRead,
    TaskPerformanceResponse,
    TaskQueueItem,
    TaskQueueResponse,
    TaskRead,
    TaskTransitionRequest,
    UserSkillsUpdate,
)
from app.tasks.service import TaskService

router = APIRouter(prefix="/tasks", tags=["Task Intelligence"])
MANAGER_ROLES = {UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER}


def _queue_item(task) -> TaskQueueItem:
    return TaskQueueItem.model_validate(
        {
            **TaskRead.model_validate(task).model_dump(),
            "claim_number": task.claim.claim_number,
            "payer_name": task.payer.name,
            "billed_amount": float(task.claim.billed_amount),
            "assignee_name": f"{task.assignee.first_name} {task.assignee.last_name}"
            if task.assignee
            else None,
        }
    )


@router.get("/queue", response_model=TaskQueueResponse)
def queue(
    status: TaskStatus | None = None,
    payer_id: int | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_TASKS)),
) -> TaskQueueResponse:
    tasks = TaskRepository(db, organization_id).queue(
        user_id=current_user.id,
        manager_view=current_user.role in MANAGER_ROLES,
        status=status,
        payer_id=payer_id,
        due_from=due_from,
        due_to=due_to,
    )
    return TaskQueueResponse(count=len(tasks), items=[_queue_item(task) for task in tasks])


@router.post("", response_model=TaskRead, status_code=201)
def create_task(
    payload: TaskCreateRequest,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_TASKS)),
) -> Task:
    return TaskService(db, organization_id).create_for_claim(
        payload.claim_id,
        payload.task_type,
        actor_id=current_user.id,
        reason=payload.reason,
        due_date=payload.due_date,
        assigned_to=payload.assigned_to,
        notes=payload.notes,
    )


@router.post("/{task_id}/transition", response_model=TaskRead)
def transition(
    task_id: int,
    payload: TaskTransitionRequest,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_TASKS)),
) -> Task:
    return TaskService(db, organization_id).transition(
        task_id, payload.status, actor=current_user, reason=payload.reason, notes=payload.notes
    )


@router.post("/{task_id}/assign", response_model=TaskRead)
def assign(
    task_id: int,
    payload: TaskAssignmentRequest,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_TASKS)),
) -> Task:
    return TaskService(db, organization_id).assign(
        task_id, payload.assigned_to, actor_id=current_user.id, reason=payload.reason
    )


@router.get("/manager", response_model=ManagerTaskDashboard)
def manager_dashboard(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_TASKS)),
) -> ManagerTaskDashboard:
    return ManagerTaskDashboard(
        **TaskRepository(db, organization_id).manager_metrics(datetime.utcnow())
    )


@router.get("/performance", response_model=TaskPerformanceResponse)
def performance(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_TASKS)),
) -> TaskPerformanceResponse:
    return TaskPerformanceResponse(
        caution=(
            "Task counts are operational signals, not standalone productivity measures; "
            "compare complexity, priority, and claim value."
        ),
        staff=TaskRepository(db, organization_id).staff_metrics(),
    )


@router.post("/sla-sweep")
def sla_sweep(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_TASKS)),
) -> dict:
    task_ids = run_task_sla_sweep(db, organization_id)
    return {"escalated_count": len(task_ids), "task_ids": task_ids}


@router.get("/notifications", response_model=list[TaskNotificationRead])
def notifications(
    unread_only: bool = True,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_TASKS)),
) -> list:
    return TaskRepository(db, organization_id).notifications(current_user.id, unread_only)


@router.post("/notifications/{notification_id}/read", response_model=TaskNotificationRead)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_TASKS)),
):
    notification = (
        db.query(TaskNotification)
        .filter(
            TaskNotification.id == notification_id,
            TaskNotification.organization_id == organization_id,
            TaskNotification.recipient_id == current_user.id,
        )
        .first()
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.read_at = datetime.utcnow()
    db.commit()
    db.refresh(notification)
    return notification


@router.get("/claims/{claim_id}/timeline", response_model=list[TaskActivityRead])
def task_timeline(
    claim_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_TASKS)),
) -> list:
    return TaskRepository(db, organization_id).activities(claim_id)


@router.put("/users/{user_id}/skills", status_code=204)
def replace_skills(
    user_id: int,
    payload: UserSkillsUpdate,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_TASKS)),
) -> None:
    user = (
        db.query(User).filter(User.id == user_id, User.organization_id == organization_id).first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    skills = sorted({skill.strip().lower() for skill in payload.skills if skill.strip()})
    TaskRepository(db, organization_id).replace_skills(user_id, skills)
    db.commit()
