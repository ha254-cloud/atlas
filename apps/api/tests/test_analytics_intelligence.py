"""
Tests for the Revenue Recovery Intelligence additions to
AnalyticsRepository: executive summary, financial KPIs, payer
performance, analyst performance, revenue forecast, and auto-generated
insights.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers every model on Base.metadata before create_all()
from app.dashboard.analytics import AnalyticsRepository
from app.db.database import Base
from app.models.appeal import Appeal, AppealStatus
from app.models.claim import Claim
from app.models.denial import Denial, DenialType
from app.models.denial_code import DenialCode, DenialCodeRecoverability, DenialCodeSeverity
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.models.user import User, UserRole


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def org_id():
    return 1


def _make_patient(db, org_id, mrn):
    patient = Patient(
        organization_id=org_id,
        first_name="Jane",
        last_name="Doe",
        medical_record_number=mrn,
        date_of_birth=date(1990, 1, 1),
    )
    db.add(patient)
    db.flush()
    return patient


def _make_claim(
    db,
    org_id,
    patient_id,
    payer_id,
    claim_number,
    status="denied",
    billed=Decimal("1000.00"),
    paid=Decimal("0.00"),
    assigned_user_id=None,
    recovery_probability=None,
    created_at=None,
):
    claim = Claim(
        organization_id=org_id,
        patient_id=patient_id,
        payer_id=payer_id,
        claim_number=claim_number,
        status=status,
        billed_amount=billed,
        paid_amount=paid,
        service_date=date(2026, 1, 10),
        assigned_user_id=assigned_user_id,
        recovery_probability=recovery_probability,
    )
    db.add(claim)
    db.flush()
    if created_at is not None:
        claim.created_at = created_at
        db.flush()
    return claim


class TestExecutiveSummary:
    def test_outstanding_revenue_and_awaiting_review(self, db, org_id):
        payer = Payer(organization_id=org_id, name="Aetna", payer_code="AET")
        db.add(payer)
        db.flush()
        patient = _make_patient(db, org_id, "MRN-1")

        unassigned = _make_claim(db, org_id, patient.id, payer.id, "CLM-1", status="denied")
        _make_claim(
            db, org_id, patient.id, payer.id, "CLM-2", status="denied", assigned_user_id=999
        )

        db.add(
            RecoveryCase(
                organization_id=org_id,
                claim_id=unassigned.id,
                recovery_score=Decimal("80"),
                estimated_value=Decimal("500.00"),
                status=RecoveryStatus.OPEN,
                recommendation="Appeal",
            )
        )
        db.commit()

        summary = AnalyticsRepository(db, org_id).executive_summary()
        assert summary["outstanding_recoverable_revenue"] == 500.0
        # Only the unassigned denied claim counts as "awaiting review".
        assert summary["claims_awaiting_review"] == 1

    def test_appeals_ready_counts_only_approved(self, db, org_id):
        payer = Payer(organization_id=org_id, name="Aetna", payer_code="AET")
        db.add(payer)
        db.flush()
        patient = _make_patient(db, org_id, "MRN-1")
        claim = _make_claim(db, org_id, patient.id, payer.id, "CLM-1")

        db.add(
            Appeal(
                organization_id=org_id,
                claim_id=claim.id,
                status=AppealStatus.APPROVED,
                appeal_text="x",
            )
        )
        db.add(
            Appeal(
                organization_id=org_id,
                claim_id=claim.id,
                status=AppealStatus.SUBMITTED,
                appeal_text="x",
            )
        )
        db.add(
            Appeal(
                organization_id=org_id,
                claim_id=claim.id,
                status=AppealStatus.DRAFT,
                appeal_text="x",
            )
        )
        db.commit()

        summary = AnalyticsRepository(db, org_id).executive_summary()
        assert summary["appeals_ready"] == 1

    def test_avg_recovery_time_and_probability(self, db, org_id):
        payer = Payer(organization_id=org_id, name="Aetna", payer_code="AET")
        db.add(payer)
        db.flush()
        patient = _make_patient(db, org_id, "MRN-1")
        claim = _make_claim(
            db, org_id, patient.id, payer.id, "CLM-1", recovery_probability=Decimal("60.00")
        )

        case = RecoveryCase(
            organization_id=org_id,
            claim_id=claim.id,
            recovery_score=Decimal("80"),
            estimated_value=Decimal("500.00"),
            status=RecoveryStatus.RECOVERED,
            recommendation="Appeal",
            recovered_amount=Decimal("500.00"),
        )
        db.add(case)
        db.flush()
        case.created_at = datetime.now(UTC) - timedelta(days=20)
        case.payment_received_at = datetime.now(UTC)
        db.commit()

        summary = AnalyticsRepository(db, org_id).executive_summary()
        assert summary["avg_recovery_time_days"] == pytest.approx(20.0, abs=1.0)
        assert summary["recovery_probability_pct"] == 60.0


class TestFinancialKPIs:
    def test_gross_denied_and_net_recovered(self, db, org_id):
        payer = Payer(organization_id=org_id, name="Cigna", payer_code="CIG")
        db.add(payer)
        db.flush()
        patient = _make_patient(db, org_id, "MRN-1")

        denied = _make_claim(
            db, org_id, patient.id, payer.id, "CLM-1", status="denied", billed=Decimal("1000.00")
        )
        _make_claim(
            db,
            org_id,
            patient.id,
            payer.id,
            "CLM-2",
            status="paid",
            billed=Decimal("500.00"),
            paid=Decimal("500.00"),
        )

        db.add(
            RecoveryCase(
                organization_id=org_id,
                claim_id=denied.id,
                recovery_score=Decimal("80"),
                estimated_value=Decimal("300.00"),
                status=RecoveryStatus.RECOVERED,
                recommendation="Appeal",
                recovered_amount=Decimal("300.00"),
                atlas_fee=Decimal("60.00"),
            )
        )
        db.commit()

        kpis = AnalyticsRepository(db, org_id).financial_kpis()
        assert kpis["gross_charges"] == 1500.0
        assert kpis["denied_revenue"] == 1000.0
        assert kpis["recovered_revenue"] == 300.0
        assert kpis["net_recovered_revenue"] == 240.0
        assert kpis["cost_per_recovered_dollar"] == pytest.approx(0.2)

    def test_appeal_success_rate_is_payer_perspective(self, db, org_id):
        payer = Payer(organization_id=org_id, name="Cigna", payer_code="CIG")
        db.add(payer)
        db.flush()
        patient = _make_patient(db, org_id, "MRN-1")
        claim = _make_claim(db, org_id, patient.id, payer.id, "CLM-1")

        db.add(
            Appeal(
                organization_id=org_id,
                claim_id=claim.id,
                status=AppealStatus.ACCEPTED,
                appeal_text="x",
            )
        )
        db.add(
            Appeal(
                organization_id=org_id,
                claim_id=claim.id,
                status=AppealStatus.REJECTED,
                appeal_text="x",
            )
        )
        db.add(
            Appeal(
                organization_id=org_id,
                claim_id=claim.id,
                status=AppealStatus.DRAFT,
                appeal_text="x",
            )
        )
        db.commit()

        kpis = AnalyticsRepository(db, org_id).financial_kpis()
        assert kpis["appeal_success_rate_pct"] == 50.0


class TestPayerPerformance:
    def test_profiles_denied_claims_per_payer(self, db, org_id):
        payer_a = Payer(organization_id=org_id, name="Aetna", payer_code="AET")
        payer_b = Payer(organization_id=org_id, name="Humana", payer_code="HUM")
        db.add_all([payer_a, payer_b])
        db.flush()
        patient = _make_patient(db, org_id, "MRN-1")

        claim_a = _make_claim(
            db,
            org_id,
            patient.id,
            payer_a.id,
            "CLM-A1",
            status="denied",
            billed=Decimal("1000.00"),
            paid=Decimal("200.00"),
        )
        _make_claim(
            db,
            org_id,
            patient.id,
            payer_b.id,
            "CLM-B1",
            status="paid",
            billed=Decimal("500.00"),
            paid=Decimal("500.00"),
        )

        db.add(
            Denial(
                organization_id=org_id,
                claim_id=claim_a.id,
                denial_code="CO-16",
                denial_type=DenialType.DOCUMENTATION,
                description="Missing docs",
            )
        )
        db.commit()

        profiles = AnalyticsRepository(db, org_id).payer_performance()
        assert len(profiles) == 1
        assert profiles[0]["payer"] == "Aetna"
        assert profiles[0]["denied_claims"] == 1
        assert profiles[0]["most_common_denial_code"] == "CO-16"
        assert profiles[0]["avg_revenue_lost"] == 800.0


class TestAnalystPerformance:
    def test_attributes_revenue_and_success_rate_to_assigned_analyst(self, db, org_id):
        analyst = User(
            organization_id=org_id,
            email="analyst@atlas.dev",
            password_hash="x",
            first_name="Alex",
            last_name="Analyst",
            role=UserRole.REVENUE_ANALYST,
        )
        db.add(analyst)
        db.flush()

        payer = Payer(organization_id=org_id, name="Aetna", payer_code="AET")
        db.add(payer)
        db.flush()
        patient = _make_patient(db, org_id, "MRN-1")
        claim = _make_claim(db, org_id, patient.id, payer.id, "CLM-1", assigned_user_id=analyst.id)

        db.add(
            RecoveryCase(
                organization_id=org_id,
                claim_id=claim.id,
                recovery_score=Decimal("80"),
                estimated_value=Decimal("500.00"),
                status=RecoveryStatus.RECOVERED,
                recommendation="Appeal",
                recovered_amount=Decimal("500.00"),
            )
        )
        db.add(
            Appeal(
                organization_id=org_id,
                claim_id=claim.id,
                status=AppealStatus.ACCEPTED,
                appeal_text="x",
                submitted_by=analyst.id,
            )
        )
        db.commit()

        results = AnalyticsRepository(db, org_id).analyst_performance()
        assert len(results) == 1
        assert results[0]["name"] == "Alex Analyst"
        assert results[0]["revenue_recovered"] == 500.0
        assert results[0]["success_rate_pct"] == 100.0
        assert results[0]["claims_assigned"] == 1


class TestRevenueForecast:
    def test_buckets_by_expected_resolution_month(self, db, org_id):
        code = DenialCode(
            code="CO16",
            category=DenialType.DOCUMENTATION,
            description="Missing info",
            recovery_strategy="Submit documentation",
            typical_recovery_rate=50.0,
            typical_resolution_days=30,
            severity=DenialCodeSeverity.MEDIUM,
            recoverability=DenialCodeRecoverability.MEDIUM,
        )
        db.add(code)
        db.flush()

        payer = Payer(organization_id=org_id, name="Aetna", payer_code="AET")
        db.add(payer)
        db.flush()
        patient = _make_patient(db, org_id, "MRN-1")
        claim = _make_claim(db, org_id, patient.id, payer.id, "CLM-1")

        db.add(
            Denial(
                organization_id=org_id,
                claim_id=claim.id,
                denial_code="CO-16",
                denial_type=DenialType.DOCUMENTATION,
                description="Missing docs",
            )
        )
        db.add(
            RecoveryCase(
                organization_id=org_id,
                claim_id=claim.id,
                recovery_score=Decimal("80"),
                estimated_value=Decimal("1000.00"),
                status=RecoveryStatus.OPEN,
                recommendation="Appeal",
            )
        )
        db.commit()

        forecast = AnalyticsRepository(db, org_id).revenue_forecast(months=3)
        assert len(forecast) == 3
        total_expected = sum(f["expected_recovery"] for f in forecast)
        # 1000 * 50% recovery rate = 500, regardless of which month it lands in.
        assert total_expected == pytest.approx(500.0)


class TestInsights:
    def test_flags_denial_type_increase_week_over_week(self, db, org_id):
        payer = Payer(organization_id=org_id, name="Aetna", payer_code="AET")
        db.add(payer)
        db.flush()
        patient = _make_patient(db, org_id, "MRN-1")
        claim = _make_claim(db, org_id, patient.id, payer.id, "CLM-1")
        db.commit()

        now = datetime.now(UTC)
        # Last week: 3 documentation denials.
        for _ in range(3):
            d = Denial(
                organization_id=org_id,
                claim_id=claim.id,
                denial_code="CO-16",
                denial_type=DenialType.DOCUMENTATION,
                description="x",
            )
            db.add(d)
            db.flush()
            d.created_at = now - timedelta(days=10)
        # This week: 6 documentation denials (100% increase).
        for _ in range(6):
            d = Denial(
                organization_id=org_id,
                claim_id=claim.id,
                denial_code="CO-16",
                denial_type=DenialType.DOCUMENTATION,
                description="x",
            )
            db.add(d)
            db.flush()
            d.created_at = now - timedelta(days=2)
        db.commit()

        insights = AnalyticsRepository(db, org_id).generate_insights()
        denial_trend_messages = [i["message"] for i in insights if i["category"] == "denial_trend"]
        assert any(
            "documentation" in m.lower() and "increased" in m.lower() for m in denial_trend_messages
        )
