"""
Tests for organization-first registration, email verification, password
reset, and team invitations — the "Multi-Tenant Registration & Auth"
milestone. Uses SQLite in-memory DB; no real Postgres/JWT infra needed
beyond the app's own jwt module (HS256, works fine against any SECRET_KEY).
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as _models  # noqa: F401 — registers every model on Base.metadata
from app.db.database import Base, get_db
from app.main import app


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
def client(db_session):
    def _get_db():
        yield db_session

    from app.middleware.rate_limit import _windows

    _windows.clear()  # each test gets a fresh rate-limit budget

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


STRONG_PASSWORD = "StrongPassword123!"


def test_register_creates_pending_organization_and_admin(client, db_session):
    from app.models.email_verification_token import EmailVerificationToken
    from app.models.organization import Organization, OrganizationSettingsVersion
    from app.models.user import User, UserRole

    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Nairobi General Hospital",
            "organization_type": "hospital",
            "country": "Kenya",
            "first_name": "Sarah",
            "last_name": "Wanjiku",
            "email": "sarah@hospital.com",
            "password": STRONG_PASSWORD,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["message"] == "Verification email sent"

    org = db_session.query(Organization).filter(Organization.id == body["organization_id"]).first()
    assert org is not None
    assert org.status == "pending_verification"
    assert org.slug == "nairobi-general-hospital"
    assert org.country == "Kenya"
    assert org.timezone == "Africa/Nairobi"
    assert org.currency == "KES"
    assert org.billing_email == "sarah@hospital.com"
    assert org.settings["billing"]["currency"] == "KES"
    assert org.settings["workflow"]["require_approval"] is True

    user = db_session.query(User).filter(User.id == body["user_id"]).first()
    assert user is not None
    assert user.role == UserRole.ADMIN
    assert user.is_superuser is False
    assert user.email_verified is False

    settings_version = (
        db_session.query(OrganizationSettingsVersion)
        .filter(OrganizationSettingsVersion.organization_id == org.id)
        .one()
    )
    assert settings_version.version == 1
    assert settings_version.changed_by == user.id

    token_row = (
        db_session.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user.id)
        .first()
    )
    assert token_row is not None


def test_onboarding_creates_hospital_admin_without_platform_access(client, db_session):
    from app.models.user import User, UserRole

    response = client.post(
        "/api/v1/onboarding/",
        json={
            "organization_name": "Mombasa Medical Centre",
            "organization_email": "operations@mombasa-medical.example",
            "organization_phone": "+254700000002",
            "first_name": "Amina",
            "last_name": "Juma",
            "admin_email": "amina@mombasa-medical.example",
            "password": STRONG_PASSWORD,
        },
    )

    assert response.status_code == 200, response.text
    user = db_session.query(User).filter(User.id == response.json()["user_id"]).one()
    assert user.role == UserRole.ADMIN
    assert user.is_superuser is False


def test_register_rejects_weak_password(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Weak Password Clinic",
            "first_name": "A",
            "last_name": "B",
            "email": "weak@hospital.com",
            "password": "weak",
        },
    )
    assert response.status_code == 422


def test_register_rejects_duplicate_email(client):
    payload = {
        "organization_name": "Org One",
        "first_name": "A",
        "last_name": "B",
        "email": "dupe@hospital.com",
        "password": STRONG_PASSWORD,
    }
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 200

    payload["organization_name"] = "Org Two"
    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 400


def test_verify_email_activates_organization_and_allows_role_in_jwt(client, db_session):
    from app.models.email_verification_token import EmailVerificationToken
    from app.models.organization import Organization
    from app.security.jwt import decode_access_token

    reg = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Verify Me Hospital",
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@verifyme.com",
            "password": STRONG_PASSWORD,
        },
    ).json()

    token_row = (
        db_session.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == reg["user_id"])
        .first()
    )

    verify = client.post("/api/v1/auth/verify-email", json={"token": token_row.token})
    assert verify.status_code == 200

    org = db_session.query(Organization).filter(Organization.id == reg["organization_id"]).first()
    assert org.status == "active"

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "jane@verifyme.com",
            "password": STRONG_PASSWORD,
        },
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    claims = decode_access_token(access_token)
    assert claims["role"] == "admin"
    assert claims["organization_id"] == reg["organization_id"]


def test_verify_email_rejects_expired_token(client, db_session):
    from app.models.email_verification_token import EmailVerificationToken

    reg = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Expired Token Hospital",
            "first_name": "Jo",
            "last_name": "Ann",
            "email": "jo@expiredtoken.com",
            "password": STRONG_PASSWORD,
        },
    ).json()

    token_row = (
        db_session.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == reg["user_id"])
        .first()
    )
    token_row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.commit()

    verify = client.post("/api/v1/auth/verify-email", json={"token": token_row.token})
    assert verify.status_code == 400


def test_forgot_and_reset_password_flow(client, db_session):
    from app.models.password_reset_token import PasswordResetToken

    reg = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Reset Flow Hospital",
            "first_name": "Reset",
            "last_name": "User",
            "email": "reset@flow.com",
            "password": STRONG_PASSWORD,
        },
    ).json()

    forgot = client.post("/api/v1/auth/forgot-password", json={"email": "reset@flow.com"})
    assert forgot.status_code == 200

    token_row = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == reg["user_id"])
        .first()
    )
    assert token_row is not None

    new_password = "NewStrongPassword456!"
    reset = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token_row.token,
            "password": new_password,
        },
    )
    assert reset.status_code == 200

    old_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "reset@flow.com",
            "password": STRONG_PASSWORD,
        },
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "reset@flow.com",
            "password": new_password,
        },
    )
    assert new_login.status_code == 200


def test_forgot_password_does_not_leak_unknown_email(client):
    response = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@nowhere.com"})
    assert response.status_code == 200


def test_invite_and_accept_invite_joins_existing_organization(client, db_session):
    from app.models.invitation import Invitation
    from app.models.user import User

    reg = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Invite Flow Hospital",
            "first_name": "Admin",
            "last_name": "Person",
            "email": "admin@inviteflow.com",
            "password": STRONG_PASSWORD,
        },
    ).json()

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@inviteflow.com",
            "password": STRONG_PASSWORD,
        },
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    invite = client.post(
        "/api/v1/users/invite",
        json={"email": "analyst@inviteflow.com", "role": "revenue_analyst"},
        headers=headers,
    )
    assert invite.status_code == 200, invite.text

    invitation = (
        db_session.query(Invitation).filter(Invitation.email == "analyst@inviteflow.com").first()
    )
    assert invitation is not None
    assert invitation.organization_id == reg["organization_id"]

    accept = client.post(
        "/api/v1/users/accept-invite",
        json={
            "token": invitation.token,
            "first_name": "Ana",
            "last_name": "Lyst",
            "password": STRONG_PASSWORD,
        },
    )
    assert accept.status_code == 200, accept.text

    new_user = db_session.query(User).filter(User.email == "analyst@inviteflow.com").first()
    assert new_user is not None
    assert new_user.organization_id == reg["organization_id"]
    assert new_user.role.value == "revenue_analyst"
    assert new_user.email_verified is True


def test_non_admin_cannot_invite(client, db_session):
    from app.models.user import UserRole
    from app.security.hashing import hash_password

    reg = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Locked Down Hospital",
            "first_name": "Admin",
            "last_name": "Person",
            "email": "admin@lockeddown.com",
            "password": STRONG_PASSWORD,
        },
    ).json()

    from app.models.user import User

    viewer = User(
        organization_id=reg["organization_id"],
        email="viewer@lockeddown.com",
        password_hash=hash_password(STRONG_PASSWORD),
        first_name="View",
        last_name="Only",
        role=UserRole.VIEWER,
        email_verified=True,
    )
    db_session.add(viewer)
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "viewer@lockeddown.com",
            "password": STRONG_PASSWORD,
        },
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    invite = client.post(
        "/api/v1/users/invite",
        json={"email": "someone@lockeddown.com", "role": "viewer"},
        headers=headers,
    )
    assert invite.status_code == 403


def test_logout_revokes_session_token(client, db_session):
    from app.governance.models import UserSession

    client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Session Hospital",
            "first_name": "Session",
            "last_name": "Admin",
            "email": "session@hospital.com",
            "password": STRONG_PASSWORD,
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "session@hospital.com",
            "password": STRONG_PASSWORD,
        },
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert db_session.query(UserSession).one().revoke_reason == "User signed out"
