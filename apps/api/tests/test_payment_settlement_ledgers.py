from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401
from app.audit.actions import AuditAction
from app.billing.models import RecoveryFeeSchedule
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.events.event_types import EventType
from app.main import app
from app.models.audit_log import AuditLog
from app.models.claim import Claim
from app.models.invoice import Invoice, InvoiceCreditNote, InvoiceLine, InvoiceStatus
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.recovery import Recovery
from app.models.user import User, UserRole
from app.payments.models import (
    Payment,
    PaymentAllocation,
    PaymentAllocationType,
    PaymentSource,
    PaymentStatus,
)
from app.payments.schemas import (
    PaymentAllocationAdjustmentCreate,
    PaymentAllocationBatchCreate,
    PaymentIngest,
    SettlementEvidenceCreate,
)
from app.payments.service import PaymentService
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


def _tenant(db, suffix: str):
    organization = Organization(
        name=f"Hospital {suffix}",
        slug=f"hospital-{suffix.lower()}",
        email=f"finance-{suffix.lower()}@atlas.test",
        currency="KES",
    )
    db.add(organization)
    db.flush()
    user = User(
        organization_id=organization.id,
        email=f"owner-{suffix.lower()}@atlas.test",
        password_hash="x",
        first_name="Finance",
        last_name=suffix,
        role=UserRole.OWNER,
    )
    patient = Patient(
        organization_id=organization.id,
        first_name="Jane",
        last_name=suffix,
        medical_record_number=f"MRN-SETTLEMENT-{suffix}",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(
        organization_id=organization.id,
        name="Social Health Authority",
        payer_code=f"SHA-{suffix}",
    )
    db.add_all([user, patient, payer])
    db.flush()
    claims = []
    for index, billed_amount in enumerate(
        (Decimal("700.00"), Decimal("300.00")),
        start=1,
    ):
        claim = Claim(
            organization_id=organization.id,
            patient_id=patient.id,
            payer_id=payer.id,
            claim_number=f"SETTLEMENT-{suffix}-{index}",
            status="denied",
            billed_amount=billed_amount,
            paid_amount=Decimal("0.00"),
            currency="KES",
            service_date=date(2026, 10, index),
        )
        db.add(claim)
        claims.append(claim)
    db.flush()
    db.add(
        RecoveryFeeSchedule(
            organization_id=organization.id,
            fee_percentage=Decimal("10.00"),
            vat_percentage=Decimal("5.00"),
            currency="KES",
            payment_terms_days=30,
            effective_from=date(2026, 1, 1),
            reason="Kenya design-partner fee schedule",
        )
    )
    db.flush()
    return organization, user, claims


def _payment(db, organization) -> Payment:
    return PaymentService(db, organization.id).ingest(
        PaymentIngest(
            payer_name="Social Health Authority",
            payment_reference=f"SHA-BULK-{organization.id}",
            payment_date=date(2026, 10, 15),
            expected_amount=Decimal("1000.00"),
            paid_amount=Decimal("1000.00"),
            adjustment_amount=Decimal("0.00"),
            currency="KES",
            payment_method="eft",
            status=PaymentStatus.PAID,
            source=PaymentSource.CSV,
            raw_payload={"settlement_batch": f"SHA-{organization.id}"},
        ),
        actor_id=None,
        correlation_id=f"payment-{organization.id}",
    ).payment


@pytest.fixture()
def seeded(db):
    organization, user, claims = _tenant(db, "ONE")
    viewer = User(
        organization_id=organization.id,
        email="viewer-one@atlas.test",
        password_hash="x",
        first_name="View",
        last_name="Only",
        role=UserRole.VIEWER,
    )
    db.add(viewer)
    payment = _payment(db, organization)
    other_organization, other_user, other_claims = _tenant(db, "TWO")
    other_payment = _payment(db, other_organization)
    db.commit()
    return {
        "organization": organization,
        "user": user,
        "viewer": viewer,
        "claims": claims,
        "payment": payment,
        "other_organization": other_organization,
        "other_user": other_user,
        "other_claims": other_claims,
        "other_payment": other_payment,
    }


@pytest.fixture()
def client(db, seeded):
    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: seeded["organization"].id
    app.dependency_overrides[get_current_user] = lambda: seeded["user"]
    yield TestClient(app)
    app.dependency_overrides.clear()


def _bulk_payload(claims) -> PaymentAllocationBatchCreate:
    return PaymentAllocationBatchCreate(
        allocations=[
            {"claim_id": claims[0].id, "amount": "700.00"},
            {"claim_id": claims[1].id, "amount": "300.00"},
        ],
        reason="Allocate SHA settlement report across the referenced claims",
        idempotency_key="sha-bulk-allocation-001",
    )


def test_bulk_partial_allocation_is_atomic_idempotent_and_tenant_scoped(db, seeded):
    service = PaymentService(db, seeded["organization"].id)
    payload = _bulk_payload(seeded["claims"])

    first = service.allocate(
        seeded["payment"].id,
        payload,
        actor_id=seeded["user"].id,
        actor_type="user",
        correlation_id="allocation-request-001",
    )
    replay = service.allocate(
        seeded["payment"].id,
        payload,
        actor_id=seeded["user"].id,
        actor_type="user",
        correlation_id="allocation-request-001",
    )

    assert first.created is True
    assert replay.created is False
    assert first.allocated_amount == Decimal("1000.00")
    assert first.unallocated_amount == Decimal("0.00")
    assert [row.amount for row in first.allocations] == [
        Decimal("700.00"),
        Decimal("300.00"),
    ]
    assert db.query(PaymentAllocation).count() == 2
    assert db.query(Recovery).count() == 2
    assert [claim.paid_amount for claim in seeded["claims"]] == [
        Decimal("700.00"),
        Decimal("300.00"),
    ]
    assert seeded["payment"].claim_id is None
    assert seeded["payment"].matching_method == "bulk_allocation"

    foreign_payload = PaymentAllocationBatchCreate(
        allocations=[
            {"claim_id": seeded["other_claims"][0].id, "amount": "1.00"},
        ],
        reason="Attempt cross-tenant allocation",
        idempotency_key="cross-tenant-allocation",
    )
    with pytest.raises(ValueError, match="not found"):
        service.allocate(
            seeded["payment"].id,
            foreign_payload,
            actor_id=seeded["user"].id,
            actor_type="user",
            correlation_id="cross-tenant-request",
        )


def test_sequential_partial_allocations_keep_candidates_and_clear_legacy_pointer(
    client,
    db,
    seeded,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.api.v1.payments.EventPublisher.publish",
        lambda *_args, **_kwargs: None,
    )
    service = PaymentService(db, seeded["organization"].id)
    first = service.allocate(
        seeded["payment"].id,
        PaymentAllocationBatchCreate(
            allocations=[{"claim_id": seeded["claims"][0].id, "amount": "700.00"}],
            reason="Allocate the first claim from the SHA settlement",
            idempotency_key="sequential-allocation-001",
        ),
        actor_id=seeded["user"].id,
        actor_type="user",
        correlation_id="sequential-allocation-request-001",
    )

    assert first.unallocated_amount == Decimal("300.00")
    assert seeded["payment"].claim_id == seeded["claims"][0].id
    candidates = service.candidates(seeded["payment"].id)
    assert [candidate.claim_id for candidate in candidates] == [
        seeded["claims"][1].id
    ]
    assert "exact_outstanding_amount" in candidates[0].reasons

    service.allocate(
        seeded["payment"].id,
        PaymentAllocationBatchCreate(
            allocations=[{"claim_id": seeded["claims"][1].id, "amount": "300.00"}],
            reason="Allocate the remaining SHA settlement",
            idempotency_key="sequential-allocation-002",
        ),
        actor_id=seeded["user"].id,
        actor_type="user",
        correlation_id="sequential-allocation-request-002",
    )
    db.commit()

    assert seeded["payment"].claim_id is None
    assert service.candidates(seeded["payment"].id) == []
    ledger = client.get("/api/v1/payments")
    assert ledger.status_code == 200
    assert {
        (row["payment_id"], row["claim_id"])
        for row in ledger.json()["payments"]
    } == {
        (seeded["payment"].id, seeded["claims"][0].id),
        (seeded["payment"].id, seeded["claims"][1].id),
    }
    assert ledger.json()["summary"]["payment_count"] == 1


def test_settlement_evidence_api_is_idempotent_audited_and_evented(
    client,
    db,
    seeded,
    monkeypatch,
):
    published = []
    monkeypatch.setattr(
        "app.api.v1.payments.EventPublisher.publish",
        lambda _publisher, event_type, payload, organization_id=None: published.append(
            (event_type, payload, organization_id)
        ),
    )
    payload = {
        "evidence_type": "settlement_report",
        "settlement_reference": "SHA-REPORT-2026-10-15",
        "amount": "1000.00",
        "currency": "KES",
        "received_at": "2026-10-15T09:30:00Z",
        "source_hash": "a" * 64,
        "reason": "Finance validated the SHA settlement report",
        "idempotency_key": "sha-settlement-report-001",
    }

    created = client.post(
        f"/api/v1/payments/records/{seeded['payment'].id}/settlement-evidence",
        json=payload,
    )
    replay = client.post(
        f"/api/v1/payments/records/{seeded['payment'].id}/settlement-evidence",
        json=payload,
    )
    conflict = client.post(
        f"/api/v1/payments/records/{seeded['payment'].id}/settlement-evidence",
        json={**payload, "reason": "Conflicting replay"},
    )

    assert created.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == created.json()["id"]
    assert conflict.status_code == 409
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.action
            == AuditAction.PAYMENT_SETTLEMENT_EVIDENCE_RECORDED.value
        )
        .one()
    )
    assert audit.organization_id == seeded["organization"].id
    assert audit.correlation_id == created.headers["x-request-id"]
    assert audit.after_state["currency"] == "KES"
    assert published[0][0] == EventType.PAYMENT_SETTLEMENT_EVIDENCE_RECORDED
    assert published[0][1]["settlement_evidence_id"] == created.json()["id"]
    assert published[0][2] == seeded["organization"].id
    assert len(published) == 1


def test_settlement_evidence_replay_normalizes_sqlite_datetime(db, seeded):
    service = PaymentService(db, seeded["organization"].id)
    payload = SettlementEvidenceCreate(
        evidence_type="bank_statement",
        settlement_reference="BANK-STATEMENT-001",
        amount=Decimal("1000.00"),
        currency="KES",
        received_at=datetime(2026, 10, 15, 9, 30, tzinfo=UTC),
        source_hash="b" * 64,
        reason="Finance validated the bank statement",
        idempotency_key="bank-statement-001",
    )
    created, was_created = service.record_settlement_evidence(
        seeded["payment"].id,
        payload,
        actor_id=seeded["user"].id,
        correlation_id="bank-statement-request-001",
    )
    db.commit()
    db.expire_all()
    replay, replay_created = service.record_settlement_evidence(
        seeded["payment"].id,
        payload,
        actor_id=seeded["user"].id,
        correlation_id="bank-statement-request-001",
    )

    assert was_created is True
    assert replay_created is False
    assert replay.id == created.id


def test_reversal_updates_projection_and_is_append_only(db, seeded):
    service = PaymentService(db, seeded["organization"].id)
    allocation = service.allocate(
        seeded["payment"].id,
        _bulk_payload(seeded["claims"]),
        actor_id=seeded["user"].id,
        actor_type="user",
        correlation_id="allocation-request-002",
    ).allocations[0]

    result = service.adjust_allocation(
        allocation.id,
        PaymentAllocationAdjustmentCreate(
            adjustment_type=PaymentAllocationType.REVERSAL,
            amount=Decimal("200.00"),
            reason="Payer reversed part of the SHA settlement",
            idempotency_key="sha-reversal-001",
        ),
        actor_id=seeded["user"].id,
        correlation_id="reversal-request-001",
    )
    replay = service.adjust_allocation(
        allocation.id,
        PaymentAllocationAdjustmentCreate(
            adjustment_type=PaymentAllocationType.REVERSAL,
            amount=Decimal("200.00"),
            reason="Payer reversed part of the SHA settlement",
            idempotency_key="sha-reversal-001",
        ),
        actor_id=seeded["user"].id,
        correlation_id="reversal-request-001",
    )

    recovery = (
        db.query(Recovery)
        .filter(
            Recovery.payment_id == seeded["payment"].id,
            Recovery.claim_id == seeded["claims"][0].id,
        )
        .one()
    )
    assert result.created is True
    assert replay.created is False
    assert result.credit_note_id is None
    assert recovery.recovered_amount == Decimal("500.00")
    assert recovery.atlas_fee_amount == Decimal("50.00")
    assert seeded["claims"][0].paid_amount == Decimal("500.00")
    assert seeded["payment"].unallocated_amount == Decimal("0.00")
    assert service.candidates(seeded["payment"].id) == []

    result.allocation.reason = "Attempt to overwrite immutable evidence"
    with pytest.raises(DatabaseError, match="payment ledgers are immutable"):
        db.commit()
    db.rollback()


def test_invoiced_refund_issues_idempotent_credit_note(db, seeded):
    service = PaymentService(db, seeded["organization"].id)
    allocation = service.allocate(
        seeded["payment"].id,
        PaymentAllocationBatchCreate(
            allocations=[
                {"claim_id": seeded["claims"][0].id, "amount": "700.00"},
            ],
            reason="Allocate the settled claim",
            idempotency_key="invoice-allocation-001",
        ),
        actor_id=seeded["user"].id,
        actor_type="user",
        correlation_id="invoice-allocation-request",
    ).allocations[0]
    recovery = db.query(Recovery).one()
    recovery.verified = True
    recovery.verified_by = seeded["user"].id
    recovery.verified_at = datetime.now(UTC)
    recovery.verification_reason = "Finance verified settlement evidence"
    invoice = Invoice(
        organization_id=seeded["organization"].id,
        invoice_number="ATL-1-202610",
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        status=InvoiceStatus.SENT,
        total_recovered_amount=Decimal("700.00"),
        total_fee_amount=Decimal("70.00"),
        vat_percentage=Decimal("5.00"),
        vat_amount=Decimal("3.50"),
        total_amount=Decimal("73.50"),
        currency="KES",
        payment_terms_days=30,
        due_date=date(2026, 11, 30),
        billing_name=seeded["organization"].name,
        billing_email=seeded["organization"].email,
    )
    db.add(invoice)
    db.flush()
    db.add(
        InvoiceLine(
            invoice_id=invoice.id,
            recovery_id=recovery.id,
            payment_id=seeded["payment"].id,
            claim_id=seeded["claims"][0].id,
            recovered_amount=Decimal("700.00"),
            fee_percentage=Decimal("10.00"),
            fee_amount=Decimal("70.00"),
            payment_date=date(2026, 10, 15),
        )
    )
    db.flush()

    payload = PaymentAllocationAdjustmentCreate(
        adjustment_type=PaymentAllocationType.REFUND,
        amount=Decimal("200.00"),
        reason="Refund confirmed by payer settlement advice",
        idempotency_key="sha-refund-001",
    )
    first = service.adjust_allocation(
        allocation.id,
        payload,
        actor_id=seeded["user"].id,
        correlation_id="refund-request-001",
    )
    replay = service.adjust_allocation(
        allocation.id,
        payload,
        actor_id=seeded["user"].id,
        correlation_id="refund-request-001",
    )

    credit_note = db.query(InvoiceCreditNote).one()
    assert first.credit_note_id == credit_note.id
    assert replay.credit_note_id == credit_note.id
    assert db.query(InvoiceCreditNote).count() == 1
    assert credit_note.recovered_adjustment_amount == Decimal("200.00")
    assert credit_note.fee_adjustment_amount == Decimal("20.00")
    assert credit_note.vat_adjustment_amount == Decimal("1.00")
    assert credit_note.total_credit_amount == Decimal("21.00")
    assert credit_note.currency == "KES"


def test_settlement_allocation_apis_reject_cross_tenant_ids(client, seeded):
    foreign_payment_id = seeded["other_payment"].id

    evidence = client.get(
        f"/api/v1/payments/records/{foreign_payment_id}/settlement-evidence"
    )
    allocations = client.post(
        f"/api/v1/payments/records/{foreign_payment_id}/allocations",
        json={
            "allocations": [
                {"claim_id": seeded["claims"][0].id, "amount": "100.00"},
            ],
            "reason": "Attempt cross-tenant payment allocation",
            "idempotency_key": "foreign-payment-allocation",
        },
    )

    assert evidence.status_code == 404
    assert allocations.status_code == 404


def test_allocation_and_adjustment_apis_emit_audit_events_and_credit_note(
    client,
    db,
    seeded,
    monkeypatch,
):
    published = []
    monkeypatch.setattr(
        "app.api.v1.payments.EventPublisher.publish",
        lambda _publisher, event_type, payload, organization_id=None: published.append(
            (event_type, payload, organization_id)
        ),
    )
    allocated = client.post(
        f"/api/v1/payments/records/{seeded['payment'].id}/allocations",
        json={
            "allocations": [
                {"claim_id": seeded["claims"][0].id, "amount": "700.00"},
            ],
            "reason": "Allocate the settled SHA claim",
            "idempotency_key": "api-allocation-001",
        },
    )
    assert allocated.status_code == 201
    allocation_id = allocated.json()["allocations"][0]["id"]
    recovery = db.query(Recovery).one()
    recovery.verified = True
    recovery.verified_by = seeded["user"].id
    recovery.verified_at = datetime.now(UTC)
    recovery.verification_reason = "Finance verified settlement evidence"
    invoice = Invoice(
        organization_id=seeded["organization"].id,
        invoice_number="ATL-API-202610",
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        status=InvoiceStatus.SENT,
        total_recovered_amount=Decimal("700.00"),
        total_fee_amount=Decimal("70.00"),
        vat_percentage=Decimal("5.00"),
        vat_amount=Decimal("3.50"),
        total_amount=Decimal("73.50"),
        currency="KES",
        payment_terms_days=30,
        due_date=date(2026, 11, 30),
        billing_name=seeded["organization"].name,
        billing_email=seeded["organization"].email,
    )
    db.add(invoice)
    db.flush()
    db.add(
        InvoiceLine(
            invoice_id=invoice.id,
            recovery_id=recovery.id,
            payment_id=seeded["payment"].id,
            claim_id=seeded["claims"][0].id,
            recovered_amount=Decimal("700.00"),
            fee_percentage=Decimal("10.00"),
            fee_amount=Decimal("70.00"),
            payment_date=date(2026, 10, 15),
        )
    )
    db.commit()

    adjusted = client.post(
        f"/api/v1/payments/allocations/{allocation_id}/adjustments",
        json={
            "adjustment_type": "refund",
            "amount": "200.00",
            "reason": "Refund confirmed by SHA settlement advice",
            "idempotency_key": "api-refund-001",
        },
    )
    adjustment_id = adjusted.json()["id"]
    invoice_line = db.query(InvoiceLine).one()
    db.add(
        InvoiceCreditNote(
            organization_id=seeded["other_organization"].id,
            invoice_id=invoice.id,
            invoice_line_id=invoice_line.id,
            payment_allocation_id=adjustment_id,
            credit_note_number="ATL-CN-FOREIGN-001",
            adjustment_type="refund",
            recovered_adjustment_amount=Decimal("1.00"),
            fee_adjustment_amount=Decimal("0.10"),
            vat_adjustment_amount=Decimal("0.01"),
            total_credit_amount=Decimal("0.11"),
            currency="KES",
            reason="Cross-tenant list isolation fixture",
            issued_by=seeded["other_user"].id,
            correlation_id="foreign-credit-note-request",
        )
    )
    db.commit()
    credit_notes = client.get("/api/v1/invoices/credit-notes")

    assert adjusted.status_code == 201
    assert adjusted.json()["parent_allocation_id"] == allocation_id
    assert db.query(InvoiceCreditNote).count() == 2
    assert credit_notes.status_code == 200
    assert len(credit_notes.json()) == 1
    assert credit_notes.json()[0]["organization_id"] == seeded["organization"].id
    assert credit_notes.json()[0]["currency"] == "KES"
    assert credit_notes.json()[0]["total_credit_amount"] == 21.0
    audits = {
        row.action: row
        for row in db.query(AuditLog)
        .filter(
            AuditLog.action.in_(
                [
                    AuditAction.PAYMENT_ALLOCATED.value,
                    AuditAction.PAYMENT_ALLOCATION_ADJUSTED.value,
                    AuditAction.INVOICE_CREDIT_NOTE_ISSUED.value,
                ]
            )
        )
        .all()
    }
    assert set(audits) == {
        AuditAction.PAYMENT_ALLOCATED.value,
        AuditAction.PAYMENT_ALLOCATION_ADJUSTED.value,
        AuditAction.INVOICE_CREDIT_NOTE_ISSUED.value,
    }
    assert audits[AuditAction.PAYMENT_ALLOCATED.value].correlation_id == (
        allocated.headers["x-request-id"]
    )
    assert audits[AuditAction.PAYMENT_ALLOCATION_ADJUSTED.value].correlation_id == (
        adjusted.headers["x-request-id"]
    )
    assert [event[0] for event in published] == [
        EventType.PAYMENT_ALLOCATED,
        EventType.PAYMENT_ALLOCATION_ADJUSTED,
        EventType.INVOICE_CREDIT_NOTE_ISSUED,
    ]
    assert all(event[2] == seeded["organization"].id for event in published)


def test_viewer_cannot_manage_settlement_ledgers(client, seeded):
    app.dependency_overrides[get_current_user] = lambda: seeded["viewer"]

    evidence = client.get(
        f"/api/v1/payments/records/{seeded['payment'].id}/settlement-evidence"
    )
    allocations = client.get(
        f"/api/v1/payments/records/{seeded['payment'].id}/allocations"
    )
    credit_notes = client.get("/api/v1/invoices/credit-notes")

    assert evidence.status_code == 403
    assert allocations.status_code == 403
    assert credit_notes.status_code == 403
