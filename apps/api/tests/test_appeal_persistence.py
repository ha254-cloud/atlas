from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401
from app.appeals.repository import AppealRepository
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.main import app
from app.models.appeal import Appeal, AppealStatus
from app.models.audit_log import AuditLog
from app.models.claim import Claim
from app.models.claim_analysis import AnalysisStatus, ClaimAnalysis
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.user import User, UserRole
from app.security.dependencies import get_current_user


@pytest.fixture()
def persistence_context():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    organization = Organization(name="Appeal Test Org", email="appeals@example.com")
    db.add(organization)
    db.flush()
    patient = Patient(
        organization_id=organization.id,
        first_name="Ada",
        last_name="Lovelace",
        medical_record_number="MRN-APPEAL-1",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(
        organization_id=organization.id,
        name="Appeal Test Payer",
        payer_code="ATP",
    )
    user = User(
        organization_id=organization.id,
        email="reviewer@example.com",
        password_hash="x",
        first_name="Review",
        last_name="User",
        role=UserRole.ADMIN,
    )
    db.add_all([patient, payer, user])
    db.flush()
    claim = Claim(
        organization_id=organization.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-APPEAL-1",
        status="denied",
        billed_amount=Decimal("1250.00"),
        paid_amount=Decimal("0.00"),
        service_date=date(2026, 7, 1),
    )
    db.add(claim)
    db.flush()
    analysis = ClaimAnalysis(
        organization_id=organization.id,
        claim_id=claim.id,
        analysis_status=AnalysisStatus.COMPLETED,
    )
    db.add(analysis)
    db.commit()

    yield {
        "db": db,
        "organization": organization,
        "claim": claim,
        "analysis": analysis,
        "user": user,
    }

    app.dependency_overrides.clear()
    db.close()


def _appeal(context, title="Initial Appeal"):
    return Appeal(
        organization_id=context["organization"].id,
        claim_id=context["claim"].id,
        analysis_id=context["analysis"].id,
        status=AppealStatus.DRAFT,
        title=title,
        appeal_text="Please reconsider this denied claim.",
        confidence=Decimal("0.9000"),
        required_documents=["Medical record"],
        missing_documents=[],
        references=["Claim CLM-APPEAL-1"],
        generated_by=str(context["user"].id),
    )


def test_repository_create_update_approve_history_latest(persistence_context):
    db = persistence_context["db"]
    repo = AppealRepository(db, persistence_context["organization"].id)

    first = repo.create(_appeal(persistence_context))
    db.commit()
    second = repo.create(_appeal(persistence_context, title="Second Appeal"))
    db.commit()

    updated = repo.update(first.id, title="Updated Appeal")
    approved = repo.approve(first.id, persistence_context["user"].id)
    db.commit()

    assert updated.title == "Updated Appeal"
    assert approved.status == AppealStatus.APPROVED
    assert approved.approved_by == persistence_context["user"].id
    assert approved.approved_at is not None
    assert repo.latest(persistence_context["claim"].id).id == second.id
    assert [appeal.id for appeal in repo.history(persistence_context["claim"].id)] == [
        second.id,
        first.id,
    ]
    assert first in persistence_context["claim"].appeals
    assert first in persistence_context["analysis"].appeals


def test_repository_delete_draft_only(persistence_context):
    db = persistence_context["db"]
    repo = AppealRepository(db, persistence_context["organization"].id)
    draft = repo.create(_appeal(persistence_context))
    approved = repo.create(_appeal(persistence_context, title="Approved"))
    approved.status = AppealStatus.APPROVED
    db.commit()

    assert repo.delete_draft(draft.id) is True
    assert repo.delete_draft(approved.id) is False
    db.commit()
    assert repo.get(draft.id) is None
    assert repo.get(approved.id) is not None


@pytest.fixture()
def client(persistence_context):
    db = persistence_context["db"]

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: (
        persistence_context["organization"].id
    )
    app.dependency_overrides[get_current_user] = lambda: persistence_context["user"]
    return TestClient(app)


def test_appeal_crud_api(client, persistence_context):
    claim_id = persistence_context["claim"].id
    analysis_id = persistence_context["analysis"].id
    create_response = client.post(
        f"/api/v1/claims/{claim_id}/appeals",
        json={
            "claim_id": claim_id,
            "analysis_id": analysis_id,
            "title": "Coverage Appeal",
            "body": "Please reconsider coverage for this claim.",
            "confidence": 0.91,
            "required_documents": ["Medical record"],
            "missing_documents": [],
            "references": ["Claim CLM-APPEAL-1"],
        },
    )
    assert create_response.status_code == 201
    appeal = create_response.json()
    assert appeal["body"] == "Please reconsider coverage for this claim."
    assert appeal["version"] == 1
    assert appeal["analysis_id"] == analysis_id

    list_response = client.get(f"/api/v1/claims/{claim_id}/appeals")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [appeal["id"]]

    get_response = client.get(f"/api/v1/appeals/{appeal['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Coverage Appeal"

    update_response = client.put(
        f"/api/v1/appeals/{appeal['id']}",
        json={"title": "Updated Coverage Appeal", "body": "Updated letter."},
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Updated Coverage Appeal"
    assert update_response.json()["body"] == "Updated letter."
    assert update_response.json()["version"] == 2

    status_response = client.put(
        f"/api/v1/appeals/{appeal['id']}",
        json={"status": "submitted"},
    )
    assert status_response.status_code == 409

    delete_response = client.delete(f"/api/v1/appeals/{appeal['id']}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/v1/appeals/{appeal['id']}").status_code == 404


def test_patch_appeal_persists_sections_and_audit(client, persistence_context):
    db = persistence_context["db"]
    appeal = AppealRepository(db, persistence_context["organization"].id).create(
        _appeal(persistence_context)
    )
    db.commit()

    response = client.patch(
        f"/api/v1/appeals/{appeal.id}",
        json={
            "appeal_text": "Reviewer-edited appeal.",
            "sections": {"introduction": "Reviewer-edited introduction."},
        },
    )

    assert response.status_code == 200
    assert response.json()["appeal_text"] == "Reviewer-edited appeal."
    assert response.json()["sections"] == {"introduction": "Reviewer-edited introduction."}
    assert response.json()["current_version"] == 2
    audit = db.query(AuditLog).filter(AuditLog.action == "appeal.edited").one()
    assert audit.organization_id == persistence_context["organization"].id
    assert audit.user_id == persistence_context["user"].id
    assert audit.before_state["version"] == 1
    assert audit.after_state["version"] == 2


def test_patch_appeal_rejects_approved_appeal(client, persistence_context):
    db = persistence_context["db"]
    appeal = _appeal(persistence_context)
    appeal.status = AppealStatus.APPROVED
    AppealRepository(db, persistence_context["organization"].id).create(appeal)
    db.commit()

    response = client.patch(
        f"/api/v1/appeals/{appeal.id}",
        json={"appeal_text": "Post-approval edit."},
    )

    assert response.status_code == 409
    db.refresh(appeal)
    assert appeal.appeal_text == "Please reconsider this denied claim."
    assert appeal.current_version == 1


def test_create_rejects_analysis_from_another_claim(client, persistence_context):
    response = client.post(
        f"/api/v1/claims/{persistence_context['claim'].id}/appeals",
        json={
            "claim_id": persistence_context["claim"].id,
            "analysis_id": 999999,
            "body": "Appeal body",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Claim analysis not found"
