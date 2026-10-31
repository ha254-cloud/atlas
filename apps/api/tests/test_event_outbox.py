"""
Tests for the transactional domain-event outbox: EventPublisher's durable
(db-backed) path writes a DomainEventOutbox row instead of dispatching
in-process, and OutboxDispatcher.dispatch_batch/dispatch_one are what
actually invoke the event bus — with retry/backoff on handler failure and
dead-lettering once attempts are exhausted. Mirrors the in-memory
EventBus/EventPublisher coverage in test_event_bus.py, but exercises the
durable path end to end against an in-memory sqlite engine.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.branches.models  # noqa: F401 — Claim.branch_id FKs here; not in app.models/__init__
import app.models  # noqa: F401 — registers every model on Base.metadata before create_all()
from app.db.database import Base
from app.events.bus import EventBus
from app.events.event_types import EventType
from app.events.models import DomainEventOutbox, DomainEventOutboxStatus
from app.events.outbox import OutboxDispatcher
from app.events.publisher import EventPublisher
from app.organizations.models import Organization


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def org_id(db):
    org = Organization(name="Atlas Demo Clinic", email="org@atlasdemo.com")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org.id


class TestDurablePublish:
    def test_publish_with_db_writes_pending_outbox_row_instead_of_dispatching(
        self, db, org_id, monkeypatch
    ):
        test_bus = EventBus()
        monkeypatch.setattr("app.events.publisher.event_bus", test_bus)
        calls = []
        test_bus.subscribe("*", lambda et, payload, org: calls.append(et))

        event_id = EventPublisher(db).publish(
            EventType.CLAIM_IMPORTED, {"claim_id": 1}, organization_id=org_id
        )
        db.commit()

        assert calls == []  # not dispatched synchronously — only queued
        row = db.query(DomainEventOutbox).filter_by(event_id=event_id).one()
        assert row.status == DomainEventOutboxStatus.PENDING.value
        assert row.organization_id == org_id
        assert row.event_type == "claim.imported"
        assert row.payload["claim_id"] == 1
        assert row.attempts == 0

    def test_publish_with_db_requires_organization_id(self, db):
        with pytest.raises(ValueError):
            EventPublisher(db).publish(EventType.CLAIM_IMPORTED, {"claim_id": 1})

    def test_publish_without_db_still_dispatches_synchronously(self, monkeypatch):
        test_bus = EventBus()
        monkeypatch.setattr("app.events.publisher.event_bus", test_bus)
        calls = []
        test_bus.subscribe("*", lambda et, payload, org: calls.append(et))

        EventPublisher().publish(EventType.CLAIM_IMPORTED, {"claim_id": 1}, organization_id=1)

        assert calls == ["claim.imported"]


class TestOutboxDispatcher:
    def _enqueue(self, db, org_id, event_type=EventType.CLAIM_IMPORTED, payload=None):
        event_id = EventPublisher(db).publish(
            event_type, payload or {"claim_id": 1}, organization_id=org_id
        )
        db.commit()
        return event_id

    def test_dispatch_batch_publishes_pending_events_and_runs_subscribers(
        self, db, org_id, monkeypatch
    ):
        test_bus = EventBus()
        monkeypatch.setattr("app.events.outbox.event_bus", test_bus)
        calls = []
        test_bus.subscribe(EventType.CLAIM_IMPORTED, lambda et, p, org: calls.append((et, org)))

        event_id = self._enqueue(db, org_id)
        published = OutboxDispatcher(db, bus=test_bus).dispatch_batch()

        assert published == 1
        assert calls == [("claim.imported", org_id)]
        row = db.query(DomainEventOutbox).filter_by(event_id=event_id).one()
        assert row.status == DomainEventOutboxStatus.PUBLISHED.value
        assert row.published_at is not None
        assert row.last_error is None

    def test_dispatch_batch_ignores_events_not_yet_available(self, db, org_id, monkeypatch):
        test_bus = EventBus()
        monkeypatch.setattr("app.events.outbox.event_bus", test_bus)
        self._enqueue(db, org_id)
        future_row = db.query(DomainEventOutbox).one()
        future_row.available_at = datetime.now(UTC) + timedelta(hours=1)
        db.commit()

        published = OutboxDispatcher(db, bus=test_bus).dispatch_batch()

        assert published == 0

    def test_failed_handler_retries_with_backoff_and_records_error(self, db, org_id, monkeypatch):
        test_bus = EventBus()
        monkeypatch.setattr("app.events.outbox.event_bus", test_bus)

        def bad_handler(et, payload, org):
            raise RuntimeError("payer webhook timed out")

        test_bus.subscribe(EventType.CLAIM_IMPORTED, bad_handler)
        event_id = self._enqueue(db, org_id)

        dispatcher = OutboxDispatcher(
            db, bus=test_bus, max_attempts=5, base_retry_seconds=10, max_retry_seconds=300
        )
        published = dispatcher.dispatch_batch()

        assert published == 0
        row = db.query(DomainEventOutbox).filter_by(event_id=event_id).one()
        assert row.status == DomainEventOutboxStatus.PENDING.value
        assert row.attempts == 1
        assert "payer webhook timed out" in row.last_error
        # sqlite round-trips DateTime(timezone=True) as naive — compare naive here.
        assert row.available_at > datetime.now(UTC).replace(tzinfo=None)

    def test_event_is_dead_lettered_after_max_attempts(self, db, org_id, monkeypatch):
        test_bus = EventBus()
        monkeypatch.setattr("app.events.outbox.event_bus", test_bus)

        def bad_handler(et, payload, org):
            raise RuntimeError("boom")

        test_bus.subscribe(EventType.CLAIM_IMPORTED, bad_handler)
        event_id = self._enqueue(db, org_id)
        row = db.query(DomainEventOutbox).filter_by(event_id=event_id).one()
        row.attempts = 4  # one dispatch away from the 5-attempt ceiling
        db.commit()

        dispatcher = OutboxDispatcher(db, bus=test_bus, max_attempts=5)
        published = dispatcher.dispatch_batch()

        assert published == 0
        row = db.query(DomainEventOutbox).filter_by(event_id=event_id).one()
        assert row.status == DomainEventOutboxStatus.DEAD_LETTER.value
        assert row.attempts == 5

    def test_dispatch_batch_processes_multiple_pending_events_in_order(
        self, db, org_id, monkeypatch
    ):
        test_bus = EventBus()
        monkeypatch.setattr("app.events.outbox.event_bus", test_bus)
        calls = []
        test_bus.subscribe("*", lambda et, p, org: calls.append(p["claim_id"]))

        self._enqueue(db, org_id, payload={"claim_id": 1})
        self._enqueue(db, org_id, payload={"claim_id": 2})
        self._enqueue(db, org_id, payload={"claim_id": 3})

        published = OutboxDispatcher(db, bus=test_bus).dispatch_batch()

        assert published == 3
        assert calls == [1, 2, 3]

    def test_dispatch_one_returns_false_for_unknown_or_unavailable_event(self, db, org_id):
        assert OutboxDispatcher(db).dispatch_one(999999) is False
