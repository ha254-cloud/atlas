import hashlib
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.main import app
from app.security.dependencies import get_current_user


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session = sessionmaker(bind=engine)()
    Base.metadata.create_all(engine)
    yield session
    session.close()


@pytest.fixture()
def tenant(db):
    from app.models.organization import Organization
    from app.models.user import User, UserRole

    organization = Organization(name="Nairobi Hospital", email="billing@nairobi.test")
    db.add(organization)
    db.flush()
    submitter = User(
        organization_id=organization.id,
        email="policy-maker@nairobi.test",
        password_hash="x",
        first_name="Policy",
        last_name="Maker",
        role=UserRole.MANAGER,
    )
    approver = User(
        organization_id=organization.id,
        email="policy-checker@nairobi.test",
        password_hash="x",
        first_name="Policy",
        last_name="Checker",
        role=UserRole.MANAGER,
    )
    db.add_all([submitter, approver])
    db.commit()
    return {
        "organization": organization,
        "submitter": submitter,
        "approver": approver,
    }


@pytest.fixture()
def client(db, tenant):
    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: tenant["organization"].id
    app.dependency_overrides[get_current_user] = lambda: tenant["submitter"]
    yield TestClient(app)
    app.dependency_overrides.clear()


def as_user(user):
    app.dependency_overrides[get_current_user] = lambda: user


def create_approved_payer(client, tenant) -> dict:
    created = client.post(
        "/api/v1/payers",
        json={
            "name": "Social Health Authority",
            "payer_code": "SHA",
            "reason": "Configure governed Kenya payer",
        },
    )
    assert created.status_code == 201
    payer = created.json()
    assert client.post(f"/api/v1/payers/{payer['id']}/submit-for-approval").status_code == 200
    as_user(tenant["approver"])
    approved = client.post(f"/api/v1/payers/{payer['id']}/approve")
    assert approved.status_code == 200
    as_user(tenant["submitter"])
    return approved.json()


def policy_payload(**overrides) -> dict:
    payload = {
        "policy_code": "SHA-PA-001",
        "title": "SHA Prior Authorization Guidance",
        "source_type": "operating_guidance",
        "source_reference": "SHA Circular 12, section 4",
        "source_uri": "https://example.test/sha/circular-12",
        "content": (
            "A request for reconsideration may include documented authorization evidence "
            "for the billed service."
        ),
        "effective_from": "2025-01-01",
        "denial_categories": ["PRIOR_AUTHORIZATION"],
        "procedure_codes": ["99213"],
        "reason": "Initial reviewed source version",
    }
    payload.update(overrides)
    return payload


def create_policy(client, payer_id: int, **overrides) -> dict:
    response = client.post(
        f"/api/v1/payers/{payer_id}/policy-sources",
        json=policy_payload(**overrides),
    )
    assert response.status_code == 201
    return response.json()


def approve_policy(client, tenant, payer_id: int, source_id: int) -> dict:
    submitted = client.post(
        f"/api/v1/payers/{payer_id}/policy-sources/{source_id}/submit-for-approval"
    )
    assert submitted.status_code == 200
    as_user(tenant["approver"])
    approved = client.post(
        f"/api/v1/payers/{payer_id}/policy-sources/{source_id}/approve"
    )
    assert approved.status_code == 200
    as_user(tenant["submitter"])
    return approved.json()


def test_policy_source_defaults_to_governed_draft_and_stable_checksum(client, tenant):
    payer = create_approved_payer(client, tenant)
    source = create_policy(client, payer["id"])

    expected_content = policy_payload()["content"]
    assert source["status"] == "draft"
    assert source["jurisdiction"] == "KE"
    assert source["version"] == 1
    assert source["content_sha256"] == hashlib.sha256(expected_content.encode()).hexdigest()


def test_policy_source_requires_different_approver_and_approved_payer(client, tenant):
    payer = create_approved_payer(client, tenant)
    source = create_policy(client, payer["id"])
    client.post(
        f"/api/v1/payers/{payer['id']}/policy-sources/{source['id']}/submit-for-approval"
    )

    same_user = client.post(
        f"/api/v1/payers/{payer['id']}/policy-sources/{source['id']}/approve"
    )
    assert same_user.status_code == 400
    assert "same user" in same_user.json()["detail"]


def test_rejected_policy_can_be_resubmitted(client, tenant):
    payer = create_approved_payer(client, tenant)
    source = create_policy(client, payer["id"])
    client.post(
        f"/api/v1/payers/{payer['id']}/policy-sources/{source['id']}/submit-for-approval"
    )
    as_user(tenant["approver"])
    rejected = client.post(
        f"/api/v1/payers/{payer['id']}/policy-sources/{source['id']}/reject",
        json={"reason": "Reference needs a more specific section"},
    )
    assert rejected.status_code == 200

    as_user(tenant["submitter"])
    resubmitted = client.post(
        f"/api/v1/payers/{payer['id']}/policy-sources/{source['id']}/submit-for-approval"
    )
    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "pending_approval"
    assert resubmitted.json()["rejection_reason"] is None


def test_new_approved_version_retires_prior_version(client, tenant):
    payer = create_approved_payer(client, tenant)
    first = create_policy(client, payer["id"])
    approve_policy(client, tenant, payer["id"], first["id"])

    second = create_policy(
        client,
        payer["id"],
        content=policy_payload()["content"] + " The revised evidence checklist applies.",
        reason="Reviewed evidence checklist revision",
    )
    assert second["version"] == 2
    approve_policy(client, tenant, payer["id"], second["id"])

    listed = client.get(f"/api/v1/payers/{payer['id']}/policy-sources")
    assert listed.status_code == 200
    by_version = {item["version"]: item["status"] for item in listed.json()}
    assert by_version == {1: "retired", 2: "approved"}


def test_policy_source_endpoints_are_cross_tenant_safe(client, db, tenant):
    from app.models.organization import Organization
    from app.models.payer import Payer, PayerPolicySource

    other = Organization(name="Other Hospital", email="other@hospital.test")
    db.add(other)
    db.flush()
    other_payer = Payer(
        organization_id=other.id,
        name="Other Payer",
        payer_code="OTHER",
        approval_status="approved",
    )
    db.add(other_payer)
    db.flush()
    other_source = PayerPolicySource(
        organization_id=other.id,
        payer_id=other_payer.id,
        policy_code="OTHER-1",
        title="Other Tenant Policy",
        source_type="payer_contract",
        jurisdiction="KE",
        version=1,
        status="pending_approval",
        source_reference="Other contract section 1",
        content="This content belongs only to the other tenant and must remain isolated.",
        content_sha256="a" * 64,
        effective_from=date(2025, 1, 1),
        denial_categories=[],
        procedure_codes=[],
        created_by=tenant["submitter"].id,
        submitted_by=tenant["submitter"].id,
        change_reason="Other tenant setup",
    )
    db.add(other_source)
    db.commit()

    assert client.get(f"/api/v1/payers/{other_payer.id}/policy-sources").status_code == 404
    response = client.post(
        f"/api/v1/payers/{other_payer.id}/policy-sources/{other_source.id}/approve"
    )
    assert response.status_code == 404


def test_applicable_excludes_unapproved_future_expired_and_wrong_scope(client, db, tenant):
    from app.payers.policies import PayerPolicyService

    payer = create_approved_payer(client, tenant)
    applicable = create_policy(client, payer["id"])
    approve_policy(client, tenant, payer["id"], applicable["id"])
    create_policy(
        client,
        payer["id"],
        policy_code="FUTURE",
        effective_from="2030-01-01",
    )
    create_policy(
        client,
        payer["id"],
        policy_code="EXPIRED",
        effective_from="2024-01-01",
        effective_to="2024-12-31",
    )
    create_policy(
        client,
        payer["id"],
        policy_code="WRONG-PROCEDURE",
        procedure_codes=["11111"],
    )

    selected = PayerPolicyService(db, tenant["organization"].id).applicable(
        payer["id"],
        on_date=date(2025, 6, 1),
        denial_category="PRIOR_AUTHORIZATION",
        procedure_codes={"99213"},
    )

    assert [item.id for item in selected] == [applicable["id"]]
