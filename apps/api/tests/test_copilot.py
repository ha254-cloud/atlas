from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register all tables
from app.copilot.service import CopilotService
from app.core.config import settings
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.main import app
from app.models.claim import Claim, ClaimPriority
from app.models.denial import Denial, DenialType
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.models.user import User, UserRole
from app.security.dependencies import get_current_user


@pytest.fixture
def db():
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


@pytest.fixture
def client(db, seeded):
    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: seeded["org"].id
    app.dependency_overrides[get_current_user] = lambda: seeded["manager"]
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(db):
    org = Organization(
        name="Atlas Health", slug="atlas-health", email="atlas@test.com", status="active"
    )
    other_org = Organization(
        name="Other Health", slug="other-health", email="other@test.com", status="active"
    )
    db.add_all([org, other_org])
    db.flush()
    manager = User(
        organization_id=org.id,
        email="manager@atlas.test",
        password_hash="x",
        first_name="Morgan",
        last_name="Manager",
        role=UserRole.MANAGER,
        is_active=True,
    )
    viewer = User(
        organization_id=org.id,
        email="viewer@atlas.test",
        password_hash="x",
        first_name="Vera",
        last_name="Viewer",
        role=UserRole.VIEWER,
        is_active=True,
    )
    sarah = User(
        organization_id=org.id,
        email="sarah@atlas.test",
        password_hash="x",
        first_name="Sarah",
        last_name="Lee",
        role=UserRole.REVENUE_ANALYST,
        is_active=True,
    )
    db.add_all([manager, viewer, sarah])
    db.flush()
    patient = Patient(
        organization_id=org.id,
        first_name="Jane",
        last_name="Doe",
        medical_record_number="MRN-COPILOT",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(organization_id=org.id, name="Blue Cross", payer_code="BCBS")
    db.add_all([patient, payer])
    db.flush()
    claims = []
    for index, amount in enumerate([Decimal("75000"), Decimal("30000")], start=1):
        claim = Claim(
            organization_id=org.id,
            patient_id=patient.id,
            payer_id=payer.id,
            claim_number=f"CLM-COP-{index}",
            status="denied",
            billed_amount=amount,
            paid_amount=Decimal("0"),
            service_date=date.today() - timedelta(days=20),
            provider="Cardiology Associates",
            priority=ClaimPriority.HIGH,
        )
        db.add(claim)
        db.flush()
        db.add(
            RecoveryCase(
                organization_id=org.id,
                claim_id=claim.id,
                recovery_score=Decimal("90") - index,
                estimated_value=amount * Decimal("0.8"),
                status=RecoveryStatus.OPEN,
                recommendation="Appeal",
            )
        )
        db.add(
            Denial(
                organization_id=org.id,
                claim_id=claim.id,
                denial_code="CO-15",
                denial_type=DenialType.PRIOR_AUTH,
                description="Authorization missing",
            )
        )
        claims.append(claim)
    db.commit()
    return {
        "org": org,
        "other_org": other_org,
        "manager": manager,
        "viewer": viewer,
        "sarah": sarah,
        "claims": claims,
    }


def test_grounded_claim_search_returns_evidence(db, seeded):
    conversation, message, confirmation = CopilotService(
        db, seeded["org"].id, seeded["manager"]
    ).chat("Show unpaid claims over KSh 50,000")

    assert confirmation is None
    assert message.tool_name == "search_claims"
    assert message.tool_output["total"] == 1
    assert message.tool_output["claims"][0]["claim_number"] == "CLM-COP-1"
    assert message.evidence[0]["path"] == f"/claims/{seeded['claims'][0].id}"
    assert conversation.organization_id == seeded["org"].id


def test_follow_up_reuses_conversation_filters(db, seeded):
    service = CopilotService(db, seeded["org"].id, seeded["manager"])
    conversation, first, _ = service.chat("Show unpaid claims")
    _, second, _ = service.chat("Only those above KSh 50,000", conversation.id)

    assert first.tool_output["total"] == 2
    assert second.tool_input == {"status": "unpaid", "min_amount": 50000.0}
    assert second.tool_output["total"] == 1


def test_vague_request_returns_guided_clarification(db, seeded):
    _, message, confirmation = CopilotService(db, seeded["org"].id, seeded["manager"]).chat(
        "please do"
    )

    assert confirmation is None
    assert message.tool_name is None
    assert message.content.startswith("What would you like me to investigate?")
    assert "I can answer grounded questions" not in message.content


def test_grounded_follow_up_replaces_vague_conversation_title(db, seeded):
    service = CopilotService(db, seeded["org"].id, seeded["manager"])
    conversation, _, _ = service.chat("hi")

    updated, message, _ = service.chat("Show unpaid claims over KSh 50,000", conversation.id)

    assert message.tool_name == "search_claims"
    assert updated.title == "Show unpaid claims over KSh 50,000"


def test_assignment_requires_confirmation_then_executes(db, seeded):
    service = CopilotService(db, seeded["org"].id, seeded["manager"])
    conversation, message, confirmation = service.chat("Assign all cardiology claims to Sarah")

    assert message.tool_output["status"] == "confirmation_required"
    assert confirmation is not None
    assert all(claim.assigned_user_id is None for claim in seeded["claims"])

    conversation_id, executed = service.confirm(confirmation["token"])
    db.expire_all()

    assert conversation_id == conversation.id
    assert executed.tool_output["status"] == "executed"
    assert all(
        db.get(Claim, claim.id).assigned_user_id == seeded["sarah"].id for claim in seeded["claims"]
    )


def test_viewer_cannot_execute_write_confirmation(db, seeded):
    manager_service = CopilotService(db, seeded["org"].id, seeded["viewer"])
    _, _, confirmation = manager_service.chat("Assign all cardiology claims to Sarah")

    with pytest.raises(PermissionError, match="permission"):
        manager_service.confirm(confirmation["token"])

    assert all(claim.assigned_user_id is None for claim in seeded["claims"])


def test_conversation_is_private_to_owning_user_and_org(db, seeded):
    conversation, _, _ = CopilotService(db, seeded["org"].id, seeded["manager"]).chat(
        "Show pending appeals"
    )

    with pytest.raises(ValueError, match="not found"):
        CopilotService(db, seeded["org"].id, seeded["viewer"]).get_conversation(conversation.id)
    with pytest.raises(ValueError, match="not found"):
        CopilotService(db, seeded["other_org"].id, seeded["manager"]).get_conversation(
            conversation.id
        )


def test_denial_trend_discloses_provider_text_filter(db, seeded):
    _, message, _ = CopilotService(db, seeded["org"].id, seeded["manager"]).chat(
        "Why are cardiology denials increasing?"
    )

    assert message.tool_name == "denial_trends"
    assert message.tool_output["provider_filter"] == "cardiology"
    assert "provider text matches" in message.content


def test_api_requires_authentication():
    app.dependency_overrides.clear()
    response = TestClient(app).post("/api/v1/copilot/chat", json={"message": "Show unpaid claims"})

    assert response.status_code == 401


def test_api_serializes_chat_and_conversation_history(client):
    chat = client.post(
        "/api/v1/copilot/chat", json={"message": "Show unpaid claims over KSh 50,000"}
    )

    assert chat.status_code == 200
    payload = chat.json()
    assert payload["message"]["tool_name"] == "search_claims"
    assert payload["message"]["evidence"][0]["path"].startswith("/claims/")
    assert payload["suggested_questions"]

    history = client.get(f"/api/v1/copilot/conversations/{payload['conversation_id']}")
    assert history.status_code == 200
    assert [message["role"] for message in history.json()["messages"]] == ["user", "assistant"]


def test_api_returns_suggestions_for_repeated_vague_requests(client):
    first = client.post("/api/v1/copilot/chat", json={"message": "hi"})
    second = client.post(
        "/api/v1/copilot/chat",
        json={
            "message": "please do",
            "conversation_id": first.json()["conversation_id"],
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["suggested_questions"]
    assert second.json()["message"]["tool_name"] is None


def test_api_feature_flag_returns_not_found(client):
    settings.COPILOT_ENABLED = False
    try:
        response = client.post("/api/v1/copilot/chat", json={"message": "Show unpaid claims"})
    finally:
        settings.COPILOT_ENABLED = True

    assert response.status_code == 404


def test_api_viewer_can_read_but_cannot_confirm_assignment(client, seeded):
    app.dependency_overrides[get_current_user] = lambda: seeded["viewer"]
    preview = client.post(
        "/api/v1/copilot/chat",
        json={"message": "Assign all cardiology claims to Sarah"},
    )

    assert preview.status_code == 200
    token = preview.json()["confirmation"]["token"]
    response = client.post("/api/v1/copilot/confirm", json={"token": token})

    assert response.status_code == 403
