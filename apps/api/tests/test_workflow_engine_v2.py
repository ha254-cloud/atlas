from app.models.organization import Organization
from app.models.workflow_definition import WorkflowStepType
from app.models.workflow_execution import WorkflowExecution
from app.workflow_engine.service import WorkflowDefinitionService
from app.workflows.actions import action_registry
from app.workflows.engine import WorkflowEventEngine
from app.workflows.models import WorkflowEvent, WorkflowEventStatus
from tests.test_workflow_automation import client, db_session, make_claim, run  # noqa: F401, F811


def add_event(db_session, organization_id: int, event_id: str, payload: dict) -> WorkflowEvent:
    event = WorkflowEvent(
        organization_id=organization_id,
        event_id=event_id,
        event_type="claim.analyzed",
        payload=payload,
        correlation_id=event_id,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


def add_triggered_workflow(db_session, organization_id: int, condition: str | None = None):
    service = WorkflowDefinitionService(db_session, organization_id)
    definition = service.create(
        name="High value recovery",
        trigger_event="claim.analyzed",
        trigger_conditions=condition,
    )
    service.add_step(
        definition.id,
        step_order=1,
        step_type=WorkflowStepType.END,
        name="Complete",
    )
    return definition


def test_matching_event_starts_workflow_with_trace_context(db_session):
    organization, claim = make_claim(db_session)
    definition = add_triggered_workflow(
        db_session,
        organization.id,
        "event.recovery_probability >= 80",
    )
    event = add_event(
        db_session,
        organization.id,
        "event-1",
        {"claim_id": claim.id, "recovery_probability": 91},
    )

    execution_ids = run(WorkflowEventEngine(db_session, organization.id).process(event.id))

    execution = db_session.get(WorkflowExecution, execution_ids[0])
    db_session.refresh(event)
    assert execution.workflow_id == definition.id
    assert execution.trigger_event == "claim.analyzed"
    assert execution.trigger_event_id == "event-1"
    assert execution.trigger_payload["recovery_probability"] == 91
    assert execution.duration_ms is not None
    assert event.status == WorkflowEventStatus.PROCESSED.value


def test_false_trigger_condition_skips_execution(db_session):
    organization, claim = make_claim(db_session)
    add_triggered_workflow(
        db_session,
        organization.id,
        "event.recovery_probability >= 80",
    )
    event = add_event(
        db_session,
        organization.id,
        "event-2",
        {"claim_id": claim.id, "recovery_probability": 20},
    )

    assert run(WorkflowEventEngine(db_session, organization.id).process(event.id)) == []
    assert db_session.query(WorkflowExecution).count() == 0


def test_event_replay_is_idempotent(db_session):
    organization, claim = make_claim(db_session)
    add_triggered_workflow(db_session, organization.id)
    event = add_event(db_session, organization.id, "event-3", {"claim_id": claim.id})
    engine = WorkflowEventEngine(db_session, organization.id)

    first_ids = run(engine.process(event.id))
    event.status = WorkflowEventStatus.PENDING.value
    db_session.commit()
    second_ids = run(engine.process(event.id))

    assert second_ids == first_ids
    assert db_session.query(WorkflowExecution).count() == 1


def test_event_matching_is_tenant_scoped(db_session):
    first_organization, _claim = make_claim(db_session)
    definition = add_triggered_workflow(db_session, first_organization.id)
    second_organization = Organization(
        name="Other Health System",
        email="ops@other-health.example",
    )
    db_session.add(second_organization)
    db_session.commit()
    event = add_event(db_session, second_organization.id, "event-4", {})

    assert run(WorkflowEventEngine(db_session, second_organization.id).process(event.id)) == []
    assert (
        db_session.query(WorkflowExecution)
        .filter(WorkflowExecution.workflow_id == definition.id)
        .count()
        == 0
    )


def test_action_registry_exposes_publish_but_not_automatic_submission():
    assert "publish_event" in action_registry.types()
    assert "submit_appeal" not in action_registry.types()


def test_publish_action_cannot_automate_submission(db_session):
    organization, _claim = make_claim(db_session)
    service = WorkflowDefinitionService(db_session, organization.id)
    definition = service.create(name="Unsafe submission")

    import pytest

    with pytest.raises(ValueError, match="human submission is required"):
        service.add_step(
            definition.id,
            step_order=1,
            step_type=WorkflowStepType.PUBLISH_EVENT,
            name="Submit appeal",
            configuration={"event_type": "submission.created"},
        )


def test_product_api_aliases_validate_and_audit(client, db_session):
    from app.models.audit_log import AuditLog

    http, organization, _claim = client
    invalid = http.post(
        "/api/v1/workflows",
        json={"name": "Invalid trigger", "trigger_event": "claim.unknown"},
    )
    assert invalid.status_code == 422

    created = http.post(
        "/api/v1/workflows",
        json={
            "name": "Tenant event workflow",
            "trigger_event": "claim.analyzed",
            "trigger_conditions": "event.score >= 80",
        },
        headers={"x-correlation-id": "workflow-api-test"},
    )
    assert created.status_code == 200
    assert created.json()["trigger_event"] == "claim.analyzed"
    assert http.get("/api/v1/workflow-actions").status_code == 200
    assert http.get("/api/v1/workflow-history").status_code == 200

    audit = (
        db_session.query(AuditLog)
        .filter(
            AuditLog.organization_id == organization.id,
            AuditLog.entity == "workflow_definition",
            AuditLog.entity_id == created.json()["id"],
        )
        .one()
    )
    assert audit.metadata_json["correlation_id"] == "workflow-api-test"
    assert audit.metadata_json["before"] is None
    assert audit.metadata_json["after"]["version"] == 1


def test_api_conceals_other_tenant_workflows(client, db_session):
    from app.core.dependencies import get_current_organization
    from app.main import app
    from app.models.user import User, UserRole
    from app.security.dependencies import get_current_user

    http, _organization, _claim = client
    workflow_id = http.post("/api/v1/workflows", json={"name": "Private workflow"}).json()["id"]
    other_organization = Organization(
        name="Second Tenant",
        email="ops@second-tenant.example",
    )
    db_session.add(other_organization)
    db_session.flush()
    other_user = User(
        organization_id=other_organization.id,
        email="admin@second-tenant.example",
        password_hash="x",
        first_name="Second",
        last_name="Admin",
        role=UserRole.ADMIN,
    )
    db_session.add(other_user)
    db_session.commit()
    app.dependency_overrides[get_current_organization] = lambda: other_organization.id
    app.dependency_overrides[get_current_user] = lambda: other_user

    assert http.get(f"/api/v1/workflow-definitions/{workflow_id}").status_code == 404
    assert all(item["id"] != workflow_id for item in http.get("/api/v1/workflows").json())


def test_definition_with_execution_history_cannot_be_deleted(client):
    http, _organization, claim = client
    workflow = http.post("/api/v1/workflows", json={"name": "Retained workflow"}).json()
    http.post(
        f"/api/v1/workflow-definitions/{workflow['id']}/steps",
        json={"step_order": 1, "step_type": "end", "name": "Finish"},
    )
    executed = http.post(
        f"/api/v1/workflow-definitions/{workflow['id']}/execute",
        json={"claim_id": claim.id},
    )
    assert executed.status_code == 200

    deleted = http.delete(f"/api/v1/workflows/{workflow['id']}")
    assert deleted.status_code == 409
