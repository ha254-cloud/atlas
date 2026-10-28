from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.workflow_definition import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowStepType,
)
from app.models.workflow_execution import WorkflowExecution, WorkflowExecutionStatus
from app.workflow_engine.conditions import evaluate_condition
from app.workflows.actions import action_registry


class WorkflowDefinitionService:
    """CRUD for WorkflowDefinition / WorkflowStep — org-scoped, mirroring
    the existing repository-per-resource convention used throughout the
    codebase (e.g. ClaimRepository)."""

    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def list_definitions(self) -> list[WorkflowDefinition]:
        return (
            self.db.query(WorkflowDefinition)
            .filter(WorkflowDefinition.organization_id == self.organization_id)
            .order_by(WorkflowDefinition.id.desc())
            .all()
        )

    def get(self, workflow_id: int) -> WorkflowDefinition | None:
        return (
            self.db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.organization_id == self.organization_id,
            )
            .first()
        )

    def create(
        self,
        *,
        name: str,
        description: str | None = None,
        trigger_event: str | None = None,
        trigger_conditions: str | None = None,
        is_active: bool = True,
    ) -> WorkflowDefinition:
        trigger_value = trigger_event.value if hasattr(trigger_event, "value") else trigger_event
        definition = WorkflowDefinition(
            organization_id=self.organization_id,
            name=name,
            description=description,
            trigger_event=trigger_value,
            trigger_conditions=trigger_conditions,
            is_active=is_active,
            version=1,
        )
        self.db.add(definition)
        self.db.commit()
        self.db.refresh(definition)
        return definition

    def update(self, workflow_id: int, updates: dict) -> WorkflowDefinition:
        definition = self.get(workflow_id)
        if definition is None:
            raise ValueError(f"Workflow definition {workflow_id} not found.")
        for key, value in updates.items():
            if key == "trigger_event" and hasattr(value, "value"):
                value = value.value
            setattr(definition, key, value)
        if updates:
            definition.version += 1
        self.db.commit()
        self.db.refresh(definition)
        return definition

    def add_step(
        self,
        workflow_id: int,
        *,
        step_order: int,
        step_type: WorkflowStepType,
        name: str,
        configuration: dict | None = None,
        next_step_id: int | None = None,
        failure_step_id: int | None = None,
        max_retries: int = 0,
        retry_delay_seconds: int = 0,
    ) -> WorkflowStep:
        if self.get(workflow_id) is None:
            raise ValueError(f"Workflow definition {workflow_id} not found.")
        self._validate_step(step_type, configuration or {})
        step = WorkflowStep(
            workflow_id=workflow_id,
            step_order=step_order,
            step_type=step_type,
            name=name,
            configuration=configuration or {},
            next_step_id=next_step_id,
            failure_step_id=failure_step_id,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        self.db.add(step)
        definition = self.get(workflow_id)
        definition.version += 1
        self.db.commit()
        self.db.refresh(step)
        return step

    def update_step(self, workflow_id: int, step_id: int, updates: dict) -> WorkflowStep:
        step = self._get_step(workflow_id, step_id)
        self._validate_step(
            updates.get("step_type", step.step_type),
            updates.get("configuration", step.configuration),
        )
        for key, value in updates.items():
            setattr(step, key, value)
        definition = self.get(workflow_id)
        definition.version += 1
        self.db.commit()
        self.db.refresh(step)
        return step

    def delete_step(self, workflow_id: int, step_id: int) -> None:
        step = self._get_step(workflow_id, step_id)
        self.db.delete(step)
        definition = self.get(workflow_id)
        definition.version += 1
        self.db.commit()

    def delete(self, workflow_id: int) -> None:
        definition = self.get(workflow_id)
        if definition is None:
            raise ValueError(f"Workflow definition {workflow_id} not found.")
        has_history = (
            self.db.query(WorkflowExecution.id)
            .filter(
                WorkflowExecution.organization_id == self.organization_id,
                WorkflowExecution.workflow_id == workflow_id,
            )
            .first()
            is not None
        )
        if has_history:
            raise ValueError(
                "Workflow definitions with execution history cannot be deleted; disable it instead."
            )
        self.db.delete(definition)
        self.db.commit()

    def set_active(self, workflow_id: int, enabled: bool) -> WorkflowDefinition:
        return self.update(workflow_id, {"is_active": enabled})

    @staticmethod
    def _validate_step(step_type: WorkflowStepType, configuration: dict) -> None:
        controls = {
            WorkflowStepType.CONDITION,
            WorkflowStepType.HUMAN_APPROVAL,
            WorkflowStepType.WAIT,
            WorkflowStepType.END,
        }
        if step_type not in controls and action_registry.get(step_type) is None:
            raise ValueError(f"Workflow action '{step_type.value}' is not available.")
        if step_type == WorkflowStepType.PUBLISH_EVENT:
            event_type = str(configuration.get("event_type", "")).lower()
            if "submit" in event_type or event_type == "submission.created":
                raise ValueError(
                    "Workflow actions cannot submit appeals; human submission is required."
                )
        if step_type == WorkflowStepType.CONDITION:
            expression = configuration.get("expression")
            if not isinstance(expression, str):
                raise ValueError("CONDITION steps require an 'expression'.")
            evaluate_condition(expression, {})

    def _get_step(self, workflow_id: int, step_id: int) -> WorkflowStep:
        if self.get(workflow_id) is None:
            raise ValueError(f"Workflow definition {workflow_id} not found.")
        step = (
            self.db.query(WorkflowStep)
            .filter(WorkflowStep.id == step_id, WorkflowStep.workflow_id == workflow_id)
            .first()
        )
        if step is None:
            raise ValueError(f"Step {step_id} not found on workflow {workflow_id}.")
        return step


def get_dashboard_summary(db: Session, organization_id: int) -> dict:
    """Powers the Workflow Dashboard's Running / Waiting Approval / Failed
    / Completed Today counts described in the Sprint 5 spec."""

    def _count(status: WorkflowExecutionStatus) -> int:
        return (
            db.query(WorkflowExecution)
            .filter(
                WorkflowExecution.organization_id == organization_id,
                WorkflowExecution.status == status,
            )
            .count()
        )

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    completed_today = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.organization_id == organization_id,
            WorkflowExecution.status == WorkflowExecutionStatus.COMPLETED,
            WorkflowExecution.completed_at >= today_start,
        )
        .count()
    )

    return {
        "running": _count(WorkflowExecutionStatus.RUNNING),
        "waiting_approval": _count(WorkflowExecutionStatus.WAITING_APPROVAL),
        "failed": _count(WorkflowExecutionStatus.FAILED),
        "completed_today": completed_today,
    }
