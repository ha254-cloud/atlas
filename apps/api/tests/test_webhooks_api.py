"""
API-level tests for the Sprint 8 Webhook subscription CRUD endpoints
(app/webhooks/router.py) — create/list/update/delete/list-deliveries, plus
an RBAC check (VIEWER role should be forbidden from managing webhooks).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401 — registers every model on Base.metadata
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.main import app
from app.models.organization import Organization
from app.models.user import User, UserRole
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
    org = Organization(name="Atlas Demo Clinic", email="org@atlasdemo.com")
    db_session.add(org)
    db_session.flush()

    user = User(
        organization_id=org.id,
        email="admin@atlasdemo.com",
        password_hash="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    db_session.commit()

    return {"org": org, "user": user}


@pytest.fixture()
def client(db_session, seed):
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: seed["org"].id
    app.dependency_overrides[get_current_user] = lambda: seed["user"]

    yield TestClient(app)

    app.dependency_overrides.clear()


class TestWebhooksAPI:
    def test_create_returns_secret_once(self, client):
        response = client.post("/api/v1/webhooks", json={"target_url": "https://example.com/hook"})
        assert response.status_code == 201
        body = response.json()
        assert body["target_url"] == "https://example.com/hook"
        assert "secret" in body and len(body["secret"]) > 0

    def test_list_does_not_include_secret(self, client):
        client.post("/api/v1/webhooks", json={"target_url": "https://example.com/hook"})

        response = client.get("/api/v1/webhooks")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert "secret" not in body[0]

    def test_update_toggles_is_active(self, client):
        created = client.post(
            "/api/v1/webhooks", json={"target_url": "https://example.com/hook"}
        ).json()

        response = client.patch(f"/api/v1/webhooks/{created['id']}", json={"is_active": False})
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_update_missing_subscription_404s(self, client):
        response = client.patch("/api/v1/webhooks/9999", json={"is_active": False})
        assert response.status_code == 404

    def test_delete_subscription(self, client):
        created = client.post(
            "/api/v1/webhooks", json={"target_url": "https://example.com/hook"}
        ).json()

        response = client.delete(f"/api/v1/webhooks/{created['id']}")
        assert response.status_code == 204

        follow_up = client.get("/api/v1/webhooks")
        assert follow_up.json() == []

    def test_delete_missing_subscription_404s(self, client):
        response = client.delete("/api/v1/webhooks/9999")
        assert response.status_code == 404

    def test_list_deliveries_empty_for_new_subscription(self, client):
        created = client.post(
            "/api/v1/webhooks", json={"target_url": "https://example.com/hook"}
        ).json()

        response = client.get(f"/api/v1/webhooks/{created['id']}/deliveries")
        assert response.status_code == 200
        assert response.json() == []

    def test_viewer_role_forbidden_from_creating_webhook(self, client, seed, db_session):
        seed["user"].role = UserRole.VIEWER
        db_session.commit()

        response = client.post("/api/v1/webhooks", json={"target_url": "https://example.com/hook"})
        assert response.status_code == 403
