from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.billing.models import RecoveryFeeSchedule
from app.db.database import Base
from app.models.claim import Claim
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.recovery import Recovery
from app.payments.models import Payment, PaymentSource, PaymentStatus
from app.payments.schemas import PaymentIngest
from app.payments.service import PaymentService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _organization(db, suffix: str):
    organization = Organization(
        name=f"Hospital {suffix}",
        slug=f"hospital-{suffix.lower()}",
        email=f"billing-{suffix.lower()}@atlas.test",
        status="active",
    )
    db.add(organization)
    db.flush()
    patient = Patient(
        organization_id=organization.id,
        first_name="Jane",
        last_name="Doe",
        medical_record_number=f"MRN-{suffix}",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(
        organization_id=organization.id,
        name="Health Plan",
        payer_code=f"HP-{suffix}",
    )
    db.add_all([patient, payer])
    db.flush()
    claim = Claim(
        organization_id=organization.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number=f"CLM-PAY-{suffix}",
        status="denied",
        billed_amount=Decimal("2000.00"),
        paid_amount=Decimal("0.00"),
        currency="KES",
        service_date=date(2026, 1, 1),
    )
    db.add(claim)
    db.flush()
    return organization, claim


@pytest.mark.parametrize(
    "source",
    [
        PaymentSource.CSV,
        PaymentSource.EXCEL,
        PaymentSource.PORTAL_EXPORT,
        PaymentSource.EMAIL_REPORT,
    ],
)
def test_kenya_first_report_sources_are_supported(source):
    payload = _payload(None).model_copy(update={"source": source})

    assert payload.source == source


def _payload(claim_id: int | None, *, reference: str = "EFT-001") -> PaymentIngest:
    return PaymentIngest(
        claim_id=claim_id,
        payer_name="Health Plan",
        payment_reference=reference,
        payment_date=date(2026, 7, 15),
        expected_amount=Decimal("2000.00"),
        paid_amount=Decimal("1000.00"),
        adjustment_amount=Decimal("1000.00"),
        currency="kes",
        payment_method="eft",
        status=PaymentStatus.PAID,
        source=PaymentSource.ERA_835,
        raw_payload={"trace": reference, "segment": "CLP"},
    )


def test_ingestion_uses_effective_tenant_fee_and_is_idempotent(db):
    organization, claim = _organization(db, "ONE")
    db.add_all([
        RecoveryFeeSchedule(
            organization_id=organization.id,
            fee_percentage=Decimal("10.00"),
            vat_percentage=Decimal("0.00"),
            currency="KES",
            payment_terms_days=30,
            effective_from=date(2026, 1, 1),
            effective_to=None,
            reason="Original contract",
        ),
        RecoveryFeeSchedule(
            organization_id=organization.id,
            fee_percentage=Decimal("15.00"),
            vat_percentage=Decimal("5.00"),
            currency="KES",
            payment_terms_days=30,
            effective_from=date(2026, 7, 1),
            effective_to=None,
            reason="Amended contract",
        ),
    ])
    db.flush()

    first = PaymentService(db, organization.id).ingest(_payload(claim.id))
    replay = PaymentService(db, organization.id).ingest(_payload(claim.id))
    recovery = db.query(Recovery).one()

    assert first.created is True
    assert replay.created is False
    assert replay.payment.id == first.payment.id
    assert db.query(Payment).count() == 1
    assert db.query(Recovery).count() == 1
    assert recovery.payment_id == first.payment.id
    assert recovery.recovered_amount == Decimal("1000.00")
    assert recovery.recovery_percentage == Decimal("50.00")
    assert recovery.atlas_fee_percentage == Decimal("15.00")
    assert recovery.atlas_fee_amount == Decimal("150.00")
    assert claim.paid_amount == Decimal("1000.00")


def test_cross_tenant_claim_cannot_be_matched(db):
    first_organization, _ = _organization(db, "ONE")
    _, other_claim = _organization(db, "TWO")

    with pytest.raises(ValueError, match="Claim .* not found"):
        PaymentService(db, first_organization.id).ingest(_payload(other_claim.id))

    assert db.query(Payment).count() == 0
    assert db.query(Recovery).count() == 0


def test_unmatched_payment_is_preserved_without_recovery(db):
    organization, _ = _organization(db, "ONE")

    result = PaymentService(db, organization.id).ingest(_payload(None))

    assert result.payment.claim_id is None
    assert result.payment.matched_at is None
    assert result.payment.raw_payload == {"trace": "EFT-001", "segment": "CLP"}
    assert db.query(Recovery).count() == 0


def test_conflicting_idempotency_replay_is_rejected(db):
    organization, claim = _organization(db, "ONE")
    db.add(RecoveryFeeSchedule(
        organization_id=organization.id,
        fee_percentage=Decimal("15.00"),
        vat_percentage=Decimal("0.00"),
        currency="KES",
        payment_terms_days=30,
        effective_from=date(2026, 1, 1),
        reason="Contract",
    ))
    db.flush()
    service = PaymentService(db, organization.id)
    service.ingest(_payload(claim.id))
    conflict = _payload(claim.id).model_copy(
        update={"paid_amount": Decimal("999.00")}
    )

    with pytest.raises(ValueError, match="immutable fields: paid_amount"):
        service.ingest(conflict)

    assert db.query(Payment).count() == 1
    assert db.query(Recovery).count() == 1


def test_missing_fee_contract_blocks_recovery_but_not_unmatched_evidence(db):
    organization, claim = _organization(db, "ONE")

    with pytest.raises(ValueError, match="No recovery fee schedule"):
        PaymentService(db, organization.id).ingest(_payload(claim.id))

    db.rollback()
    unmatched = PaymentService(db, organization.id).ingest(
        _payload(None, reference="EFT-UNMATCHED")
    )
    assert unmatched.payment.id is not None


def test_unmatched_payment_candidates_are_ranked_and_tenant_scoped(db):
    organization, own_claim = _organization(db, "ONE")
    _, foreign_claim = _organization(db, "TWO")
    payment = PaymentService(db, organization.id).ingest(
        _payload(None).model_copy(
            update={
                "raw_payload": {
                    "claim_number": own_claim.claim_number,
                    "foreign_claim_number": foreign_claim.claim_number,
                }
            }
        )
    ).payment

    candidates = PaymentService(db, organization.id).candidates(payment.id)

    assert [candidate.claim_id for candidate in candidates] == [own_claim.id]
    assert candidates[0].confidence == 90
    assert candidates[0].reasons == [
        "currency_match",
        "claim_reference",
        "payer_name",
        "amount_within_outstanding",
    ]


def test_manual_match_records_provenance_and_rejects_currency_mismatch(db):
    organization, claim = _organization(db, "ONE")
    db.add(
        RecoveryFeeSchedule(
            organization_id=organization.id,
            fee_percentage=Decimal("15.00"),
            vat_percentage=Decimal("0.00"),
            currency="KES",
            payment_terms_days=30,
            effective_from=date(2026, 1, 1),
            reason="Contract",
        )
    )
    payment = PaymentService(db, organization.id).ingest(_payload(None)).payment
    service = PaymentService(db, organization.id)

    matched = service.match(
        payment.id,
        claim_id=claim.id,
        matched_by=42,
        reason="Matched to payer remittance claim reference",
    )

    assert matched.claim_id == claim.id
    assert matched.matched_by_id == 42
    assert matched.matching_method == "manual"
    assert matched.matching_reason == "Matched to payer remittance claim reference"
    assert db.query(Recovery).filter(Recovery.payment_id == payment.id).one()

    other_payment = PaymentService(db, organization.id).ingest(
        _payload(None, reference="EFT-USD").model_copy(update={"currency": "USD"})
    ).payment
    with pytest.raises(ValueError, match="does not match payment currency"):
        service.match(
            other_payment.id,
            claim_id=claim.id,
            matched_by=42,
            reason="Attempt mismatched currency",
        )
