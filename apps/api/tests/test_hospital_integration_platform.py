from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.database import Base
from app.integrations.connectors.sftp import SFTPConnector
from app.integrations.history import IntegrationSyncHistoryService
from app.integrations.jobs import run_sync_job, schedule_all_syncs
from app.integrations.mapping import IntegrationMappingService, MappingError, apply_mapping
from app.integrations.models import SyncResult
from app.models.integration import Integration, IntegrationStatus
from app.models.organization import Organization
from app.models.user import User, UserRole


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


def _organization(db, suffix: str):
    organization = Organization(name=f"Hospital {suffix}", email=f"{suffix.lower()}@hospital.test")
    db.add(organization)
    db.flush()
    user = User(
        organization_id=organization.id,
        email=f"admin-{suffix.lower()}@hospital.test",
        password_hash="x",
        first_name="Hospital",
        last_name="Admin",
        role=UserRole.ADMIN,
    )
    integration = Integration(
        organization_id=organization.id,
        provider="sftp",
        settings={"hostname": f"{suffix.lower()}.hospital.test"},
    )
    db.add_all([user, integration])
    db.commit()
    return organization, user, integration


def _fields(prefix: str = ""):
    return [
        {"source_field": f"{prefix}ClaimNo", "target_field": "claim_number", "required": True},
        {"source_field": f"{prefix}Payer", "target_field": "payer_code", "required": True},
        {
            "source_field": f"{prefix}Amount",
            "target_field": "billed_amount",
            "required": True,
            "transform": {"type": "decimal", "currency_symbols": ["KES", ","]},
        },
        {
            "source_field": f"{prefix}ServiceDate",
            "target_field": "service_date",
            "required": True,
            "transform": {"type": "date", "input_format": "%d/%m/%y"},
        },
        {"source_field": f"{prefix}HospitalNo", "target_field": "medical_record_number"},
    ]


def test_mapping_normalizes_kenyan_hospital_export(db):
    organization, user, integration = _organization(db, "ONE")
    service = IntegrationMappingService(db, organization.id)
    profile = service.create_profile(
        integration.id,
        name="Care2000 claims",
        source_format="csv",
        fields=_fields(),
        actor_id=user.id,
        reason="Initial onboarding mapping",
        correlation_id="mapping-test-1",
    )

    mapped = apply_mapping(
        {
            "ClaimNo": " CLM-001 ",
            "Payer": "SHA",
            "Amount": "KES 20,000",
            "ServiceDate": "10/08/26",
            "HospitalNo": "H-100",
        },
        service.fields_for(profile.id),
    )

    assert mapped == {
        "claim_number": "CLM-001",
        "payer_code": "SHA",
        "billed_amount": "20000.00",
        "service_date": date(2026, 8, 10).isoformat(),
        "medical_record_number": "H-100",
    }


def test_required_source_field_has_clear_rejection(db):
    organization, user, integration = _organization(db, "ONE")
    service = IntegrationMappingService(db, organization.id)
    profile = service.create_profile(
        integration.id,
        name="Required fields",
        source_format="csv",
        fields=_fields(),
        actor_id=user.id,
        reason="Validate required fields",
        correlation_id="mapping-test-2",
    )

    with pytest.raises(MappingError) as exc_info:
        apply_mapping({"ClaimNo": "CLM-002"}, service.fields_for(profile.id))

    assert exc_info.value.code == "required_source_field_missing"
    assert exc_info.value.source_field == "Payer"


def test_mapping_versions_are_append_only_and_tenant_scoped(db):
    organization, user, integration = _organization(db, "ONE")
    other_organization, _, _ = _organization(db, "TWO")
    service = IntegrationMappingService(db, organization.id)

    first = service.create_profile(
        integration.id,
        name="Version one",
        source_format="csv",
        fields=_fields(),
        actor_id=user.id,
        reason="Initial mapping",
        correlation_id="mapping-v1",
    )
    second = service.create_profile(
        integration.id,
        name="Version two",
        source_format="csv",
        fields=_fields("New"),
        actor_id=user.id,
        reason="Hospital changed export headers",
        correlation_id="mapping-v2",
    )

    assert [profile.version for profile in service.list_profiles(integration.id)] == [2, 1]
    assert first.id != second.id
    assert service.fields_for(first.id)[0].source_field == "ClaimNo"
    assert service.latest_profile(integration.id).id == second.id

    with pytest.raises(ValueError, match="Integration not found"):
        IntegrationMappingService(db, other_organization.id).list_profiles(integration.id)


def test_mapping_rejects_unknown_canonical_field(db):
    organization, user, integration = _organization(db, "ONE")
    fields = _fields()
    fields.append({"source_field": "Secret", "target_field": "patient_identity"})

    with pytest.raises(ValueError, match="Unsupported canonical fields"):
        IntegrationMappingService(db, organization.id).create_profile(
            integration.id,
            name="Unsafe mapping",
            source_format="csv",
            fields=fields,
            actor_id=user.id,
            reason="Must reject arbitrary target fields",
            correlation_id="mapping-test-unsafe",
        )


def test_sftp_mapping_rejects_bad_row_and_keeps_valid_row(db):
    organization, user, integration = _organization(db, "ONE")
    service = IntegrationMappingService(db, organization.id)
    profile = service.create_profile(
        integration.id,
        name="Care2000 claims",
        source_format="csv",
        fields=_fields(),
        actor_id=user.id,
        reason="Test partial file processing",
        correlation_id="mapping-partial",
    )
    rules = [
        {
            "source_field": field.source_field,
            "target_field": field.target_field,
            "transform": field.transform,
            "required": field.required,
            "default_value": field.default_value,
        }
        for field in service.fields_for(profile.id)
    ]
    connector = SFTPConnector(
        organization.id,
        field_mapping=rules,
        mapping_profile_id=profile.id,
    )
    payload = (
        "ClaimNo,Payer,Amount,ServiceDate,HospitalNo\n"
        "CLM-VALID,SHA,120000,10/08/26,H-1\n"
        "CLM-BAD,SHA,not-money,10/08/26,H-2\n"
    )

    claims = connector._parse_csv(payload, "file-1", "/claims/daily.csv")

    assert [claim.claim_number for claim in claims] == ["CLM-VALID"]
    assert connector.rejection_details == [
        {
            "row_number": 3,
            "source_field": "Amount",
            "error_code": "invalid_decimal",
            "message": "Field 'Amount' is not a valid amount",
        }
    ]


def test_sync_history_records_partial_run_without_raw_patient_data(db):
    organization, user, integration = _organization(db, "ONE")
    history = IntegrationSyncHistoryService(db, organization.id)
    run = history.start(
        integration.id,
        trigger="manual",
        initiated_by=user.id,
        correlation_id="sync-partial",
    )
    history.complete(
        run,
        {"claims_imported": 5, "errors": ["Missing payer"]},
        [
            {
                "row_number": 7,
                "source_field": "Payer",
                "error_code": "required_source_field_missing",
                "message": "Required source field 'Payer' is missing",
            }
        ],
    )

    stored = history.list_runs(integration.id)[0]
    errors = history.list_errors(integration.id, stored.id)
    assert stored.status == "partial"
    assert stored.records_received == 6
    assert stored.records_imported == 5
    assert stored.records_rejected == 1
    assert errors[0].row_number == 7
    assert not hasattr(errors[0], "raw_record")


def test_partial_sync_keeps_connection_active_and_scheduled(db, monkeypatch):
    organization, user, integration = _organization(db, "PARTIAL")
    rejection = {
        "row_number": 3,
        "source_field": "Amount",
        "error_code": "invalid_decimal",
        "message": "Field 'Amount' is not a valid amount",
    }
    result = SyncResult(
        provider="sftp",
        organization_id=organization.id,
        rejection_details=[rejection],
        errors=[rejection["message"]],
    )

    class FakeManager:
        def __init__(self, session):
            self.session = session

        async def sync(self, integration_id, organization_id):
            integration.status = IntegrationStatus.ACTIVE
            self.session.commit()
            return result

        def get_integration(self, integration_id, organization_id):
            return integration

    class FakeOrchestrator:
        def __init__(self, session, organization_id, integration_id):
            pass

        def process(self, sync_result):
            return {"claims_imported": 1, "errors": sync_result.errors}

    class FakePublisher:
        def publish(self, event_type, payload):
            pass

    monkeypatch.setattr("app.integrations.jobs.get_db", lambda: iter([db]))
    monkeypatch.setattr("app.integrations.jobs.IntegrationManager", FakeManager)
    monkeypatch.setattr("app.integrations.jobs.SyncOrchestrator", FakeOrchestrator)
    monkeypatch.setattr("app.integrations.jobs.EventPublisher", FakePublisher)
    monkeypatch.setattr("app.workers.tasks.sync_integration.delay", lambda *args: None)

    summary = run_sync_job(
        integration.id,
        organization.id,
        initiated_by=user.id,
        trigger="manual",
    )

    db.add(integration)
    db.refresh(integration)
    assert summary["errors"] == [rejection["message"]]
    assert integration.status == IntegrationStatus.ACTIVE
    assert integration.id in schedule_all_syncs(db)
