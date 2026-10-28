"""
Tests for the Evidence Library (app/documents/): upload, list/search, tag,
download, delete, tenant isolation, and permission gating. Uses the same
TestClient + SQLite in-memory + dependency-override pattern as
test_workflow_engine.py.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401 — registers every model on Base.metadata
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.events.bus import ALL_EVENTS, EventBus
from app.main import app
from app.security.dependencies import get_current_user


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


@pytest.fixture()
def seed(db_session):
    from app.models.claim import Claim
    from app.models.organization import Organization
    from app.models.patient import Patient
    from app.models.payer import Payer
    from app.models.user import User, UserRole

    org = Organization(name="Atlas Demo Clinic", email="org@atlasdemo.com")
    other_org = Organization(name="Other Health System", email="org@otherhealth.com")
    db_session.add_all([org, other_org])
    db_session.flush()

    patient = Patient(
        organization_id=org.id,
        first_name="John",
        last_name="Smith",
        medical_record_number="MRN-001",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(organization_id=org.id, name="Aetna", payer_code="AETNA")
    db_session.add_all([patient, payer])
    db_session.flush()

    claim = Claim(
        organization_id=org.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-0001",
        status="imported",
        billed_amount=1500.00,
        paid_amount=0.00,
        service_date=date(2026, 1, 5),
    )
    db_session.add(claim)

    admin = User(
        organization_id=org.id,
        email="admin@atlasdemo.com",
        password_hash="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
    )
    viewer = User(
        organization_id=org.id,
        email="viewer@atlasdemo.com",
        password_hash="x",
        first_name="View",
        last_name="Only",
        role=UserRole.VIEWER,
    )
    db_session.add_all([admin, viewer])
    db_session.commit()

    return {
        "org": org,
        "other_org": other_org,
        "patient": patient,
        "payer": payer,
        "claim": claim,
        "admin": admin,
        "viewer": viewer,
    }


@pytest.fixture()
def client(db_session, seed):
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: seed["org"].id
    app.dependency_overrides[get_current_user] = lambda: seed["admin"]

    yield TestClient(app)

    app.dependency_overrides.clear()


def as_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


def as_organization(organization_id: int):
    app.dependency_overrides[get_current_organization] = lambda: organization_id


def _upload(
    client,
    claim_id,
    filename="notes.txt",
    content=b"Operative note: patient tolerated procedure well.",
    content_type="text/plain",
    document_type="physician_notes",
):
    return client.post(
        f"/api/v1/claims/{claim_id}/documents",
        files={"file": (filename, content, content_type)},
        data={"document_type": document_type},
    )


def test_upload_document_creates_record_with_extracted_text(client, seed):
    response = _upload(client, seed["claim"].id)
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "notes.txt"
    assert body["document_type"] == "physician_notes"
    assert body["file_size"] > 0
    assert len(body["checksum"]) == 64
    assert "tolerated procedure well" in body["extracted_text"]
    assert body["extraction_status"] == "succeeded"
    assert body["extraction_method"] == "direct_text"
    assert body["extraction_engine"] == "python"
    assert body["tags"] == []


def test_upload_removes_database_invalid_nul_from_extracted_text(client, seed):
    response = _upload(
        client,
        seed["claim"].id,
        filename="utf16-like.txt",
        content=b"P\x00a\x00t\x00i\x00e\x00n\x00t\x00 \x00n\x00o\x00t\x00e\x00",
    )

    assert response.status_code == 200
    assert response.json()["extracted_text"] == "Patient note"


def test_upload_records_scanned_document_ocr_confidence(client, seed, monkeypatch):
    from app.documents.extraction import ExtractionResult

    monkeypatch.setattr(
        "app.documents.service.extraction.extract_document",
        lambda *args, **kwargs: ExtractionResult(
            text="Scanned operative report",
            status="succeeded",
            method="ocr",
            engine="tesseract",
            engine_version="5.3.0",
            confidence=0.91,
        ),
    )

    response = _upload(
        client,
        seed["claim"].id,
        filename="scan.png",
        content=b"representative-scanned-fixture",
        content_type="image/png",
    )

    assert response.status_code == 200
    assert response.json()["extraction_method"] == "ocr"
    assert response.json()["extraction_engine"] == "tesseract"
    assert response.json()["extraction_engine_version"] == "5.3.0"
    assert response.json()["extraction_confidence"] == 0.91


def test_upload_succeeds_when_ocr_is_unavailable(client, seed, monkeypatch):
    from app.documents.extraction import ExtractionResult

    monkeypatch.setattr(
        "app.documents.service.extraction.extract_document",
        lambda *args, **kwargs: ExtractionResult(
            text=None,
            status="unavailable",
            method="ocr",
            engine="tesseract",
            engine_version="unavailable",
        ),
    )

    response = _upload(
        client,
        seed["claim"].id,
        filename="scan.png",
        content=b"representative-scanned-fixture-unavailable",
        content_type="image/png",
    )

    assert response.status_code == 200
    assert response.json()["extracted_text"] is None
    assert response.json()["extraction_status"] == "unavailable"


def test_upload_records_timeline_event(client, seed):
    _upload(client, seed["claim"].id)

    events = client.get(f"/api/v1/claims/{seed['claim'].id}/timeline").json()
    assert any(e["event_type"] == "claim.document_uploaded" for e in events)


def test_upload_records_immutable_audit_entry(client, seed, db_session):
    from app.audit.actions import AuditAction
    from app.models.audit_log import AuditLog

    document_id = _upload(client, seed["claim"].id).json()["id"]

    entry = db_session.query(AuditLog).filter(AuditLog.entity_id == document_id).one()
    assert entry.organization_id == seed["org"].id
    assert entry.user_id == seed["admin"].id
    assert entry.action == AuditAction.DOCUMENT_UPLOADED
    assert entry.metadata_json["after"]["checksum"]


def test_upload_rejects_unsupported_file_type(client, seed):
    response = client.post(
        f"/api/v1/claims/{seed['claim'].id}/documents",
        files={"file": ("malware.exe", b"binary", "application/octet-stream")},
        data={"document_type": "other"},
    )
    assert response.status_code == 400


def test_upload_nonexistent_claim_returns_404(client, seed):
    response = _upload(client, 99999)
    assert response.status_code == 404


def test_upload_rejects_duplicate_content_for_same_claim(client, seed):
    assert _upload(client, seed["claim"].id).status_code == 200

    response = _upload(client, seed["claim"].id, filename="duplicate.txt")

    assert response.status_code == 409


def test_list_documents_returns_only_this_claims_documents(client, seed):
    _upload(client, seed["claim"].id, filename="a.txt", content=b"first")
    _upload(client, seed["claim"].id, filename="b.txt", content=b"second")

    response = client.get(f"/api/v1/claims/{seed['claim'].id}/documents")
    assert response.status_code == 200
    filenames = {d["filename"] for d in response.json()}
    assert filenames == {"a.txt", "b.txt"}


def test_search_documents_by_extracted_text(client, seed):
    _upload(client, seed["claim"].id, filename="op_report.txt", content=b"Operative report content")
    _upload(client, seed["claim"].id, filename="lab.txt", content=b"Lab results content")

    response = client.get(
        f"/api/v1/claims/{seed['claim'].id}/documents", params={"search": "Operative"}
    )
    results = response.json()
    assert len(results) == 1
    assert results[0]["filename"] == "op_report.txt"


def test_update_document_tags(client, seed):
    document_id = _upload(client, seed["claim"].id).json()["id"]

    response = client.patch(
        f"/api/v1/documents/{document_id}", json={"tags": ["urgent", "reviewed"]}
    )
    assert response.status_code == 200
    assert response.json()["tags"] == ["urgent", "reviewed"]


def test_classify_document_records_confidence_and_pending_review(client, seed, monkeypatch):
    async def _classification_result(*args, **kwargs):
        return {
            "document_type": "operative_report",
            "confidence": 0.94,
        }

    monkeypatch.setattr("app.documents.service.gateway.generate_json", _classification_result)
    document_id = _upload(client, seed["claim"].id).json()["id"]

    response = client.post(f"/api/v1/documents/{document_id}/classify")

    assert response.status_code == 200
    assert response.json()["predicted_document_type"] == "operative_report"
    assert response.json()["classification_confidence"] == 0.94
    assert response.json()["classification_review_status"] == "pending"


def test_classification_can_be_human_corrected_and_audited(client, seed, db_session, monkeypatch):
    from app.audit.actions import AuditAction
    from app.models.audit_log import AuditLog

    async def _classification_result(*args, **kwargs):
        return {"document_type": "operative_report", "confidence": 0.74}

    monkeypatch.setattr("app.documents.service.gateway.generate_json", _classification_result)
    document_id = _upload(client, seed["claim"].id).json()["id"]
    assert client.post(f"/api/v1/documents/{document_id}/classify").status_code == 200

    response = client.post(
        f"/api/v1/documents/{document_id}/classification-review",
        json={
            "document_type": "physician_notes",
            "reason": "Reviewer confirmed this is a progress note.",
        },
    )

    assert response.status_code == 200
    assert response.json()["document_type"] == "physician_notes"
    assert response.json()["predicted_document_type"] == "operative_report"
    assert response.json()["classification_review_status"] == "corrected"
    assert response.json()["classification_reviewed_by_id"] == seed["admin"].id
    entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == AuditAction.DOCUMENT_CLASSIFICATION_REVIEWED)
        .one()
    )
    assert entry.organization_id == seed["org"].id
    assert entry.reason == "Reviewer confirmed this is a progress note."


def test_classification_is_tenant_scoped(client, seed, monkeypatch):
    async def _classification_result(*args, **kwargs):
        return {"document_type": "physician_notes", "confidence": 0.91}

    monkeypatch.setattr("app.documents.service.gateway.generate_json", _classification_result)
    document_id = _upload(client, seed["claim"].id).json()["id"]

    as_organization(seed["other_org"].id)

    assert client.post(f"/api/v1/documents/{document_id}/classify").status_code == 404


def test_classification_provider_failure_is_retryable(client, seed, monkeypatch):
    from app.ai.exceptions import AIProviderError

    async def _provider_failure(*args, **kwargs):
        raise AIProviderError("offline", task="document_classification", provider="openai")

    monkeypatch.setattr("app.documents.service.gateway.generate_json", _provider_failure)
    document_id = _upload(client, seed["claim"].id).json()["id"]

    response = client.post(f"/api/v1/documents/{document_id}/classify")

    assert response.status_code == 503
    assert response.json()["detail"] == "Document classification provider is unavailable"


def test_download_document_returns_file_content(client, seed):
    content = b"Operative note: patient tolerated procedure well."
    document_id = _upload(client, seed["claim"].id, content=content).json()["id"]

    response = client.get(f"/api/v1/documents/{document_id}/download")
    assert response.status_code == 200
    assert response.content == content


def test_delete_document_removes_it_from_list(client, seed):
    document_id = _upload(client, seed["claim"].id).json()["id"]

    response = client.delete(f"/api/v1/documents/{document_id}")
    assert response.status_code == 204

    remaining = client.get(f"/api/v1/claims/{seed['claim'].id}/documents").json()
    assert remaining == []


def test_documents_are_tenant_isolated(client, seed):
    document_id = _upload(client, seed["claim"].id).json()["id"]

    as_organization(seed["other_org"].id)
    response = client.get(f"/api/v1/documents/{document_id}")
    assert response.status_code == 404

    response = client.delete(f"/api/v1/documents/{document_id}")
    assert response.status_code == 404


def test_patient_claim_document_workflow_is_tenant_scoped(client, seed, monkeypatch):
    test_bus = EventBus()
    monkeypatch.setattr("app.events.publisher.event_bus", test_bus)
    events = []
    test_bus.subscribe(
        ALL_EVENTS,
        lambda event_type, payload, organization_id: events.append(
            (event_type, payload, organization_id)
        ),
    )

    patient_response = client.post(
        "/api/v1/patients",
        json={
            "first_name": "Workflow",
            "last_name": "Patient",
            "medical_record_number": "MRN-DOC-WORKFLOW",
            "date_of_birth": "1984-03-12",
        },
    )
    assert patient_response.status_code == 201

    claim_response = client.post(
        "/api/v1/claims/",
        json={
            "patient_id": patient_response.json()["id"],
            "payer_id": seed["payer"].id,
            "claim_number": "CLM-DOC-WORKFLOW",
            "billed_amount": 125000,
            "paid_amount": 0,
            "service_date": "2026-08-01",
        },
    )
    assert claim_response.status_code == 200
    claim_id = claim_response.json()["id"]

    document_response = _upload(
        client,
        claim_id,
        filename="workflow-evidence.txt",
        content=b"Authorization and clinical evidence for submission.",
    )
    assert document_response.status_code == 200
    document_id = document_response.json()["id"]
    assert client.get(f"/api/v1/claims/{claim_id}/documents").json()[0]["id"] == document_id

    assert [event_type for event_type, _, _ in events] == [
        "patient.created",
        "claim.created",
        "workflow.transitioned",
        "document.uploaded",
    ]
    assert [organization_id for _, _, organization_id in events] == [seed["org"].id] * 4
    assert events[0][1]["patient_id"] == patient_response.json()["id"]
    assert events[1][1]["claim_id"] == claim_id
    assert events[2][1]["claim_id"] == claim_id
    assert events[2][1]["from"] == "imported"
    assert events[2][1]["to"] == "validated"
    assert events[3][1]["claim_id"] == claim_id
    assert events[3][1]["document_id"] == document_id
    assert all(payload["correlation_id"] for _, payload, _ in events)

    as_organization(seed["other_org"].id)
    assert client.get(f"/api/v1/claims/{claim_id}/documents").status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}").status_code == 404


def test_viewer_role_cannot_upload_documents(client, seed):
    as_user(seed["viewer"])

    response = _upload(client, seed["claim"].id)
    assert response.status_code == 403


def test_viewer_role_can_list_documents(client, seed):
    _upload(client, seed["claim"].id)
    as_user(seed["viewer"])

    response = client.get(f"/api/v1/claims/{seed['claim'].id}/documents")
    assert response.status_code == 200
