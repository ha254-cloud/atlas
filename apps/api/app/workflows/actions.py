from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session

from app.models.workflow_definition import WorkflowStep, WorkflowStepType
from app.models.workflow_execution import WorkflowExecution

WorkflowAction = Callable[
    [Session, int, WorkflowExecution, WorkflowStep],
    Awaitable[dict],
]


class WorkflowActionRegistry:
    def __init__(self) -> None:
        self._actions: dict[WorkflowStepType, WorkflowAction] = {}

    def register(self, action_type: WorkflowStepType, action: WorkflowAction) -> None:
        if action_type in self._actions:
            raise ValueError(f"Workflow action '{action_type.value}' is already registered")
        self._actions[action_type] = action

    def get(self, action_type: WorkflowStepType) -> WorkflowAction | None:
        return self._actions.get(action_type)

    def types(self) -> list[str]:
        return sorted(action.value for action in self._actions)


action_registry = WorkflowActionRegistry()


def register_builtin_actions() -> None:
    if action_registry.types():
        return
    from app.workflow_engine import step_handlers

    for action_type, action in (
        (WorkflowStepType.AI_ANALYSIS, step_handlers.handle_ai_analysis),
        (WorkflowStepType.GENERATE_APPEAL, step_handlers.handle_generate_appeal),
        (WorkflowStepType.ASSIGN_USER, step_handlers.handle_assign_user),
        (WorkflowStepType.EMAIL, step_handlers.handle_email),
        (WorkflowStepType.NOTIFICATION, step_handlers.handle_notification),
        (WorkflowStepType.PUBLISH_EVENT, step_handlers.handle_publish_event),
    ):
        action_registry.register(action_type, action)
