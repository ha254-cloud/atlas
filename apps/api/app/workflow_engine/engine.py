"""
The Sprint 5 Workflow Engine executor — walks a WorkflowDefinition's steps
for one claim, persisting a WorkflowExecution + one WorkflowStepExecution
row per step attempt (the "Workflow History" audit trail).

Design notes:
- CONDITION steps use `next_step_id` as the TRUE branch and
  `failure_step_id` as the FALSE branch.
- HUMAN_APPROVAL and WAIT steps pause execution (status WAITING_APPROVAL /
  WAITING) rather than blocking a request thread. HUMAN_APPROVAL is
  resumed via the approve/reject API endpoint; WAIT is resumed
  automatically by a Celery task scheduled with `apply_async(countdown=...)`
  (see `_schedule_resume` below and `resume_workflow_execution` in
  app/workers/tasks.py) — this codebase had no delayed-scheduling
  precedent before Sprint 5; `.delay()` (immediate dispatch) was the only
  pattern used elsewhere.
- Retries are synchronous/immediate, up to `step.max_retries`, before
  falling back to `step.failure_step_id` (or failing the execution). A
  Celery-scheduled delayed retry (using `retry_delay_seconds`) would be a
  reasonable future upgrade but isn't required for correct retry
  semantics today.
- Definitions can be started manually or by the durable event engine in
    `app.workflows.engine`.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.claim import Claim
from app.models.workflow_definition import (
    WorkflowDefinition,
    WorkflowStep,
    WorkflowStepType,
)
from app.models.workflow_execution import (
    WorkflowExecution,
    WorkflowExecutionStatus,
    WorkflowStepExecution,
    WorkflowStepExecutionStatus,
)
from app.workflow_engine.conditions import ConditionError, evaluate_condition
from app.workflows.actions import action_registry, register_builtin_actions

logger = logging.getLogger(__name__)

register_builtin_actions()

# Compatibility alias retained for existing tests and extensions that
# register temporary handlers directly.
_HANDLERS = action_registry._actions

# Listed in WorkflowStepType for forward-compatibility, but with no
# handler implemented yet — running one fails clearly instead of silently
# no-opping. See step_handlers.py's module docstring for why (CALL_API in
# particular is an SSRF risk without an egress allowlist).
_UNIMPLEMENTED_STEP_TYPES = {
    WorkflowStepType.UPLOAD_DOCUMENT,
    WorkflowStepType.CALL_API,
    WorkflowStepType.LOOP,
}


class WorkflowEngine:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    async def start(
        self,
        workflow_id: int,
        claim_id: int | None,
        *,
        trigger_event: str | None = None,
        trigger_event_id: str | None = None,
        trigger_payload: dict | None = None,
    ) -> WorkflowExecution:
        definition = (
            self.db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.organization_id == self.organization_id,
            )
            .first()
        )
        if definition is None:
            raise ValueError(f"Workflow definition {workflow_id} not found.")
        if not definition.is_active:
            raise ValueError(f"Workflow definition {workflow_id} is not active.")

        entry_step = (
            self.db.query(WorkflowStep)
            .filter(WorkflowStep.workflow_id == workflow_id)
            .order_by(WorkflowStep.step_order.asc())
            .first()
        )
        if entry_step is None:
            raise ValueError(f"Workflow definition {workflow_id} has no steps.")

        claim = None
        if claim_id is not None:
            claim = (
                self.db.query(Claim)
                .filter(Claim.id == claim_id, Claim.organization_id == self.organization_id)
                .first()
            )
            if claim is None:
                raise ValueError(f"Claim {claim_id} not found.")

        context = {"event": trigger_payload or {}}
        if claim is not None:
            context["claim"] = self._claim_snapshot(claim)

        execution = WorkflowExecution(
            organization_id=self.organization_id,
            workflow_id=workflow_id,
            claim_id=claim_id,
            trigger_event=trigger_event,
            trigger_event_id=trigger_event_id,
            trigger_payload=trigger_payload or {},
            status=WorkflowExecutionStatus.RUNNING,
            # Seed a basic claim snapshot up front so CONDITION steps can
            # reference fields like "claim.billed_amount" immediately,
            # without requiring an AI_ANALYSIS step to run first.
            context=context,
            started_at=datetime.now(UTC),
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)

        await self._advance(execution, entry_step)
        return execution

    async def resume(self, execution_id: int, *, approved: bool | None = None) -> WorkflowExecution:
        execution = self._get_execution(execution_id)
        if execution.status not in (
            WorkflowExecutionStatus.WAITING_APPROVAL,
            WorkflowExecutionStatus.WAITING,
        ):
            raise ValueError(
                f"Execution {execution_id} is not waiting (status={execution.status.value})."
            )

        step = self._get_step(execution.current_step_id)
        if step is None:
            raise ValueError("Execution has no current step to resume from.")

        if step.step_type == WorkflowStepType.HUMAN_APPROVAL:
            next_step_id = step.next_step_id if approved else step.failure_step_id
        else:
            next_step_id = step.next_step_id

        execution.status = WorkflowExecutionStatus.RUNNING
        self.db.commit()

        await self._advance(execution, self._get_step(next_step_id))
        return execution

    async def _advance(self, execution: WorkflowExecution, step: WorkflowStep | None) -> None:
        while step is not None:
            execution.current_step_id = step.id
            self.db.commit()

            if step.step_type == WorkflowStepType.END:
                self._log_step(execution, step, WorkflowStepExecutionStatus.SUCCEEDED)
                self._complete(execution)
                return

            if step.step_type == WorkflowStepType.HUMAN_APPROVAL:
                execution.status = WorkflowExecutionStatus.WAITING_APPROVAL
                self.db.commit()
                self._log_step(execution, step, WorkflowStepExecutionStatus.WAITING)
                return

            if step.step_type == WorkflowStepType.WAIT:
                seconds = self._wait_seconds(step.configuration or {})
                execution.status = WorkflowExecutionStatus.WAITING
                self.db.commit()
                self._log_step(execution, step, WorkflowStepExecutionStatus.WAITING)
                self._schedule_resume(execution.id, seconds)
                return

            if step.step_type == WorkflowStepType.CONDITION:
                try:
                    expression = (step.configuration or {}).get("expression", "")
                    result = evaluate_condition(expression, execution.context)
                except ConditionError as exc:
                    self._log_step(
                        execution, step, WorkflowStepExecutionStatus.FAILED, error=str(exc)
                    )
                    self._fail(execution, str(exc))
                    return
                self._log_step(
                    execution,
                    step,
                    WorkflowStepExecutionStatus.SUCCEEDED,
                    output={"result": result},
                )
                next_step_id = step.next_step_id if result else step.failure_step_id
                step = self._get_step(next_step_id)
                continue

            success, output, error = await self._execute_with_retries(execution, step)
            if success:
                execution.context = {**execution.context, step.step_type.value: output}
                self.db.commit()
                self._log_step(
                    execution, step, WorkflowStepExecutionStatus.SUCCEEDED, output=output
                )
                step = self._get_step(step.next_step_id)
                continue

            self._log_step(execution, step, WorkflowStepExecutionStatus.FAILED, error=error)
            if step.failure_step_id:
                step = self._get_step(step.failure_step_id)
                continue
            self._fail(execution, error)
            return

        self._complete(execution)

    async def _execute_with_retries(self, execution: WorkflowExecution, step: WorkflowStep):
        handler = action_registry.get(step.step_type)
        if step.step_type in _UNIMPLEMENTED_STEP_TYPES or handler is None:
            return False, None, f"Step type '{step.step_type.value}' is not yet implemented."

        attempts = max(1, (step.max_retries or 0) + 1)
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                output = await handler(self.db, self.organization_id, execution, step)
                return True, output, None
            except Exception as exc:
                last_error = str(exc)
                logger.exception(
                    "Workflow step %s (%s) attempt %s/%s failed",
                    step.id,
                    step.step_type.value,
                    attempt,
                    attempts,
                )
        return False, None, last_error

    def _claim_snapshot(self, claim: Claim) -> dict:
        return {
            "id": claim.id,
            "claim_number": claim.claim_number,
            "billed_amount": float(claim.billed_amount)
            if claim.billed_amount is not None
            else None,
            "paid_amount": float(claim.paid_amount) if claim.paid_amount is not None else None,
            "status": claim.status,
        }

    def _wait_seconds(self, configuration: dict) -> int:
        if "duration_seconds" in configuration:
            return int(configuration["duration_seconds"])
        if "duration_days" in configuration:
            return int(configuration["duration_days"]) * 86400
        return 86400

    def _schedule_resume(self, execution_id: int, seconds: int) -> None:
        # Best-effort, matching the existing pattern of never letting a
        # background-dispatch failure break the primary flow.
        try:
            from app.workers.tasks import resume_workflow_execution

            resume_workflow_execution.apply_async(args=[execution_id], countdown=seconds)
        except Exception:
            logger.exception("Failed to schedule resume for workflow execution %s", execution_id)

    def _complete(self, execution: WorkflowExecution) -> None:
        execution.status = WorkflowExecutionStatus.COMPLETED
        execution.completed_at = datetime.now(UTC)
        self.db.commit()

    def _fail(self, execution: WorkflowExecution, error: str | None) -> None:
        execution.status = WorkflowExecutionStatus.FAILED
        execution.error_message = error
        execution.completed_at = datetime.now(UTC)
        self.db.commit()

    def _log_step(
        self,
        execution: WorkflowExecution,
        step: WorkflowStep,
        status: WorkflowStepExecutionStatus,
        *,
        output: dict | None = None,
        error: str | None = None,
    ) -> None:
        try:
            attempt = (
                self.db.query(WorkflowStepExecution)
                .filter(
                    WorkflowStepExecution.execution_id == execution.id,
                    WorkflowStepExecution.step_id == step.id,
                )
                .count()
                + 1
            )
            self.db.add(
                WorkflowStepExecution(
                    execution_id=execution.id,
                    step_id=step.id,
                    status=status,
                    attempt=attempt,
                    output=output,
                    error_message=error,
                    started_at=datetime.now(UTC),
                    completed_at=None
                    if status == WorkflowStepExecutionStatus.WAITING
                    else datetime.now(UTC),
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception(
                "Failed to log workflow step execution for execution %s step %s",
                execution.id,
                step.id,
            )

    def _get_execution(self, execution_id: int) -> WorkflowExecution:
        execution = (
            self.db.query(WorkflowExecution)
            .filter(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.organization_id == self.organization_id,
            )
            .first()
        )
        if execution is None:
            raise ValueError(f"Workflow execution {execution_id} not found.")
        return execution

    def _get_step(self, step_id: int | None) -> WorkflowStep | None:
        if step_id is None:
            return None
        return self.db.query(WorkflowStep).filter(WorkflowStep.id == step_id).first()
