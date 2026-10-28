from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.main import app
from app.models.claim import Claim
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.user import User, UserRole
from app.security.dependencies import get_current_user
from app.tasks.models import Task, TaskActivity, TaskNotification, TaskStatus, TaskType
from app.tasks.priority import calculate_priority_score
from app.tasks.scheduler import run_task_sla_sweep
from app.tasks.service import TaskService


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _organization(db, suffix: str) -> tuple[Organization, Patient, Payer]:
    organization = Organization(
        name=f"Kenya Hospital {suffix}",
        email=f"tasks-{suffix.lower()}@atlas.test",
        currency="KES",
        country="KE",
        settings={
            "task_intelligence": {
                "payer_sla_days": {"JUBILEE": 21},
                "payer_skill_map": {},
                "escalation_after_days": [0, 14, 29],
            }
        },
    )
    db.add(organization)
    db.flush()
    patient = Patient(
        organization_id=organization.id,
        first_name="Amina",
        last_name="Wanjiku",
        medical_record_number=f"MRN-TASK-{suffix}",
        date_of_birth=date(1985, 1, 1),
    )
    payer = Payer(organization_id=organization.id, name="Jubilee", payer_code=f"JUBILEE-{suffix}")
    db.add_all([patient, payer])
    db.flush()
    return organization, patient, payer


def _user(db, organization_id: int, suffix: str, role: UserRole) -> User:
    user = User(
        organization_id=organization_id,
        email=f"{suffix.lower()}@atlas.test",
        password_hash="not-used",
        first_name=suffix,
        last_name="Officer",
        role=role,
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def _claim(db, organization: Organization, patient: Patient, payer: Payer, suffix: str) -> Claim:
    claim = Claim(
        organization_id=organization.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number=f"CLM-TASK-{suffix}",
        status="analyzed",
        billed_amount=Decimal("850000.00"),
        paid_amount=Decimal("0.00"),
        service_date=date.today() - timedelta(days=67),
        recovery_probability=Decimal("96.00"),
    )
    db.add(claim)
    db.flush()
    return claim


def test_priority_example_scores_99():
    assert (
        calculate_priority_score(
            billed_amount=Decimal("850000"),
            recovery_probability=Decimal("96"),
            service_date=date.today() - timedelta(days=67),
        )
        == 99
    )


def test_task_creation_assigns_least_loaded_and_is_idempotent(db):
    organization, patient, payer = _organization(db, "ONE")
    jane = _user(db, organization.id, "Jane", UserRole.REVENUE_ANALYST)
    peter = _user(db, organization.id, "Peter", UserRole.REVENUE_ANALYST)
    claim = _claim(db, organization, patient, payer, "ONE")
    existing_claim = _claim(db, organization, patient, payer, "JANE")
    db.add(
        Task(
            organization_id=organization.id,
            claim_id=existing_claim.id,
            payer_id=payer.id,
            assigned_to=jane.id,
            department="CLAIMS",
            priority_score=50,
            task_type=TaskType.REVIEW_CLAIM,
            status=TaskStatus.ASSIGNED,
            due_date=datetime.utcnow() + timedelta(days=1),
        )
    )
    db.commit()

    service = TaskService(db, organization.id)
    task = service.create_for_claim(claim.id, TaskType.REVIEW_CLAIM, reason="AI analysis completed")
    duplicate = service.create_for_claim(claim.id, TaskType.REVIEW_CLAIM, reason="Duplicate event")

    assert task.id == duplicate.id
    assert task.assigned_to == peter.id
    assert task.priority_score == 99
    assert task.status == TaskStatus.ASSIGNED
    assert db.query(Task).filter(Task.claim_id == claim.id).count() == 1
    assert db.query(TaskNotification).filter(TaskNotification.recipient_id == peter.id).count() == 1
    assert db.query(TaskActivity).filter(TaskActivity.task_id == task.id).count() == 1


def test_completion_creates_next_task_and_rejects_cross_tenant_actor(db):
    organization, patient, payer = _organization(db, "ONE")
    officer = _user(db, organization.id, "Jane", UserRole.REVENUE_ANALYST)
    claim = _claim(db, organization, patient, payer, "ONE")
    other_organization, _, _ = _organization(db, "TWO")
    outsider = _user(db, other_organization.id, "Outsider", UserRole.REVENUE_ANALYST)
    task = TaskService(db, organization.id).create_for_claim(
        claim.id, TaskType.REVIEW_CLAIM, assigned_to=officer.id, reason="Create review task"
    )

    with pytest.raises(Exception) as exc_info:
        TaskService(db, organization.id).transition(
            task.id, TaskStatus.COMPLETED, actor=outsider, reason="Cross tenant attempt"
        )
    assert getattr(exc_info.value, "status_code", None) == 403

    service = TaskService(db, organization.id)
    service.transition(task.id, TaskStatus.IN_PROGRESS, actor=officer, reason="Review started")
    completed = service.transition(
        task.id, TaskStatus.COMPLETED, actor=officer, reason="Review finished"
    )

    assert completed.completed_at is not None
    next_task = (
        db.query(Task)
        .filter(Task.claim_id == claim.id, Task.task_type == TaskType.GENERATE_APPEAL)
        .one()
    )
    assert next_task.id != task.id
    assert db.query(TaskActivity).filter(TaskActivity.task_id == task.id).count() == 3


def test_sla_sweep_escalates_once_and_notifies_manager(db):
    organization, patient, payer = _organization(db, "ONE")
    officer = _user(db, organization.id, "Jane", UserRole.REVENUE_ANALYST)
    manager = _user(db, organization.id, "Manager", UserRole.MANAGER)
    claim = _claim(db, organization, patient, payer, "ONE")
    task = TaskService(db, organization.id).create_for_claim(
        claim.id,
        TaskType.REVIEW_CLAIM,
        assigned_to=officer.id,
        reason="Create overdue task",
        due_date=datetime.utcnow() - timedelta(days=1),
    )

    first = run_task_sla_sweep(db, organization.id)
    second = run_task_sla_sweep(db, organization.id)
    db.refresh(task)

    assert first == [task.id]
    assert second == []
    assert task.status == TaskStatus.OVERDUE
    assert task.escalation_level == 1
    assert (
        db.query(TaskNotification)
        .filter(
            TaskNotification.task_id == task.id,
            TaskNotification.recipient_id == manager.id,
            TaskNotification.notification_type == "task.escalated",
        )
        .count()
        == 1
    )


def test_task_queue_api_is_authenticated_and_tenant_scoped(db):
    organization, patient, payer = _organization(db, "ONE")
    officer = _user(db, organization.id, "Jane", UserRole.REVENUE_ANALYST)
    claim = _claim(db, organization, patient, payer, "ONE")
    TaskService(db, organization.id).create_for_claim(
        claim.id, TaskType.REVIEW_CLAIM, assigned_to=officer.id, reason="Queue test"
    )
    other_organization, other_patient, other_payer = _organization(db, "TWO")
    other_officer = _user(db, other_organization.id, "Peter", UserRole.REVENUE_ANALYST)
    other_claim = _claim(db, other_organization, other_patient, other_payer, "TWO")
    TaskService(db, other_organization.id).create_for_claim(
        other_claim.id, TaskType.REVIEW_CLAIM, assigned_to=other_officer.id, reason="Other tenant"
    )

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: officer
    app.dependency_overrides[get_current_organization] = lambda: organization.id
    try:
        response = TestClient(app).get("/api/v1/tasks/queue")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["items"][0]["claim_id"] == claim.id

    unauthenticated = TestClient(app).get("/api/v1/tasks/queue")
    assert unauthenticated.status_code == 401
