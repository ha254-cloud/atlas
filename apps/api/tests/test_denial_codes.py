"""
Tests for Atlas' denial knowledge base: the `DenialCode` model,
`DenialCodeRepository`, and the read-only `/api/v1/denial-codes` API.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401 — registers every model on Base.metadata
from app.db.database import Base, get_db
from app.main import app
from app.models.denial import DenialType
from app.models.denial_code import DenialCode, DenialCodeRecoverability, DenialCodeSeverity
from app.repositories.denial_code_repository import DenialCodeRepository, normalize_code
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
def seeded_codes(db_session):
    codes = [
        DenialCode(
            code="CO16",
            category=DenialType.DOCUMENTATION,
            description="Missing information needed for adjudication.",
            recovery_strategy="Attach the required documentation and resubmit.",
            ai_guidance="Weight recovery probability higher when docs are easy to obtain.",
            severity=DenialCodeSeverity.MEDIUM,
            recoverability=DenialCodeRecoverability.HIGH,
            typical_recovery_rate=85.0,
            required_documents=["Medical records", "Physician notes"],
            typical_resolution_days=15,
            common_payers=["Medicare", "BCBS"],
            references=["X12 CARC official code list"],
        ),
        DenialCode(
            code="CO29",
            category=DenialType.TIMELY_FILING,
            description="Filing deadline exceeded.",
            recovery_strategy="Appeal with proof of timely submission.",
            is_active=False,
        ),
    ]
    db_session.add_all(codes)
    db_session.commit()
    return codes


def test_normalize_code_strips_separators_and_uppercases():
    assert normalize_code("co-16") == "CO16"
    assert normalize_code(" CO16 ") == "CO16"
    assert normalize_code("CO16") == "CO16"


def test_get_by_code_matches_hyphenated_and_lowercase_variants(db_session, seeded_codes):
    repo = DenialCodeRepository(db_session)

    assert repo.get_by_code("CO16").code == "CO16"
    assert repo.get_by_code("CO-16").code == "CO16"
    assert repo.get_by_code("co16").code == "CO16"


def test_get_by_code_returns_none_for_unknown_code(db_session, seeded_codes):
    repo = DenialCodeRepository(db_session)
    assert repo.get_by_code("CO999") is None


def test_get_by_code_returns_none_for_empty_code(db_session, seeded_codes):
    repo = DenialCodeRepository(db_session)
    assert repo.get_by_code(None) is None
    assert repo.get_by_code("") is None


def test_list_all_returns_every_code_sorted(db_session, seeded_codes):
    repo = DenialCodeRepository(db_session)
    codes = repo.list_all()
    assert [c.code for c in codes] == ["CO16", "CO29"]


def test_find_by_category_returns_matching_codes(db_session, seeded_codes):
    repo = DenialCodeRepository(db_session)
    codes = repo.find_by_category("documentation")
    assert [c.code for c in codes] == ["CO16"]


def test_find_by_category_returns_empty_for_unknown_category(db_session, seeded_codes):
    repo = DenialCodeRepository(db_session)
    assert repo.find_by_category("not_a_real_category") == []


def test_list_active_excludes_inactive_codes(db_session, seeded_codes):
    repo = DenialCodeRepository(db_session)
    codes = repo.list_active()
    assert [c.code for c in codes] == ["CO16"]


@pytest.fixture()
def client(db_session, seeded_codes):
    def _get_db():
        yield db_session

    def _get_current_user():
        return type("StubUser", (), {"id": 1, "organization_id": 1})()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_denial_codes_endpoint(client):
    response = client.get("/api/v1/denial-codes")
    assert response.status_code == 200
    codes = response.json()
    assert [c["code"] for c in codes] == ["CO16", "CO29"]
    assert codes[0]["category"] == "documentation"
    assert codes[0]["recovery_strategy"] == "Attach the required documentation and resubmit."
    assert (
        codes[0]["ai_guidance"]
        == "Weight recovery probability higher when docs are easy to obtain."
    )
    assert codes[0]["is_active"] is True
    assert codes[1]["is_active"] is False


def test_list_denial_codes_endpoint_includes_richer_intelligence_fields(client):
    response = client.get("/api/v1/denial-codes")
    assert response.status_code == 200
    co16 = next(c for c in response.json() if c["code"] == "CO16")
    assert co16["severity"] == "medium"
    assert co16["recoverability"] == "high"
    assert co16["typical_recovery_rate"] == 85.0
    assert co16["required_documents"] == ["Medical records", "Physician notes"]
    assert co16["typical_resolution_days"] == 15
    assert co16["common_payers"] == ["Medicare", "BCBS"]
    assert co16["references"] == ["X12 CARC official code list"]


def test_list_denial_codes_endpoint_filters_by_category(client):
    response = client.get("/api/v1/denial-codes", params={"category": "timely_filing"})
    assert response.status_code == 200
    codes = response.json()
    assert [c["code"] for c in codes] == ["CO29"]


def test_list_denial_codes_endpoint_active_only(client):
    response = client.get("/api/v1/denial-codes", params={"active_only": "true"})
    assert response.status_code == 200
    codes = response.json()
    assert [c["code"] for c in codes] == ["CO16"]


def test_get_denial_code_endpoint_matches_hyphenated_variant(client):
    response = client.get("/api/v1/denial-codes/CO-29")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "CO29"
    assert body["category"] == "timely_filing"


def test_get_denial_code_endpoint_404_for_unknown_code(client):
    response = client.get("/api/v1/denial-codes/CO999")
    assert response.status_code == 404
