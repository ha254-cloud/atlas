from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.workflow_definition import WorkflowStepType
from app.models.workflow_execution import (
    WorkflowExecutionStatus,
    WorkflowStepExecutionStatus,
)
from app.workflow_engine.conditions import ConditionError, evaluate_condition
from app.workflows.events import WorkflowTrigger


class WorkflowStepCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_order: int = Field(ge=1)
    step_type: WorkflowStepType
    name: str = Field(min_length=2, max_length=255)
    configuration: dict[str, Any] = Field(default_factory=dict)
    next_step_id: int | None = None
    failure_step_id: int | None = None
    max_retries: int = Field(default=0, ge=0, le=10)
    retry_delay_seconds: int = Field(default=0, ge=0, le=86400)


class WorkflowStepUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_order: int | None = None
    step_type: WorkflowStepType | None = None
    name: str | None = None
    configuration: dict[str, Any] | None = None
    next_step_id: int | None = None
    failure_step_id: int | None = None
    max_retries: int | None = Field(default=None, ge=0, le=10)
    retry_delay_seconds: int | None = Field(default=None, ge=0, le=86400)


class WorkflowStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_order: int
    step_type: WorkflowStepType
    name: str
    configuration: dict[str, Any]
    next_step_id: int | None
    failure_step_id: int | None
    max_retries: int
    retry_delay_seconds: int


class WorkflowDefinitionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    trigger_event: WorkflowTrigger | None = None
    trigger_conditions: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    @field_validator("trigger_conditions")
    @classmethod
    def validate_trigger_conditions(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            evaluate_condition(value, {})
        except ConditionError as exc:
            raise ValueError(str(exc)) from exc
        return value


class WorkflowDefinitionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    trigger_event: WorkflowTrigger | None = None
    trigger_conditions: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    @field_validator("trigger_conditions")
    @classmethod
    def validate_trigger_conditions(cls, value: str | None) -> str | None:
        return WorkflowDefinitionCreate.validate_trigger_conditions(value)


class WorkflowDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    trigger_event: str | None
    trigger_conditions: str | None
    is_active: bool
    version: int
    steps: list[WorkflowStepRead] = []


class WorkflowExecutionRequest(BaseModel):
    claim_id: int


class WorkflowStepExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    step_id: int
    status: WorkflowStepExecutionStatus
    attempt: int
    output: dict[str, Any] | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None


class WorkflowExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workflow_id: int
    claim_id: int | None
    trigger_event: str | None
    trigger_event_id: str | None
    trigger_payload: dict[str, Any]
    duration_ms: int | None
    status: WorkflowExecutionStatus
    current_step_id: int | None
    context: dict[str, Any]
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    step_executions: list[WorkflowStepExecutionRead] = []


class WorkflowApprovalRequest(BaseModel):
    approved: bool
    note: str | None = None


class WorkflowDashboardSummary(BaseModel):
    running: int
    waiting_approval: int
    failed: int
    completed_today: int
