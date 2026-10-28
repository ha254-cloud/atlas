from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.tasks.models import TaskDepartment, TaskStatus, TaskType


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    claim_id: int
    payer_id: int
    assigned_to: int | None
    department: TaskDepartment
    priority_score: int
    task_type: TaskType
    status: TaskStatus
    due_date: datetime
    completed_at: datetime | None
    notes: str | None
    escalation_level: int
    created_at: datetime
    updated_at: datetime


class TaskQueueItem(TaskRead):
    claim_number: str
    payer_name: str
    billed_amount: float
    assignee_name: str | None


class TaskQueueResponse(BaseModel):
    count: int
    items: list[TaskQueueItem]


class TaskTransitionRequest(BaseModel):
    status: TaskStatus
    reason: str = Field(min_length=3, max_length=500)
    notes: str | None = Field(default=None, max_length=5000)


class TaskAssignmentRequest(BaseModel):
    assigned_to: int
    reason: str = Field(min_length=3, max_length=500)


class TaskCreateRequest(BaseModel):
    claim_id: int
    task_type: TaskType
    due_date: datetime | None = None
    assigned_to: int | None = None
    notes: str | None = Field(default=None, max_length=5000)
    reason: str = Field(min_length=3, max_length=500)


class TaskQueueFilters(BaseModel):
    status: TaskStatus | None = None
    payer_id: int | None = None
    due_from: date | None = None
    due_to: date | None = None


class ManagerTaskDashboard(BaseModel):
    open_tasks: int
    completed_today: int
    overdue_tasks: int
    average_completion_hours: float


class StaffTaskPerformance(BaseModel):
    user_id: int
    user_name: str
    role: str
    completed_tasks: int
    average_completion_hours: float
    average_priority: float
    total_claim_value: float


class TaskPerformanceResponse(BaseModel):
    caution: str
    staff: list[StaffTaskPerformance]


class TaskNotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    notification_type: str
    title: str
    message: str
    level: int
    read_at: datetime | None
    created_at: datetime


class TaskActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    actor_id: int | None
    action: str
    before: dict | None
    after: dict
    reason: str
    correlation_id: str
    occurred_at: datetime


class UserSkillsUpdate(BaseModel):
    skills: list[str] = Field(max_length=20)
    reason: str = Field(min_length=3, max_length=500)
