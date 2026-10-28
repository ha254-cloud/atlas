"""
Tests for Atlas' Decision Intelligence layer (Sprint 6): the pure scoring
engine (app.decisions.scoring.DecisionEngine), the claim-level evaluation
service (app.decisions.service.DecisionService), payer statistics
(app.decisions.payer_stats_service.PayerStatisticsService), and the
read-side queue/forecast aggregations + API surface
(app.decisions.queries / app.decisions.router).
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401 — registers every model on Base.metadata
from app.core.dependencies import get_current_organization
from app.db.database import Base, get_db
from app.decisions.payer_stats_service import PayerStatisticsService
from app.decisions.queries import DecisionQueryService
from app.decisions.scoring import DecisionEngine, DecisionInput
from app.decisions.service import DecisionService
from app.main import app
from app.models.appeal import Appeal, AppealStatus
from app.models.claim import Claim, ClaimPriority
from app.models.claim_analysis import AnalysisStatus, ClaimAnalysis
from app.models.claim_decision import ClaimDecision, DecisionAction
from app.models.denial import Denial, DenialType
from app.models.denial_code import DenialCode
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.payer_statistics import PayerStatistics
from app.models.recovery_case import RecoveryCase, RecoveryStatus
from app.models.user import User, UserRole
from app.security.dependencies import get_current_user

# ---------------------------------------------------------------------------
# Pure DecisionEngine tests — no database.
# ---------------------------------------------------------------------------


class TestDecisionEngine:
    def setup_method(self):
        self.engine = DecisionEngine()

    def test_high_probability_high_value_recommends_appeal(self):
        result = self.engine.evaluate(
            DecisionInput(
                balance=Decimal("6000"),
                recovery_probability_pct=85.0,
                ai_confidence_pct=90.0,
                analyst_effort="low",
                days_until_deadline=5,
                payer_avg_payment_days=10.0,
            )
        )
        assert result.recommended_action == "appeal"
        assert result.decision_score > Decimal("70")
        assert any("deadline" in r.lower() for r in result.reasoning)

    def test_low_probability_low_value_recommends_write_off(self):
        result = self.engine.evaluate(
            DecisionInput(
                balance=Decimal("200"),
                recovery_probability_pct=15.0,
                ai_confidence_pct=40.0,
                analyst_effort="high",
            )
        )
        assert result.recommended_action == "write_off"
        assert result.potential_recovery < result.estimated_effort_cost

    def test_negative_roi_example_from_spec_recommends_write_off(self):
        # Mirrors the product spec's worked example: appeal cost $480,
        # expected recovery $120 -> "Don't Appeal".
        result = self.engine.evaluate(
            DecisionInput(
                balance=Decimal("545"),  # * 0.22 recovery probability ~= $120
                recovery_probability_pct=22.0,
                ai_confidence_pct=60.0,
                analyst_effort="high",  # ~$400 effort cost
            )
        )
        assert result.recommended_action == "write_off"

    def test_missing_documents_recommends_upload_documentation(self):
        result = self.engine.evaluate(
            DecisionInput(
                balance=Decimal("4000"),
                recovery_probability_pct=75.0,
                ai_confidence_pct=80.0,
                analyst_effort="low",
                documentation_gaps=["Operative report"],
            )
        )
        assert result.recommended_action == "upload_documentation"
        assert "Operative report" in result.reasoning[-2] or any(
            "Operative report" in r for r in result.reasoning
        )

    def test_awaiting_authorization_takes_priority(self):
        result = self.engine.evaluate(
            DecisionInput(
                balance=Decimal("4000"),
                recovery_probability_pct=75.0,
                ai_confidence_pct=80.0,
                analyst_effort="low",
                awaiting_authorization=True,
            )
        )
        assert result.recommended_action == "await_authorization"

    def test_compliance_blocking_forces_write_off(self):
        result = self.engine.evaluate(
            DecisionInput(
                balance=Decimal("9000"),
                recovery_probability_pct=90.0,
                ai_confidence_pct=95.0,
                analyst_effort="low",
                compliance_blocking=True,
            )
        )
        assert result.recommended_action == "write_off"

    def test_moderate_signals_recommend_monitor(self):
        result = self.engine.evaluate(
            DecisionInput(
                balance=Decimal("300"),
                recovery_probability_pct=35.0,
                ai_confidence_pct=50.0,
                analyst_effort="medium",
            )
        )
        assert result.recommended_action in ("monitor", "write_off")

    def test_reasoning_is_never_empty(self):
        result = self.engine.evaluate(
            DecisionInput(
                balance=Decimal("1000"),
                recovery_probability_pct=50.0,
                ai_confidence_pct=50.0,
                analyst_effort="medium",
            )
        )
        assert len(result.reasoning) > 0


# ---------------------------------------------------------------------------
# Database-backed fixtures
# ---------------------------------------------------------------------------


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

    patient = Patient(
        organization_id=org.id,
        first_name="John",
        last_name="Smith",
        medical_record_number="MRN-001",
        date_of_birth=date(1980, 1, 1),
    )
    payer = Payer(organization_id=org.id, name="Aetna", payer_code="AETNA")
    user = User(
        organization_id=org.id,
        email="admin@atlasdemo.com",
        password_hash="x",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
    )
    db_session.add_all([patient, payer, user])
    db_session.flush()

    claim = Claim(
        organization_id=org.id,
        patient_id=patient.id,
        payer_id=payer.id,
        claim_number="CLM-0001",
        status="denied",
        billed_amount=Decimal("6000.00"),
        paid_amount=Decimal("0.00"),
        service_date=date.today() - timedelta(days=20),
        priority=ClaimPriority.HIGH,
        recovery_probability=Decimal("80.00"),
        ai_risk_score=Decimal("20.00"),
    )
    db_session.add(claim)
    db_session.flush()

    denial_code = DenialCode(
        code="CO50",
        category=DenialType.MEDICAL_NECESSITY,
        description="Not medically necessary",
        recovery_strategy="Submit clinical documentation supporting necessity.",
        typical_resolution_days=30,
        required_documents=["Operative report"],
    )
    db_session.add(denial_code)
    db_session.flush()

    denial = Denial(
        organization_id=org.id,
        claim_id=claim.id,
        denial_code="CO50",
        denial_type=DenialType.MEDICAL_NECESSITY,
        description="Not medically necessary per payer review.",
    )
    db_session.add(denial)
    db_session.flush()

    analysis = ClaimAnalysis(
        organization_id=org.id,
        claim_id=claim.id,
        analysis_status=AnalysisStatus.COMPLETED,
        denial_category="medical_necessity",
        recovery_probability=Decimal("80.00"),
        confidence_score=Decimal("85.00"),
        multi_agent_result={"risk": {"estimated_effort": "low"}},
    )
    db_session.add(analysis)

    recovery_case = RecoveryCase(
        organization_id=org.id,
        claim_id=claim.id,
        recovery_score=Decimal("75.00"),
        estimated_value=Decimal("4800.00"),
        status=RecoveryStatus.OPEN,
        recommendation="Review claim and pursue recovery",
    )
    db_session.add(recovery_case)
    db_session.commit()

    return {"org": org, "claim": claim, "user": user, "payer": payer, "denial": denial}


# ---------------------------------------------------------------------------
# DecisionService
# ---------------------------------------------------------------------------


class TestDecisionService:
    def test_evaluate_claim_persists_a_decision(self, db_session, seed):
        service = DecisionService(db_session, seed["org"].id)
        decision = service.evaluate_claim(seed["claim"].id)

        assert isinstance(decision, ClaimDecision)
        assert decision.claim_id == seed["claim"].id
        assert decision.organization_id == seed["org"].id
        assert decision.recommended_action == DecisionAction.UPLOAD_DOCUMENTATION
        assert decision.potential_recovery > 0
        assert len(decision.reasoning) > 0

    def test_evaluate_claim_without_documentation_gap_recommends_appeal(self, db_session, seed):
        # Authorization on file -> documentation gap check no longer fires.
        seed["claim"].authorization_number = "AUTH-123"
        db_session.commit()

        service = DecisionService(db_session, seed["org"].id)
        decision = service.evaluate_claim(seed["claim"].id)

        assert decision.recommended_action == DecisionAction.APPEAL

    def test_get_latest_for_claim_returns_most_recent(self, db_session, seed):
        service = DecisionService(db_session, seed["org"].id)
        first = service.evaluate_claim(seed["claim"].id)
        second = service.evaluate_claim(seed["claim"].id)

        latest = service.get_latest_for_claim(seed["claim"].id)
        assert latest.id == second.id
        assert second.id != first.id

    def test_evaluate_open_claims_covers_open_recovery_cases(self, db_session, seed):
        service = DecisionService(db_session, seed["org"].id)
        results = service.evaluate_open_claims()
        assert len(results) == 1
        assert results[0].claim_id == seed["claim"].id

    def test_evaluate_claim_records_decision_generated_timeline_event(self, db_session, seed):
        from app.models.claim_event import ClaimEvent, ClaimEventType

        service = DecisionService(db_session, seed["org"].id)
        decision = service.evaluate_claim(seed["claim"].id)

        event = (
            db_session.query(ClaimEvent)
            .filter(
                ClaimEvent.claim_id == seed["claim"].id,
                ClaimEvent.event_type == ClaimEventType.DECISION_GENERATED,
            )
            .first()
        )
        assert event is not None
        assert event.event_metadata["decision_id"] == decision.id


# ---------------------------------------------------------------------------
# PayerStatisticsService
# ---------------------------------------------------------------------------


class TestPayerStatisticsService:
    def test_refresh_payer_computes_real_metrics(self, db_session, seed):
        # Record a recovered outcome + an accepted appeal so the stats
        # have real (non-null) data to compute from.
        seed["claim"].paid_amount = Decimal("0.00")
        recovery_case = (
            db_session.query(RecoveryCase).filter(RecoveryCase.claim_id == seed["claim"].id).first()
        )
        recovery_case.status = RecoveryStatus.RECOVERED
        recovery_case.recovered_amount = Decimal("4800.00")
        recovery_case.payment_received_at = datetime.now(UTC)

        appeal = Appeal(
            organization_id=seed["org"].id,
            claim_id=seed["claim"].id,
            status=AppealStatus.ACCEPTED,
            appeal_text="Appeal letter text.",
            missing_documents=None,
        )
        db_session.add(appeal)
        db_session.commit()

        stats = PayerStatisticsService(db_session, seed["org"].id).refresh_payer(seed["payer"].id)

        assert stats.sample_size == 1
        assert stats.average_denial_rate == 100.0
        assert stats.appeal_success_rate == 100.0
        assert stats.documentation_score == 100.0
        assert stats.average_recovery == Decimal("4800.00")
        assert stats.timely_filing_days == 30

    def test_refresh_all_upserts_without_duplicating(self, db_session, seed):
        service = PayerStatisticsService(db_session, seed["org"].id)
        service.refresh_all()
        service.refresh_all()

        rows = (
            db_session.query(PayerStatistics)
            .filter(PayerStatistics.organization_id == seed["org"].id)
            .all()
        )
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# DecisionQueryService (queue + executive forecast)
# ---------------------------------------------------------------------------


class TestDecisionQueryService:
    def test_queue_groups_by_recommended_action(self, db_session, seed):
        DecisionService(db_session, seed["org"].id).evaluate_claim(seed["claim"].id)

        queue = DecisionQueryService(db_session, seed["org"].id).get_queue()
        actions = {bucket["recommended_action"] for bucket in queue["buckets"]}
        assert "upload_documentation" in actions

        bucket = next(
            b for b in queue["buckets"] if b["recommended_action"] == "upload_documentation"
        )
        assert bucket["count"] == 1
        assert bucket["claims"][0]["claim_number"] == "CLM-0001"

    def test_forecast_excludes_write_offs_and_reports_confidence(self, db_session, seed):
        DecisionService(db_session, seed["org"].id).evaluate_claim(seed["claim"].id)

        forecast = DecisionQueryService(db_session, seed["org"].id).get_executive_forecast()
        assert forecast["claims_evaluated"] == 1
        assert forecast["current_recoverable_revenue"] > 0
        assert forecast["confidence"] > 0

    def test_forecast_with_no_decisions_returns_zeros(self, db_session, seed):
        forecast = DecisionQueryService(db_session, seed["org"].id).get_executive_forecast()
        assert forecast == {
            "current_recoverable_revenue": 0.0,
            "expected_recovery": 0.0,
            "confidence": 0.0,
            "average_time_days": None,
            "claims_evaluated": 0,
        }


# ---------------------------------------------------------------------------
# API-level tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db_session, seed):
    def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_organization] = lambda: seed["org"].id
    app.dependency_overrides[get_current_user] = lambda: seed["user"]

    yield TestClient(app)

    app.dependency_overrides.clear()


class TestDecisionsAPI:
    def test_evaluate_and_fetch_decision(self, client, seed):
        response = client.post(f"/api/v1/decisions/claims/{seed['claim'].id}/evaluate")
        assert response.status_code == 200
        body = response.json()
        assert body["claim_id"] == seed["claim"].id
        assert body["recommended_action"] in [a.value for a in DecisionAction]

        fetch = client.get(f"/api/v1/decisions/claims/{seed['claim'].id}")
        assert fetch.status_code == 200
        assert fetch.json()["id"] == body["id"]

    def test_decision_queue_and_forecast_endpoints(self, client, seed):
        client.post(f"/api/v1/decisions/claims/{seed['claim'].id}/evaluate")

        queue = client.get("/api/v1/decisions/queue")
        assert queue.status_code == 200
        assert len(queue.json()["buckets"]) >= 1

        forecast = client.get("/api/v1/decisions/executive-forecast")
        assert forecast.status_code == 200
        assert forecast.json()["claims_evaluated"] == 1

    def test_viewer_role_forbidden_from_evaluate_open(self, client, seed, db_session):
        seed["user"].role = UserRole.VIEWER
        db_session.commit()

        response = client.post("/api/v1/decisions/evaluate-open")
        assert response.status_code == 403

    def test_payer_statistics_refresh_endpoint(self, client, seed):
        response = client.post("/api/v1/decisions/payer-statistics/refresh")
        assert response.status_code == 200
        assert response.json()[0]["payer_id"] == seed["payer"].id
