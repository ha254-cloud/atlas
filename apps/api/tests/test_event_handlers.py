"""
Tests for the built-in Sprint 8 event handlers (app/events/handlers/*).
Each handler is exercised directly (not through the full EventPublisher/bus
plumbing, already covered by test_event_bus.py) with a real in-memory
SQLite session — the handlers' internal `from app.db.database import
get_db` is monkeypatched to yield that session (same pattern the rest of
this suite already uses for FastAPI dependency overrides, adapted for
handlers that aren't FastAPI endpoints).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models as _models  # noqa: F401 — registers every model on Base.metadata
from app.db.database import Base
from app.models.claim import Claim, ClaimPriority
from app.models.organization import Organization
from app.models.patient import Patient
from app.models.payer import Payer
from app.models.payer_statistics import PayerStatistics
from app.models.user import User, UserRole
from app.models.webhook import WebhookSubscription


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def patch_get_db(monkeypatch, db_engine):
    """Handlers open their own `get_db()` session (same convention as
    Celery tasks) and close it when done. Rather than sharing the test's
    `db_session` object directly (which would get detached the moment a
    handler closes "its" session), give each handler call a fresh Session
    bound to the same StaticPool SQLite connection — matching how the real
    app hands out a new session per request/task."""
    Session = sessionmaker(bind=db_engine)

    def _fake_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr("app.db.database.get_db", _fake_get_db)


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
    analyst = User(
        organization_id=org.id,
        email="analyst@atlasdemo.com",
        password_hash="x",
        first_name="Ana",
        last_name="Lyst",
        role=UserRole.REVENUE_ANALYST,
    )
    db_session.add_all([patient, payer, analyst])
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
        assigned_user_id=analyst.id,
    )
    db_session.add(claim)
    db_session.commit()

    return {"org": org, "claim": claim, "payer": payer, "analyst": analyst}


class TestClaimsHandler:
    def test_dispatches_analyze_claim_task_for_valid_payload(self, monkeypatch):
        from app.events.handlers.claims import ClaimsHandler

        calls = []
        monkeypatch.setattr(
            "app.workers.tasks.analyze_claim_task.delay",
            lambda claim_id, org_id: calls.append((claim_id, org_id)),
        )

        ClaimsHandler()("claim.imported", {"claim_id": 5}, 9)

        assert calls == [(5, 9)]

    def test_skips_when_claim_id_missing(self, monkeypatch):
        from app.events.handlers.claims import ClaimsHandler

        calls = []
        monkeypatch.setattr(
            "app.workers.tasks.analyze_claim_task.delay",
            lambda claim_id, org_id: calls.append((claim_id, org_id)),
        )

        ClaimsHandler()("claim.imported", {}, 9)

        assert calls == []

    def test_never_raises_if_dispatch_fails(self, monkeypatch):
        from app.events.handlers.claims import ClaimsHandler

        def _boom(claim_id, org_id):
            raise RuntimeError("no broker")

        monkeypatch.setattr("app.workers.tasks.analyze_claim_task.delay", _boom)

        ClaimsHandler()("claim.imported", {"claim_id": 5}, 9)  # must not raise


class TestAppealGeneratedHandler:
    def test_records_audit_and_advances_workflow(self, monkeypatch, patch_get_db, db_session, seed):
        from app.events.handlers.appeals import AppealGeneratedHandler
        from app.models.audit_log import AuditLog
        from app.models.claim_workflow import ClaimWorkflow, ClaimWorkflowState

        monkeypatch.setattr(
            "app.workflows.service.EventPublisher",
            lambda: type("Publisher", (), {"publish": lambda self, *args, **kwargs: None})(),
        )

        workflow = ClaimWorkflow(
            organization_id=seed["org"].id,
            claim_id=seed["claim"].id,
            state=ClaimWorkflowState.READY_FOR_APPEAL,
        )
        db_session.add(workflow)
        db_session.commit()
        workflow_id = workflow.id

        AppealGeneratedHandler()(
            "appeal.generated",
            {
                "appeal_id": 44,
                "claim_id": seed["claim"].id,
                "requested_by": seed["analyst"].id,
                "version": 1,
            },
            seed["org"].id,
        )

        db_session.rollback()
        db_session.expire_all()
        assert (
            db_session.get(ClaimWorkflow, workflow_id).state == ClaimWorkflowState.APPEAL_GENERATED
        )
        audit = db_session.query(AuditLog).filter(AuditLog.entity_id == 44).one()
        assert audit.action == "appeal.generated"
        assert audit.metadata_json == {"claim_id": seed["claim"].id, "version": 1}


class TestNotificationHandler:
    def test_emails_assigned_analyst_when_appeal_draft_is_ready(self, patch_get_db, seed):
        from app.events.handlers.notifications import NotificationHandler

        sent = []

        class _FakeEmailService:
            def send_custom(self, to, subject, body):
                sent.append((to, subject, body))

        import app.services.email_service as email_module

        original = email_module.EmailService
        email_module.EmailService = _FakeEmailService
        try:
            NotificationHandler()(
                "appeal.generated",
                {"appeal_id": 1, "claim_id": seed["claim"].id},
                seed["org"].id,
            )
        finally:
            email_module.EmailService = original

        assert len(sent) == 1
        assert "draft ready" in sent[0][1].lower()
        assert "review and edit" in sent[0][2].lower()

    def test_emails_assigned_analyst_on_appeal_approved(self, patch_get_db, seed):
        from app.events.handlers.notifications import NotificationHandler

        sent = []

        class _FakeEmailService:
            def send_custom(self, to, subject, body):
                sent.append((to, subject, body))

        import app.services.email_service as email_module

        original = email_module.EmailService
        email_module.EmailService = _FakeEmailService
        try:
            NotificationHandler()(
                "appeal.approved",
                {"appeal_id": 1, "claim_id": seed["claim"].id, "organization_id": seed["org"].id},
                seed["org"].id,
            )
        finally:
            email_module.EmailService = original

        assert len(sent) == 1
        assert sent[0][0] == "analyst@atlasdemo.com"
        assert "CLM-0001" in sent[0][1]

    def test_skips_when_claim_has_no_assigned_user(self, patch_get_db, seed, db_session):
        from app.events.handlers.notifications import NotificationHandler

        seed["claim"].assigned_user_id = None
        db_session.commit()

        sent = []

        import app.services.email_service as email_module

        class _FakeEmailService:
            def send_custom(self, to, subject, body):
                sent.append((to, subject, body))

        original = email_module.EmailService
        email_module.EmailService = _FakeEmailService
        try:
            NotificationHandler()(
                "appeal.approved",
                {"appeal_id": 1, "claim_id": seed["claim"].id},
                seed["org"].id,
            )
        finally:
            email_module.EmailService = original

        assert sent == []

    def test_skips_when_claim_id_missing(self, patch_get_db, seed):
        from app.events.handlers.notifications import NotificationHandler

        NotificationHandler()("appeal.approved", {}, seed["org"].id)  # must not raise

    def test_emails_assigned_analyst_on_claim_analyzed(self, patch_get_db, seed):
        from app.events.handlers.notifications import NotificationHandler

        sent = []

        class _FakeEmailService:
            def send_custom(self, to, subject, body):
                sent.append((to, subject, body))

        import app.services.email_service as email_module

        original = email_module.EmailService
        email_module.EmailService = _FakeEmailService
        try:
            NotificationHandler()(
                "claim.analyzed",
                {"claim_id": seed["claim"].id, "analysis_id": 1, "organization_id": seed["org"].id},
                seed["org"].id,
            )
        finally:
            email_module.EmailService = original

        assert len(sent) == 1
        assert sent[0][0] == "analyst@atlasdemo.com"
        assert "AI analysis ready" in sent[0][1]
        assert "CLM-0001" in sent[0][1]


class TestDecisionHandler:
    def test_evaluates_and_persists_a_decision_on_claim_analyzed(
        self, patch_get_db, seed, db_session
    ):
        from app.events.handlers.decisions import DecisionHandler
        from app.models.claim_decision import ClaimDecision

        seed["claim"].recovery_probability = Decimal("80.00")
        seed["claim"].ai_risk_score = Decimal("20.00")
        db_session.commit()

        DecisionHandler()(
            "claim.analyzed",
            {"claim_id": seed["claim"].id, "analysis_id": 1, "organization_id": seed["org"].id},
            seed["org"].id,
        )

        decision = (
            db_session.query(ClaimDecision)
            .filter(ClaimDecision.claim_id == seed["claim"].id)
            .first()
        )
        assert decision is not None

    def test_skips_when_claim_id_missing(self, patch_get_db, seed):
        from app.events.handlers.decisions import DecisionHandler

        DecisionHandler()("claim.analyzed", {}, seed["org"].id)  # must not raise

    def test_never_raises_when_evaluation_fails(self, patch_get_db, seed, monkeypatch):
        from app.events.handlers.decisions import DecisionHandler

        def _boom(self, claim_id):
            raise RuntimeError("boom")

        monkeypatch.setattr("app.decisions.service.DecisionService.evaluate_claim", _boom)

        DecisionHandler()(
            "claim.analyzed",
            {"claim_id": seed["claim"].id, "organization_id": seed["org"].id},
            seed["org"].id,
        )  # must not raise


class TestAnalyticsHandler:
    def test_refreshes_payer_statistics_on_payment_received(self, patch_get_db, seed, db_session):
        from app.events.handlers.analytics import AnalyticsHandler

        AnalyticsHandler()(
            "payment.received",
            {"claim_id": seed["claim"].id},
            seed["org"].id,
        )

        stats = (
            db_session.query(PayerStatistics)
            .filter(
                PayerStatistics.organization_id == seed["org"].id,
                PayerStatistics.payer_id == seed["payer"].id,
            )
            .first()
        )
        assert stats is not None
        assert stats.sample_size == 1

    def test_skips_when_organization_id_missing(self, patch_get_db, seed):
        from app.events.handlers.analytics import AnalyticsHandler

        AnalyticsHandler()(
            "payment.received", {"claim_id": seed["claim"].id}, None
        )  # must not raise


class TestDashboardHandler:
    def test_forwards_to_publish_notification_when_org_id_present(self, monkeypatch):
        from app.events.handlers.dashboard import DashboardHandler

        calls = []
        monkeypatch.setattr(
            "app.api.v1.notifications.publish_notification",
            lambda org_id, event_type, payload: calls.append((org_id, event_type, payload)),
        )

        DashboardHandler()("claim.analyzed", {"claim_id": 1}, 3)

        assert calls == [(3, "claim.analyzed", {"claim_id": 1})]

    def test_skips_when_organization_id_missing(self, monkeypatch):
        from app.events.handlers.dashboard import DashboardHandler

        calls = []
        monkeypatch.setattr(
            "app.api.v1.notifications.publish_notification",
            lambda org_id, event_type, payload: calls.append(1),
        )

        DashboardHandler()("claim.analyzed", {"claim_id": 1}, None)

        assert calls == []


class TestWebhookHandler:
    def test_queues_delivery_for_wildcard_subscription(
        self, patch_get_db, seed, db_session, monkeypatch
    ):
        from app.events.handlers.webhooks import WebhookHandler

        sub = WebhookSubscription(
            organization_id=seed["org"].id,
            target_url="https://example.com/hook",
            secret="s3cr3t",
            event_types=None,
        )
        db_session.add(sub)
        db_session.commit()

        calls = []
        monkeypatch.setattr(
            "app.workers.tasks.deliver_webhook.delay",
            lambda sub_id, event_type, payload: calls.append((sub_id, event_type, payload)),
        )

        WebhookHandler()("claim.analyzed", {"claim_id": 1}, seed["org"].id)

        assert calls == [(sub.id, "claim.analyzed", {"claim_id": 1})]

    def test_skips_subscription_not_matching_event_types(
        self, patch_get_db, seed, db_session, monkeypatch
    ):
        from app.events.handlers.webhooks import WebhookHandler

        sub = WebhookSubscription(
            organization_id=seed["org"].id,
            target_url="https://example.com/hook",
            secret="s3cr3t",
            event_types=["appeal.approved"],
        )
        db_session.add(sub)
        db_session.commit()

        calls = []
        monkeypatch.setattr("app.workers.tasks.deliver_webhook.delay", lambda *a: calls.append(a))

        WebhookHandler()("claim.analyzed", {"claim_id": 1}, seed["org"].id)

        assert calls == []

    def test_skips_inactive_subscription(self, patch_get_db, seed, db_session, monkeypatch):
        from app.events.handlers.webhooks import WebhookHandler

        sub = WebhookSubscription(
            organization_id=seed["org"].id,
            target_url="https://example.com/hook",
            secret="s3cr3t",
            event_types=None,
            is_active=False,
        )
        db_session.add(sub)
        db_session.commit()

        calls = []
        monkeypatch.setattr("app.workers.tasks.deliver_webhook.delay", lambda *a: calls.append(a))

        WebhookHandler()("claim.analyzed", {"claim_id": 1}, seed["org"].id)

        assert calls == []
