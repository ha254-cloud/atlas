from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.organizations.schemas import TaskIntelligenceSettings
from app.tasks.models import Task, TaskDepartment, TaskStatus, UserTaskSkill

OPEN_STATUSES = (
    TaskStatus.NEW,
    TaskStatus.ASSIGNED,
    TaskStatus.IN_PROGRESS,
    TaskStatus.WAITING,
    TaskStatus.OVERDUE,
)


def _required_role(department: TaskDepartment, amount: Decimal, threshold: Decimal) -> UserRole:
    if amount >= threshold:
        return UserRole.MANAGER
    if department == TaskDepartment.APPEALS:
        return UserRole.APPEALS_SPECIALIST
    if department == TaskDepartment.FINANCE:
        return UserRole.BILLER
    return UserRole.REVENUE_ANALYST


def assign_least_loaded(
    db: Session,
    *,
    organization_id: int,
    department: TaskDepartment,
    billed_amount: Decimal,
    payer_code: str | None,
    payer_name: str,
    settings: TaskIntelligenceSettings,
) -> User | None:
    identifiers = [value.upper() for value in (payer_code, payer_name) if value]
    required_skill = next(
        (settings.payer_skill_map[key] for key in identifiers if key in settings.payer_skill_map),
        None,
    )
    required_role = _required_role(department, billed_amount, settings.high_value_threshold)
    workload = func.sum(case((Task.status.in_(OPEN_STATUSES), 1), else_=0))
    query = (
        db.query(User)
        .outerjoin(Task, (Task.assigned_to == User.id) & (Task.organization_id == organization_id))
        .filter(
            User.organization_id == organization_id,
            User.is_active.is_(True),
            User.role == required_role,
        )
    )
    if required_skill:
        has_skilled_candidate = (
            db.query(User.id)
            .join(UserTaskSkill, UserTaskSkill.user_id == User.id)
            .filter(
                User.organization_id == organization_id,
                User.is_active.is_(True),
                User.role == required_role,
                UserTaskSkill.organization_id == organization_id,
                UserTaskSkill.skill == required_skill,
            )
            .first()
        )
        if has_skilled_candidate is not None:
            query = query.join(UserTaskSkill, UserTaskSkill.user_id == User.id).filter(
                UserTaskSkill.organization_id == organization_id,
                UserTaskSkill.skill == required_skill,
            )
    return query.group_by(User.id).order_by(workload.asc(), User.id.asc()).first()
