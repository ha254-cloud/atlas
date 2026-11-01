from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.eclaims.fhir import SHABundleBuilder, canonical_json_sha256
from app.eclaims.models import SHAExchange, SHAExchangeEvent
from app.eclaims.schemas import SHAClaimSubmit
from app.events.models import DomainEventOutbox
from app.integrations.base import EClaimsConnector, EClaimsTransportResponse
from app.integrations.connectors.sha import SHAConnector, SHAConnectorError
from app.main import app
from app.models.audit_log import AuditLog
from app.models.claim import Claim
from app.models.claim_diagnosis import ClaimDiagnosis
from app.models.claim_line import ClaimLine
from app.models.integration import Integration, IntegrationStatus
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.user import User, UserRole
from app.security.dependencies import get_current_user
from app.security.permissions import Permission, role_has_permission


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def seeded(db_session):
    organization = Organization(
        name="Nairobi General Hospital",
        email="hospital@example.test",
    )
    other_organization = Organization(
        name="Other Hospital",
        email="other@example.test",
    )
    db_session.add_all([organization, other_organization])
    db_session.flush()
    user = User(
        organization_id=organization.id,
        email="biller@example.test",
        password_hash="x",
        first_name="Amina",
        last_name="Biller",
        role=UserRole.BILLER,
    )
    viewer = User(
        organization_id=organization.id,
        email="viewer@example.test",
        password_hash="x",
        first_name="View",
        last_name="Only",
        role=UserRole.VIEWER,
    )
    patient = Patient(
        organization_id=organization.id,
        first_name="Jane",
        last_name="Wanjiku",
        medical_record_number="MRN-001",
        date_of_birth=date(1985, 6, 15),
    )
    payer = Payer(
        organization_id=organization.id,
        name="Social Health Authority",
        payer_code="SHA",
    )
    integration = Integration(
        organization_id=organization.id,
        provider="sha",
        status=IntegrationStatus.ACTIVE,
        settings={
            "base_url": "https://hie-test.dha.go.ke/fhir",
            "token_url": "https://auth-test.dha.go.ke/oauth/token",
            "client_id": "atlas-test-client",
            "provider_number": "PROV-KE-00123",
            "facility_name": "Nairobi General Hospital",
        },
    )
    db_session.add_all([user, viewer, patient, payer, integration])
    db_session.flush()
    claim = Claim(
        organization_id=organization.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="SHA-CLAIM-001",
        status="pending",
        billed_amount=Decimal("85000.00"),
        paid_amount=Decimal("0.00"),
        currency="KES",
        service_date=date(2026, 10, 31),
    )
    db_session.add(claim)
    db_session.flush()
    diagnosis = ClaimDiagnosis(
        claim_id=claim.id,
        icd_code="K35.80",
        description="Appendicitis",
        is_primary=True,
    )
    line = ClaimLine(
        claim_id=claim.id,
        cpt_code="44950",
        description="Appendectomy",
        units=1,
        charge_amount=Decimal("85000.00"),
    )
    db_session.add_all([diagnosis, line])
    db_session.commit()
    db_session.refresh(claim)
    return {
        "organization": organization,
        "other_organization": other_organization,
        "user": user,
        "viewer": viewer,
        "claim": claim,
        "diagnosis": diagnosis,
        "line": line,
        "integration": integration,
    }


@pytest.fixture()
def payload(seeded):
    return {
        "integration_id": seeded["integration"].id,
        "idempotency_key": "sha-claim-001-attempt-1",
        "reason": "Submit verified hospital claim to SHA",
        "patient_identifier_type": "SHA-NUMBER",
        "patient_identifier": "SHA-2026-001234",
        "patient_gender": "female",
        "patient_phone": "+254712345678",
        "patient_contact": {
            "family_name": "Wanjiku",
            "given_names": ["Mary"],
            "phone": "+254798765432",
        },
        "practitioner": {
            "identifier_type": "SHA-NUMBER",
            "identifier": "DR-KE-00456",
            "family_name": "Ochieng",
            "given_names": ["James"],
            "phone": "+254711234567",
            "gender": "male",
            "birth_date": "1978-03-22",
        },
        "invoice": {
            "number": "INV-2026-001234",
            "date": "2026-10-31",
            "patient_share": "0.00",
        },
        "claim_type": "institutional",
        "claim_subtype": "inpatient",
        "coverage": {
            "number": "COV-SHA-2026-001234",
            "class_code": "GROUP",
            "class_display": "Group",
            "class_value": "SHA-SOCIAL-001",
            "class_name": "SHA Social Health Scheme",
            "annual_limit_category_code": "17",
            "annual_limit_category_display": "General Practice",
            "period_start": "2026-01-01",
            "period_end": "2026-12-31",
        },
        "encounter": {
            "number": "ENC-2026-001234",
            "class_code": "IMP",
            "class_display": "inpatient encounter",
            "service_type_code": "124",
            "service_type_display": "General Practice",
            "period_start": "2026-10-30T08:00:00+03:00",
            "period_end": "2026-10-31T10:00:00+03:00",
        },
        "diagnoses": [
            {
                "claim_diagnosis_id": seeded["diagnosis"].id,
                "icd11_code": "DC80",
                "display": "Appendicitis",
            }
        ],
        "line_items": [
            {
                "claim_line_id": seeded["line"].id,
                "intervention_code": "SHA-19",
                "intervention_display": "Surgical Services",
                "benefit_category_code": "2",
                "benefit_category_display": "Surgical",
            }
        ],
    }


class AcceptedSHAConnector(EClaimsConnector):
    async def submit_claim_bundle(
        self,
        bundle,
        *,
        correlation_id,
    ) -> EClaimsTransportResponse:
        assert bundle["resourceType"] == "Bundle"
        assert correlation_id
        resource = {
            "resourceType": "ClaimResponse",
            "id": "response-001",
            "extension": [
                {
                    "url": (
                        "https://fhir.dha.go.ke/claims/StructureDefinition/"
                        "eclaim-state-extension"
                    ),
                    "valueCodeableConcept": {
                        "coding": [{"code": "under-review"}]
                    },
                }
            ],
            "outcome": "queued",
        }
        return EClaimsTransportResponse(
            http_status=201,
            resource=resource,
            response_sha256=canonical_json_sha256(resource),
            external_reference="response-001",
        )

    async def get_claim_response(
        self,
        external_reference,
        *,
        correlation_id,
    ) -> EClaimsTransportResponse:
        assert external_reference == "response-001"
        assert correlation_id
        resource = {
            "resourceType": "ClaimResponse",
            "id": "response-001",
            "extension": [
                {
                    "url": (
                        "https://fhir.dha.go.ke/claims/StructureDefinition/"
                        "eclaim-state-extension"
                    ),
                    "valueCodeableConcept": {"coding": [{"code": "approved"}]},
                }
            ],
            "outcome": "complete",
            "total": [
                {
                    "category": {"coding": [{"code": "benefit"}]},
                    "amount": {"value": 80000, "currency": "KES"},
                }
            ],
        }
        return EClaimsTransportResponse(
            http_status=200,
            resource=resource,
            response_sha256=canonical_json_sha256(resource),
            external_reference="response-001",
        )


def test_bundle_builder_uses_official_profiles_and_minimizes_patient_data(
    seeded,
    payload,
):
    claim = seeded["claim"]
    claim.patient = claim.patient
    claim.claim_lines = [seeded["line"]]
    claim.diagnoses = [seeded["diagnosis"]]
    request = SHAClaimSubmit.model_validate(payload)

    bundle = SHABundleBuilder(seeded["integration"].settings).build(
        claim,
        seeded["organization"],
        request,
        requested_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
    )

    assert bundle["type"] == "collection"
    assert bundle["meta"]["lastUpdated"] == "2026-11-01T12:00:00+00:00"
    resources = {
        entry["resource"]["resourceType"]: entry["resource"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] != "Condition"
    }
    assert resources["Claim"]["meta"]["profile"] == [
        "https://fhir.dha.go.ke/claims/StructureDefinition/ke-eclaims-claimsubmission"
    ]
    assert resources["Patient"]["identifier"][0]["value"] == "SHA-2026-001234"
    assert resources["Patient"]["telecom"][0]["value"] == "+254712345678"
    assert "MRN-001" not in str(bundle)
    assert resources["Claim"]["extension"][0]["extension"][0]["valueString"] == (
        "INV-2026-001234"
    )
    assert resources["Claim"]["item"][0]["productOrService"]["coding"][0][
        "code"
    ] == "SHA-19"
    practitioner = next(
        entry["resource"]
        for entry in bundle["entry"]
        if entry["resource"]["resourceType"] == "Practitioner"
    )
    assert practitioner["identifier"][0]["value"] == "DR-KE-00456"


@pytest.mark.asyncio
async def test_sha_connector_uses_client_credentials_and_real_fhir_endpoints():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/oauth/token":
            assert request.headers["authorization"].startswith("Basic ")
            return httpx.Response(
                200,
                json={"access_token": "short-lived-token", "expires_in": 900},
            )
        assert request.headers["authorization"] == "Bearer short-lived-token"
        assert request.headers["content-type"] == "application/fhir+json"
        return httpx.Response(
            201,
            json={"resourceType": "ClaimResponse", "id": "response-001"},
        )

    connector = SHAConnector(
        organization_id=1,
        client_id="atlas-client",
        client_secret="secret",
        token_url="https://auth-test.dha.go.ke/oauth/token",
        base_url="https://hie-test.dha.go.ke/fhir",
        transport=httpx.MockTransport(handler),
    )
    result = await connector.submit_claim_bundle(
        {"resourceType": "Bundle", "type": "collection", "entry": []},
        correlation_id="corr-001",
    )

    assert result.http_status == 201
    assert result.external_reference == "response-001"
    assert [request.url.path for request in requests] == [
        "/oauth/token",
        "/fhir/Bundle",
    ]


@pytest.mark.asyncio
async def test_sha_connector_surfaces_operation_outcome_without_token_or_phi():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "token", "expires_in": 900})
        return httpx.Response(
            422,
            json={
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "required",
                        "details": {"text": "Claim.patient is required"},
                        "expression": ["Bundle.entry[0].resource.patient"],
                    }
                ],
            },
        )

    connector = SHAConnector(
        organization_id=1,
        client_id="atlas-client",
        client_secret="secret",
        token_url="https://auth-test.dha.go.ke/oauth/token",
        base_url="https://hie-test.dha.go.ke/fhir",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(SHAConnectorError) as captured:
        await connector.submit_claim_bundle(
            {"resourceType": "Bundle", "type": "collection", "entry": []},
            correlation_id="corr-002",
        )

    assert captured.value.http_status == 422
    assert captured.value.issues[0]["code"] == "required"
    assert "token" not in str(captured.value)


def test_biller_can_submit_claims_but_viewer_cannot():
    assert role_has_permission(UserRole.BILLER, Permission.SUBMIT_CLAIMS)
    assert not role_has_permission(UserRole.VIEWER, Permission.SUBMIT_CLAIMS)


def test_sha_api_is_tenant_scoped_idempotent_and_audited(
    db_session,
    seeded,
    payload,
):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_organization] = lambda: seeded[
        "organization"
    ].id
    app.dependency_overrides[get_current_user] = lambda: seeded["user"]
    client = TestClient(app)
    try:
        with patch(
            "app.eclaims.service.IntegrationManager.connector",
            return_value=AcceptedSHAConnector(),
        ):
            response = client.post(
                f"/api/v1/eclaims/claims/{seeded['claim'].id}/submit",
                json=payload,
                headers={"X-Request-ID": "corr-api-001"},
            )
            duplicate = client.post(
                f"/api/v1/eclaims/claims/{seeded['claim'].id}/submit",
                json=payload,
                headers={"X-Request-ID": "corr-api-001"},
            )

        assert response.status_code == 201, response.text
        assert duplicate.status_code == 201
        assert response.json()["id"] == duplicate.json()["id"]
        assert response.json()["status"] == "under-review"
        assert db_session.query(SHAExchange).count() == 1
        assert db_session.query(SHAExchangeEvent).count() == 2
        assert (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "sha_eclaim.submitted")
            .count()
            == 1
        )
        assert (
            db_session.query(DomainEventOutbox)
            .filter(DomainEventOutbox.event_type == "claim.submitted")
            .count()
            == 1
        )

        app.dependency_overrides[get_current_organization] = lambda: seeded[
            "other_organization"
        ].id
        cross_tenant = client.get(
            f"/api/v1/eclaims/exchanges/{response.json()['id']}"
        )
        assert cross_tenant.status_code == 404
    finally:
        app.dependency_overrides.clear()
