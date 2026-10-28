"""
Tests for the Sprint 5 Workflow Engine (app/workflow_engine/) — the
configurable, per-organization multi-step business-process automation
layer. Deliberately separate from test_workflow_engine.py (which tests
the pre-existing hardcoded ClaimWorkflow/app/workflows/ state machine —
an unrelated system despite the similar name).

Covers: the safe condition evaluator, the core engine's step sequencing/
branching/retry/failure-routing/pause-resume behavior (against a real
in-memory SQLite DB, with fake step handlers so no LLM/SMTP/Celery calls
happen), and a handful of API-level smoke tests through the FastAPI
TestClient to confirm the router/permissions wiring works end to end.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401 — registers every model on Base.metadata
from app.db.database import Base
from app.models.claim import Claim, ClaimPriority
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.workflow_engine.conditions import ConditionError, evaluate_condition

# ---------------------------------------------------------------------------
# conditions.py
# ---------------------------------------------------------------------------


class TestEvaluateCondition:
    def test_simple_greater_than_true(self):
        assert (
            evaluate_condition("claim.billed_amount > 5000", {"claim": {"billed_amount": 6000}})
            is True
        )

    def test_simple_greater_than_false(self):
        assert (
            evaluate_condition("claim.billed_amount > 5000", {"claim": {"billed_amount": 100}})
            is False
        )

    def test_and_combination_requires_both(self):
        expr = "claim.billed_amount > 5000 AND risk.recovery_probability_pct > 80"
        context = {"claim": {"billed_amount": 6000}, "risk": {"recovery_probability_pct": 90}}
        assert evaluate_condition(expr, context) is True
        context["risk"]["recovery_probability_pct"] = 10
        assert evaluate_condition(expr, context) is False

    def test_or_combination_needs_only_one(self):
        expr = "claim.billed_amount > 5000 OR risk.recovery_probability_pct > 80"
        context = {"claim": {"billed_amount": 100}, "risk": {"recovery_probability_pct": 90}}
        assert evaluate_condition(expr, context) is True

    def test_missing_field_is_false_for_ordering_ops(self):
        assert evaluate_condition("claim.billed_amount > 5000", {}) is False

    def test_string_equality(self):
        assert (
            evaluate_condition("claim.status == 'denied'", {"claim": {"status": "denied"}}) is True
        )
        assert (
            evaluate_condition("claim.status == 'denied'", {"claim": {"status": "paid"}}) is False
        )

    def test_boolean_value(self):
        assert (
            evaluate_condition("compliance.blocking == true", {"compliance": {"blocking": True}})
            is True
        )
        assert (
            evaluate_condition("compliance.blocking == true", {"compliance": {"blocking": False}})
            is False
        )

    def test_empty_expression_raises(self):
        with pytest.raises(ConditionError):
            evaluate_condition("", {})

    def test_malformed_clause_raises(self):
        with pytest.raises(ConditionError):
            evaluate_condition("not a valid clause", {})


# ---------------------------------------------------------------------------
# Engine-level fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def make_claim(db_session, *, billed=Decimal("1000.00")):
    org = Organization(name="Test Health System", email="ops@test-health.example")
    db_session.add(org)
    db_session.flush()

    patient = Patient(
        organization_id=org.id,
        first_name="Jane",
        last_name="Doe",
        medical_record_number="MRN-1",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(organization_id=org.id, name="Acme Insurance", payer_code="ACME")
    db_session.add_all([patient, payer])
    db_session.flush()

    claim = Claim(
        organization_id=org.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-1",
        status="denied",
        billed_amount=billed,
        paid_amount=Decimal("0.00"),
        service_date=date.today() - timedelta(days=10),
        priority=ClaimPriority.MEDIUM,
    )
    db_session.add(claim)
    db_session.commit()
    return org, claim


def run(coro):
    import asyncio

    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# WorkflowEngine — direct, using fake handlers to avoid touching AI/SMTP
# ---------------------------------------------------------------------------


class TestWorkflowEngine:
    def test_linear_workflow_completes_and_logs_each_step(self, db_session, monkeypatch):
        import app.workflow_engine.engine as engine_module
        from app.models.workflow_definition import WorkflowStepType
        from app.workflow_engine.engine import WorkflowEngine
        from app.workflow_engine.service import WorkflowDefinitionService

        async def fake_notification(db, organization_id, execution, step):
            return {"message": "hello"}

        monkeypatch.setitem(
            engine_module._HANDLERS, WorkflowStepType.NOTIFICATION, fake_notification
        )

        org, claim = make_claim(db_session)
        service = WorkflowDefinitionService(db_session, org.id)
        definition = service.create(name="Simple notify then end")
        step1 = service.add_step(
            definition.id,
            step_order=1,
            step_type=WorkflowStepType.NOTIFICATION,
            name="Notify",
        )
        end_step = service.add_step(
            definition.id, step_order=2, step_type=WorkflowStepType.END, name="Done"
        )
        service.update_step(definition.id, step1.id, {"next_step_id": end_step.id})

        execution = run(WorkflowEngine(db_session, org.id).start(definition.id, claim.id))

        assert execution.status.value == "completed"
        assert execution.context["notification"]["message"] == "hello"

        from app.models.workflow_execution import WorkflowStepExecution

        logs = (
            db_session.query(WorkflowStepExecution)
            .filter(WorkflowStepExecution.execution_id == execution.id)
            .all()
        )
        assert len(logs) == 2
        assert all(log.status.value == "succeeded" for log in logs)

    def test_condition_step_branches_true_and_false(self, db_session):
        from app.models.workflow_definition import WorkflowStepType
        from app.workflow_engine.engine import WorkflowEngine
        from app.workflow_engine.service import WorkflowDefinitionService

        org, claim = make_claim(db_session, billed=Decimal("6000.00"))
        service = WorkflowDefinitionService(db_session, org.id)
        definition = service.create(name="Branch on amount")

        true_end = service.add_step(
            definition.id, step_order=3, step_type=WorkflowStepType.END, name="High value"
        )
        false_end = service.add_step(
            definition.id, step_order=4, step_type=WorkflowStepType.END, name="Low value"
        )
        service.add_step(
            definition.id,
            step_order=1,
            step_type=WorkflowStepType.CONDITION,
            name="Amount check",
            configuration={"expression": "claim.billed_amount > 5000"},
            next_step_id=true_end.id,
            failure_step_id=false_end.id,
        )

        execution = run(WorkflowEngine(db_session, org.id).start(definition.id, claim.id))

        assert execution.status.value == "completed"
        assert execution.current_step_id == true_end.id

    def test_unimplemented_step_type_is_rejected_before_persistence(self, db_session):
        from app.models.workflow_definition import WorkflowStepType
        from app.workflow_engine.service import WorkflowDefinitionService

        org, _claim = make_claim(db_session)
        service = WorkflowDefinitionService(db_session, org.id)
        definition = service.create(name="Uses an unimplemented step")

        with pytest.raises(ValueError, match="not available"):
            service.add_step(
                definition.id,
                step_order=1,
                step_type=WorkflowStepType.CALL_API,
                name="Call out",
            )

    def test_step_failure_routes_to_failure_step_when_retries_exhausted(
        self, db_session, monkeypatch
    ):
        import app.workflow_engine.engine as engine_module
        from app.models.workflow_definition import WorkflowStepType
        from app.workflow_engine.engine import WorkflowEngine
        from app.workflow_engine.service import WorkflowDefinitionService

        attempts = {"count": 0}

        async def flaky_handler(db, organization_id, execution, step):
            attempts["count"] += 1
            raise RuntimeError("transient failure")

        monkeypatch.setitem(engine_module._HANDLERS, WorkflowStepType.ASSIGN_USER, flaky_handler)

        org, claim = make_claim(db_session)
        service = WorkflowDefinitionService(db_session, org.id)
        definition = service.create(name="Retries then fails to failure_step")
        failure_end = service.add_step(
            definition.id, step_order=2, step_type=WorkflowStepType.END, name="Failure path"
        )
        service.add_step(
            definition.id,
            step_order=1,
            step_type=WorkflowStepType.ASSIGN_USER,
            name="Assign",
            max_retries=2,
            failure_step_id=failure_end.id,
        )

        execution = run(WorkflowEngine(db_session, org.id).start(definition.id, claim.id))

        assert attempts["count"] == 3  # 1 initial + 2 retries
        assert execution.status.value == "completed"  # routed to failure_step, which is an END
        assert execution.current_step_id == failure_end.id

    def test_human_approval_pauses_then_resumes_on_approve(self, db_session):
        from app.models.workflow_definition import WorkflowStepType
        from app.workflow_engine.engine import WorkflowEngine
        from app.workflow_engine.service import WorkflowDefinitionService

        org, claim = make_claim(db_session)
        service = WorkflowDefinitionService(db_session, org.id)
        definition = service.create(name="Needs approval")
        approved_end = service.add_step(
            definition.id, step_order=2, step_type=WorkflowStepType.END, name="Approved"
        )
        rejected_end = service.add_step(
            definition.id, step_order=3, step_type=WorkflowStepType.END, name="Rejected"
        )
        service.add_step(
            definition.id,
            step_order=1,
            step_type=WorkflowStepType.HUMAN_APPROVAL,
            name="Manager sign-off",
            next_step_id=approved_end.id,
            failure_step_id=rejected_end.id,
        )

        engine = WorkflowEngine(db_session, org.id)
        execution = run(engine.start(definition.id, claim.id))
        assert execution.status.value == "waiting_approval"

        execution = run(engine.resume(execution.id, approved=True))
        assert execution.status.value == "completed"
        assert execution.current_step_id == approved_end.id

    def test_wait_step_pauses_and_schedules_resume(self, db_session, monkeypatch):
        from app.models.workflow_definition import WorkflowStepType
        from app.workflow_engine.engine import WorkflowEngine
        from app.workflow_engine.service import WorkflowDefinitionService

        scheduled = {}

        def fake_schedule(self, execution_id, seconds):
            scheduled["execution_id"] = execution_id
            scheduled["seconds"] = seconds

        monkeypatch.setattr(WorkflowEngine, "_schedule_resume", fake_schedule)

        org, claim = make_claim(db_session)
        service = WorkflowDefinitionService(db_session, org.id)
        definition = service.create(name="Waits a while")
        service.add_step(
            definition.id,
            step_order=1,
            step_type=WorkflowStepType.WAIT,
            name="Cool off",
            configuration={"duration_days": 3},
        )

        execution = run(WorkflowEngine(db_session, org.id).start(definition.id, claim.id))

        assert execution.status.value == "waiting"
        assert scheduled["seconds"] == 3 * 86400
        assert scheduled["execution_id"] == execution.id

    def test_starting_inactive_workflow_raises(self, db_session):
        from app.models.workflow_definition import WorkflowStepType
        from app.workflow_engine.engine import WorkflowEngine
        from app.workflow_engine.service import WorkflowDefinitionService

        org, claim = make_claim(db_session)
        service = WorkflowDefinitionService(db_session, org.id)
        definition = service.create(name="Inactive", is_active=False)
        service.add_step(definition.id, step_order=1, step_type=WorkflowStepType.END, name="Done")

        with pytest.raises(ValueError, match="not active"):
            run(WorkflowEngine(db_session, org.id).start(definition.id, claim.id))


# ---------------------------------------------------------------------------
# API-level smoke tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db_session):
    from app.core.dependencies import get_current_organization
    from app.db.database import get_db
    from app.main import app
    from app.models.user import User, UserRole
    from app.security.dependencies import get_current_user

    org, claim = make_claim(db_session)
    admin = User(
        organization_id=org.id,
        email="admin@atlasdemo.com",
        password_hash="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
    )
    db_session.add(admin)
    db_session.commit()

    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: org.id
    app.dependency_overrides[get_current_user] = lambda: admin

    yield TestClient(app), org, claim

    app.dependency_overrides.clear()


class TestWorkflowDefinitionsAPI:
    def test_create_list_and_add_steps(self, client):
        http, org, claim = client

        created = http.post(
            "/api/v1/workflow-definitions",
            json={"name": "Denial follow-up", "description": "Auto-handle denials"},
        )
        assert created.status_code == 200
        definition_id = created.json()["id"]

        step = http.post(
            f"/api/v1/workflow-definitions/{definition_id}/steps",
            json={"step_order": 1, "step_type": "end", "name": "Finish"},
        )
        assert step.status_code == 200

        listed = http.get("/api/v1/workflow-definitions")
        assert listed.status_code == 200
        assert any(d["id"] == definition_id for d in listed.json())

        detail = http.get(f"/api/v1/workflow-definitions/{definition_id}")
        assert detail.status_code == 200
        assert len(detail.json()["steps"]) == 1

    def test_execute_workflow_and_dashboard_counts(self, client):
        http, org, claim = client

        created = http.post("/api/v1/workflow-definitions", json={"name": "Immediate end"}).json()
        http.post(
            f"/api/v1/workflow-definitions/{created['id']}/steps",
            json={"step_order": 1, "step_type": "end", "name": "Finish"},
        )

        executed = http.post(
            f"/api/v1/workflow-definitions/{created['id']}/execute",
            json={"claim_id": claim.id},
        )
        assert executed.status_code == 200
        assert executed.json()["status"] == "completed"

        dashboard = http.get("/api/v1/workflow-executions/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json()["completed_today"] >= 1

    def test_viewer_cannot_manage_workflows(self, client):
        http, org, claim = client
        from app.db.database import get_db
        from app.main import app
        from app.models.user import User, UserRole
        from app.security.dependencies import get_current_user

        db_session_gen = app.dependency_overrides[get_db]()
        db_session = next(db_session_gen)

        viewer = User(
            organization_id=org.id,
            email="viewer@atlasdemo.com",
            password_hash="x",
            first_name="View",
            last_name="Only",
            role=UserRole.VIEWER,
        )
        db_session.add(viewer)
        db_session.commit()

        app.dependency_overrides[get_current_user] = lambda: viewer
        response = http.post("/api/v1/workflow-definitions", json={"name": "Should be forbidden"})
        assert response.status_code == 403
