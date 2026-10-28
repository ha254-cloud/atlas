from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models as _models  # noqa: F401
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.main import app
from app.models.claim import Claim
from app.models.claim_analysis import AnalysisStatus, ClaimAnalysis
from app.models.claim_event import ClaimEvent, ClaimEventType
from app.models.import_job import ImportJob
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.user import User, UserRole
from app.repositories.claim_analysis import ClaimAnalysisRepository
from app.schemas.appeal import AppealResult
from app.schemas.claim_analysis import ClaimAnalysisResult
from app.security.dependencies import get_current_user

VALID_RESULT = ClaimAnalysisResult(
    risk_score=91,
    recovery_probability=0.88,
    priority="high",
    confidence=0.94,
    recommended_action="Generate an appeal with the authorization record.",
    summary="The denial is likely recoverable with supporting documentation.",
    required_documents=["Operative Report", "Authorization"],
)


@pytest.fixture()
def db_engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'atlas-test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def session_factory(db_engine):
    return sessionmaker(bind=db_engine)


@pytest.fixture()
def db_session(session_factory):
    session = session_factory()
    yield session
    session.close()


@pytest.fixture()
def seed(db_session):
    organization = Organization(name="Atlas Test Clinic", email="atlas@example.com")
    db_session.add(organization)
    db_session.flush()

    patient = Patient(
        organization_id=organization.id,
        first_name="Jane",
        last_name="Doe",
        medical_record_number="MRN-PIPELINE-1",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(
        organization_id=organization.id,
        name="Test Health Plan",
        payer_code="TEST",
    )
    user = User(
        organization_id=organization.id,
        email="admin@example.com",
        password_hash="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
    )
    db_session.add_all([patient, payer, user])
    db_session.flush()

    claim = Claim(
        organization_id=organization.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-AI-PIPELINE-1",
        status="denied",
        billed_amount=Decimal("2500.00"),
        paid_amount=Decimal("0.00"),
        service_date=date(2026, 7, 1),
    )
    db_session.add(claim)
    db_session.commit()
    return {"organization": organization, "user": user, "claim": claim}


@pytest.fixture()
def client(db_session, seed):
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: seed["organization"].id
    app.dependency_overrides[get_current_user] = lambda: seed["user"]
    yield TestClient(app)
    app.dependency_overrides.clear()


def _patch_task_dependencies(monkeypatch, session_factory, service_class):
    import app.tasks.ai_analysis as task_module

    def _get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(task_module, "get_db", _get_db)
    monkeypatch.setattr(task_module, "AIAnalysisService", service_class)
    monkeypatch.setattr(
        task_module,
        "EventPublisher",
        lambda: type(
            "Publisher",
            (),
            {"publish": lambda self, event_type, payload: None},
        )(),
    )


def test_repository_persists_validated_analysis(db_session, seed):
    repository = ClaimAnalysisRepository(db_session, seed["organization"].id)

    analysis = repository.save(
        claim_id=seed["claim"].id,
        result=VALID_RESULT,
        model="gpt-test",
        prompt_version="1.0",
    )

    assert analysis.analysis_status == AnalysisStatus.COMPLETED
    assert analysis.risk_score == Decimal("91.00")
    assert analysis.recovery_probability == Decimal("88.00")
    assert analysis.confidence_score == Decimal("94.00")
    assert analysis.required_documents == ["Operative Report", "Authorization"]
    assert analysis.model == "gpt-test"
    assert analysis.prompt_version == "1.0"
    assert repository.get_latest(seed["claim"].id).id == analysis.id
    assert repository.list_by_claim(seed["claim"].id) == [analysis]


def test_worker_saves_analysis_records_event_and_publishes(
    monkeypatch, session_factory, db_session, seed
):
    import app.tasks.ai_analysis as task_module

    observed_context = {}

    class StubService:
        model = "gpt-test"
        prompt_version = "1.0"

        async def analyze(self, claim):
            from app.ai.cost_tracking import current_context

            observed_context.update(current_context())
            return VALID_RESULT

    published = []
    _patch_task_dependencies(monkeypatch, session_factory, StubService)
    monkeypatch.setattr(
        task_module,
        "EventPublisher",
        lambda: type(
            "Publisher",
            (),
            {"publish": lambda self, event_type, payload: published.append((event_type, payload))},
        )(),
    )

    analysis_id = task_module.analyze_claim_task.run(
        seed["claim"].id,
        seed["organization"].id,
    )

    db_session.expire_all()
    analysis = db_session.get(ClaimAnalysis, analysis_id)
    event = (
        db_session.query(ClaimEvent)
        .filter(
            ClaimEvent.claim_id == seed["claim"].id,
            ClaimEvent.event_type == ClaimEventType.ANALYZED,
        )
        .one()
    )
    assert analysis.analysis_status == AnalysisStatus.COMPLETED
    assert event.event_metadata == {
        "risk_score": 91,
        "priority": "HIGH",
        "confidence": 0.94,
    }
    assert observed_context == {
        "organization_id": seed["organization"].id,
        "claim_id": seed["claim"].id,
    }
    assert published[0][1]["analysis_id"] == analysis.id


def test_worker_marks_failed_and_records_terminal_retry(
    monkeypatch, session_factory, db_session, seed
):
    import app.tasks.ai_analysis as task_module

    class FailingService:
        model = "gpt-test"
        prompt_version = "1.0"

        async def analyze(self, claim):
            raise RuntimeError("provider unavailable")

    _patch_task_dependencies(monkeypatch, session_factory, FailingService)
    task_module.analyze_claim_task.push_request(retries=3)
    try:
        with pytest.raises(RuntimeError):
            task_module.analyze_claim_task.run(
                seed["claim"].id,
                seed["organization"].id,
            )
    finally:
        task_module.analyze_claim_task.pop_request()

    db_session.expire_all()
    analysis = (
        db_session.query(ClaimAnalysis).filter(ClaimAnalysis.claim_id == seed["claim"].id).one()
    )
    event = (
        db_session.query(ClaimEvent)
        .filter(
            ClaimEvent.claim_id == seed["claim"].id,
            ClaimEvent.event_type == ClaimEventType.AI_ANALYSIS_FAILED,
        )
        .one()
    )
    assert analysis.analysis_status == AnalysisStatus.FAILED
    assert event.event_metadata["error_type"] == "RuntimeError"
    assert event.event_metadata["retry_count"] == 3
    assert task_module.analyze_claim_task.max_retries == 3


def test_analysis_endpoint_returns_stored_result(client, db_session, seed):
    ClaimAnalysisRepository(db_session, seed["organization"].id).save(
        claim_id=seed["claim"].id,
        result=VALID_RESULT,
        model="gpt-test",
        prompt_version="1.0",
    )

    response = client.get(f"/api/v1/claims/{seed['claim'].id}/analysis")

    assert response.status_code == 200
    assert response.json() == {
        "status": "completed",
        "risk_score": 91.0,
        "priority": "HIGH",
        "confidence": 0.94,
        "recovery_probability": 0.88,
        "recommended_action": "Generate an appeal with the authorization record.",
        "summary": "The denial is likely recoverable with supporting documentation.",
        "required_documents": ["Operative Report", "Authorization"],
    }


def test_csv_upload_runs_analysis_pipeline(monkeypatch, client, session_factory, db_session, seed):
    import app.tasks.generate_appeal as appeal_task_module
    from app.workers.tasks import analyze_claim_task, generate_appeal_task, process_import

    class StubService:
        model = "gpt-test"
        prompt_version = "1.0"

        async def analyze(self, claim):
            return VALID_RESULT

    class StubAppealService:
        model = "gpt-test"
        prompt_version = "1.0"
        generation = 0

        async def generate(self, claim):
            StubAppealService.generation += 1
            return AppealResult(
                title="Claim reconsideration request",
                letter=(
                    f"Please reconsider claim {claim.claim_number}. The supplied "
                    "record supports reversal of the denial and reprocessing. "
                    f"Draft {StubAppealService.generation}."
                ),
                confidence=0.92,
                required_documents=["Medical record"],
                missing_documents=[],
                references=[f"Claim {claim.claim_number}"],
            )

    _patch_task_dependencies(monkeypatch, session_factory, StubService)

    def _get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr("app.db.database.get_db", _get_db)
    monkeypatch.setattr(appeal_task_module, "get_db", _get_db)
    monkeypatch.setattr(
        appeal_task_module,
        "AppealGenerationService",
        StubAppealService,
    )
    published_appeals = []
    monkeypatch.setattr(
        appeal_task_module,
        "EventPublisher",
        lambda: type(
            "Publisher",
            (),
            {
                "publish": lambda self, event_type, payload: published_appeals.append(
                    (event_type, payload)
                )
            },
        )(),
    )
    monkeypatch.setattr(
        "app.appeals.service.EventPublisher",
        lambda: type(
            "Publisher",
            (),
            {"publish": lambda self, event_type, payload: None},
        )(),
    )
    monkeypatch.setattr(
        "app.imports.import_service.process_import.delay",
        lambda job_id: process_import.run(job_id),
    )
    task_errors = []

    def _run_analysis(claim_id, organization_id):
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(analyze_claim_task.run, claim_id, organization_id).result()
        except Exception as exc:
            task_errors.append(exc)
            raise

    monkeypatch.setattr(
        "app.workers.tasks.analyze_claim_task.delay",
        _run_analysis,
    )

    def _run_appeal(claim_id, organization_id, appeal_id, requested_by):
        return generate_appeal_task.run(
            claim_id,
            organization_id,
            appeal_id,
            requested_by,
        )

    monkeypatch.setattr(
        "app.claims.router.generate_appeal_task.delay",
        _run_appeal,
    )

    csv_content = (
        "claim_number,medical_record_number,payer_code,billed_amount,paid_amount,"
        "service_date,status,patient_first_name,patient_last_name\n"
        "CLM-UPLOAD-AI-1,MRN-UPLOAD-AI-1,TEST,3200.00,0.00,2026-07-10,"
        "denied,Amina,Otieno\n"
    )
    response = client.post(
        "/api/v1/uploads/claims",
        files={"file": ("claims.csv", csv_content, "text/csv")},
    )

    try:
        assert response.status_code == 200
        db_session.expire_all()
        import_job = db_session.get(ImportJob, response.json()["job_id"])
        assert not import_job.error_details, import_job.error_details
        assert not task_errors, task_errors
        claim = db_session.query(Claim).filter(Claim.claim_number == "CLM-UPLOAD-AI-1").one()
        analysis = db_session.query(ClaimAnalysis).filter(ClaimAnalysis.claim_id == claim.id).one()
        assert analysis.analysis_status == AnalysisStatus.COMPLETED

        api_response = client.get(f"/api/v1/claims/{claim.id}/analysis")
        assert api_response.status_code == 200
        assert api_response.json()["risk_score"] == 91.0

        generate_response = client.post(f"/api/v1/claims/{claim.id}/appeals/generate")
        assert generate_response.status_code == 202
        appeal_id = generate_response.json()["id"]

        appeal_response = client.get(f"/api/v1/appeals/{appeal_id}")
        assert appeal_response.status_code == 200
        assert appeal_response.json()["title"] == "Claim reconsideration request"
        assert appeal_response.json()["version"] == 1
        assert appeal_response.json()["analysis_id"] == analysis.id
        assert published_appeals[0][1]["appeal_id"] == appeal_id

        regenerate_response = client.post(f"/api/v1/claims/{claim.id}/appeals/generate")
        assert regenerate_response.status_code == 202
        assert regenerate_response.json()["id"] == appeal_id
        regenerated = client.get(f"/api/v1/appeals/{appeal_id}")
        assert regenerated.json()["version"] == 2

        from app.models.appeal_version import AppealVersion

        db_session.expire_all()
        versions = (
            db_session.query(AppealVersion)
            .filter(AppealVersion.appeal_id == appeal_id)
            .order_by(AppealVersion.version_number)
            .all()
        )
        assert [version.version_number for version in versions] == [1, 2]
        assert versions[0].appeal_text.endswith("Draft 1.")
        assert versions[1].appeal_text.endswith("Draft 2.")

        review_response = client.post(f"/api/v1/appeals/{appeal_id}/review")
        assert review_response.status_code == 200
        approve_response = client.post(f"/api/v1/appeals/{appeal_id}/approve")
        assert approve_response.status_code == 200
        assert approve_response.json()["approved_by"] == seed["user"].id
        assert approve_response.json()["approved_at"] is not None
        assert approve_response.json()["pdf_document_id"] is not None

        pdf_response = client.get(f"/api/v1/appeals/{appeal_id}/pdf")
        assert pdf_response.status_code == 200
        assert pdf_response.headers["content-type"] == "application/pdf"
        assert pdf_response.content.startswith(b"%PDF-")
        assert b"Claim reconsideration request" in pdf_response.content
    finally:
        from app.models.appeal import Appeal

        db_session.expire_all()
        appeal = (
            db_session.query(Appeal).filter(Appeal.claim_id == claim.id).first()
            if "claim" in locals()
            else None
        )
        if appeal is not None and appeal.pdf_document is not None:
            Path(appeal.pdf_document.storage_path).unlink(missing_ok=True)
        uploaded_file = Path(response.json().get("filename", ""))
        if uploaded_file.is_file():
            uploaded_file.unlink()
