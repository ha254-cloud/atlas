from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.audit.actions import AuditAction
from app.audit.service import AuditService
from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User
from app.models.workflow_execution import WorkflowExecution
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.workflow_engine.engine import WorkflowEngine
from app.workflow_engine.schemas import (
    WorkflowApprovalRequest,
    WorkflowDashboardSummary,
    WorkflowDefinitionCreate,
    WorkflowDefinitionRead,
    WorkflowDefinitionUpdate,
    WorkflowExecutionRead,
    WorkflowExecutionRequest,
    WorkflowStepCreate,
    WorkflowStepRead,
    WorkflowStepUpdate,
)
from app.workflow_engine.service import WorkflowDefinitionService, get_dashboard_summary
from app.workflows.actions import action_registry
from app.workflows.repository import WorkflowRepository

router = APIRouter(tags=["Workflow Engine"])


def _service(db: Session, organization_id: int) -> WorkflowDefinitionService:
    return WorkflowDefinitionService(db, organization_id)


def _snapshot(definition) -> dict:
    return {
        "name": definition.name,
        "description": definition.description,
        "trigger_event": definition.trigger_event,
        "trigger_conditions": definition.trigger_conditions,
        "is_active": definition.is_active,
        "version": definition.version,
        "steps": [
            {
                "id": step.id,
                "order": step.step_order,
                "type": step.step_type.value,
                "name": step.name,
            }
            for step in definition.steps
        ],
    }


def _audit(
    db: Session,
    request: Request,
    organization_id: int,
    user_id: int,
    action: AuditAction,
    entity_id: int,
    before: dict | None,
    after: dict | None,
    reason: str,
) -> None:
    AuditService(db).log(
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        entity="workflow_definition",
        entity_id=entity_id,
        ip_address=request.client.host if request.client else None,
        metadata={
            "before": before,
            "after": after,
            "reason": reason,
            "correlation_id": request.headers.get("x-correlation-id"),
        },
    )
    db.commit()


@router.post("/workflow-definitions", response_model=WorkflowDefinitionRead)
@router.post("/workflows", response_model=WorkflowDefinitionRead)
def create_workflow_definition(
    payload: WorkflowDefinitionCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    definition = _service(db, organization_id).create(**payload.model_dump())
    _audit(
        db,
        request,
        organization_id,
        current_user.id,
        AuditAction.WORKFLOW_DEFINITION_CREATED,
        definition.id,
        None,
        _snapshot(definition),
        "Workflow definition created",
    )
    return definition


@router.get("/workflow-definitions", response_model=list[WorkflowDefinitionRead])
@router.get("/workflows", response_model=list[WorkflowDefinitionRead])
def list_workflow_definitions(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    return _service(db, organization_id).list_definitions()


@router.get("/workflow-definitions/{workflow_id}", response_model=WorkflowDefinitionRead)
def get_workflow_definition(
    workflow_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    definition = _service(db, organization_id).get(workflow_id)
    if definition is None:
        raise HTTPException(status_code=404, detail="Workflow definition not found")
    return definition


@router.patch("/workflow-definitions/{workflow_id}", response_model=WorkflowDefinitionRead)
@router.put("/workflows/{workflow_id}", response_model=WorkflowDefinitionRead)
def update_workflow_definition(
    workflow_id: int,
    payload: WorkflowDefinitionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    try:
        service = _service(db, organization_id)
        definition = service.get(workflow_id)
        if definition is None:
            raise ValueError(f"Workflow definition {workflow_id} not found.")
        before = _snapshot(definition)
        definition = service.update(workflow_id, payload.model_dump(exclude_unset=True))
        _audit(
            db,
            request,
            organization_id,
            current_user.id,
            AuditAction.WORKFLOW_DEFINITION_UPDATED,
            definition.id,
            before,
            _snapshot(definition),
            "Workflow definition updated",
        )
        return definition
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(
    workflow_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    try:
        service = _service(db, organization_id)
        definition = service.get(workflow_id)
        if definition is None:
            raise ValueError(f"Workflow definition {workflow_id} not found.")
        before = _snapshot(definition)
        service.delete(workflow_id)
        _audit(
            db,
            request,
            organization_id,
            current_user.id,
            AuditAction.WORKFLOW_DEFINITION_DELETED,
            workflow_id,
            before,
            None,
            "Workflow definition deleted before first execution",
        )
    except ValueError as exc:
        status_code = 409 if "execution history" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/workflows/{workflow_id}/enable", response_model=WorkflowDefinitionRead)
def enable_workflow(
    workflow_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    try:
        service = _service(db, organization_id)
        before_definition = service.get(workflow_id)
        if before_definition is None:
            raise ValueError(f"Workflow definition {workflow_id} not found.")
        before = _snapshot(before_definition)
        definition = service.set_active(workflow_id, True)
        _audit(
            db,
            request,
            organization_id,
            current_user.id,
            AuditAction.WORKFLOW_DEFINITION_UPDATED,
            workflow_id,
            before,
            _snapshot(definition),
            "Workflow enabled",
        )
        return definition
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/workflows/{workflow_id}/disable", response_model=WorkflowDefinitionRead)
def disable_workflow(
    workflow_id: int,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    try:
        service = _service(db, organization_id)
        before_definition = service.get(workflow_id)
        if before_definition is None:
            raise ValueError(f"Workflow definition {workflow_id} not found.")
        before = _snapshot(before_definition)
        definition = service.set_active(workflow_id, False)
        _audit(
            db,
            request,
            organization_id,
            current_user.id,
            AuditAction.WORKFLOW_DEFINITION_UPDATED,
            workflow_id,
            before,
            _snapshot(definition),
            "Workflow disabled",
        )
        return definition
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/workflow-actions", response_model=list[str])
def list_workflow_actions(
    _current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    return action_registry.types()


@router.get("/workflow-history", response_model=list[WorkflowExecutionRead])
def list_workflow_history(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    return WorkflowRepository(db, organization_id).history(limit)


@router.post("/workflow-definitions/{workflow_id}/steps", response_model=WorkflowStepRead)
def add_workflow_step(
    workflow_id: int,
    payload: WorkflowStepCreate,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    try:
        service = _service(db, organization_id)
        definition = service.get(workflow_id)
        if definition is None:
            raise ValueError(f"Workflow definition {workflow_id} not found.")
        before = _snapshot(definition)
        step = service.add_step(workflow_id, **payload.model_dump())
        definition = service.get(workflow_id)
        _audit(
            db,
            request,
            organization_id,
            current_user.id,
            AuditAction.WORKFLOW_DEFINITION_UPDATED,
            workflow_id,
            before,
            _snapshot(definition),
            "Workflow action added",
        )
        return step
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch(
    "/workflow-definitions/{workflow_id}/steps/{step_id}", response_model=WorkflowStepRead
)
def update_workflow_step(
    workflow_id: int,
    step_id: int,
    payload: WorkflowStepUpdate,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    try:
        return _service(db, organization_id).update_step(
            workflow_id, step_id, payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/workflow-definitions/{workflow_id}/steps/{step_id}", status_code=204)
def delete_workflow_step(
    workflow_id: int,
    step_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    try:
        _service(db, organization_id).delete_step(workflow_id, step_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/workflow-definitions/{workflow_id}/execute", response_model=WorkflowExecutionRead)
async def execute_workflow(
    workflow_id: int,
    payload: WorkflowExecutionRequest,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    try:
        return await WorkflowEngine(db, organization_id).start(workflow_id, payload.claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/workflow-executions/dashboard", response_model=WorkflowDashboardSummary)
def workflow_dashboard(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    return get_dashboard_summary(db, organization_id)


@router.get("/workflow-executions/{execution_id}", response_model=WorkflowExecutionRead)
def get_workflow_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.VIEW_CLAIMS)),
):
    execution = (
        db.query(WorkflowExecution)
        .filter(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.organization_id == organization_id,
        )
        .first()
    )
    if execution is None:
        raise HTTPException(status_code=404, detail="Workflow execution not found")
    return execution


@router.post("/workflow-executions/{execution_id}/approve", response_model=WorkflowExecutionRead)
async def approve_workflow_execution(
    execution_id: int,
    payload: WorkflowApprovalRequest,
    request: Request,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.MANAGE_WORKFLOWS)),
):
    try:
        execution = await WorkflowEngine(db, organization_id).resume(
            execution_id,
            approved=payload.approved,
        )
        AuditService(db).log(
            organization_id=organization_id,
            user_id=current_user.id,
            action=AuditAction.WORKFLOW_APPROVAL_DECIDED,
            entity="workflow_execution",
            entity_id=execution_id,
            ip_address=request.client.host if request.client else None,
            metadata={
                "before": {"status": "waiting_approval"},
                "after": {"status": execution.status.value},
                "reason": payload.note or ("Approved" if payload.approved else "Rejected"),
                "correlation_id": request.headers.get("x-correlation-id"),
            },
        )
        db.commit()
        return execution
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
