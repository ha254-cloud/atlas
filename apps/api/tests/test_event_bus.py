"""
Pure unit tests for the Sprint 8 EventBus (app.events.bus) — no database,
no FastAPI app. Covers: subscribe/dispatch by exact event type, the "*"
wildcard subscription, unsubscribe, and handler-failure isolation (one
raising handler must not stop others or bubble up to the caller).
"""

from app.events.bus import ALL_EVENTS, EventBus
from app.events.event_types import EventType
from app.events.publisher import EventPublisher


class TestEventBusSubscribeDispatch:
    def test_dispatch_calls_subscribed_handler_with_type_payload_org(self):
        bus = EventBus()
        calls = []
        bus.subscribe(
            EventType.CLAIM_IMPORTED, lambda et, payload, org: calls.append((et, payload, org))
        )

        bus.dispatch(EventType.CLAIM_IMPORTED, {"claim_id": 1}, organization_id=7)

        assert calls == [("claim.imported", {"claim_id": 1}, 7)]

    def test_dispatch_ignores_handlers_subscribed_to_other_event_types(self):
        bus = EventBus()
        calls = []
        bus.subscribe(EventType.CLAIM_ANALYZED, lambda et, payload, org: calls.append(et))

        bus.dispatch(EventType.CLAIM_IMPORTED, {}, organization_id=1)

        assert calls == []

    def test_accepts_plain_string_event_type_on_both_sides(self):
        bus = EventBus()
        calls = []
        bus.subscribe("claim.imported", lambda et, payload, org: calls.append(et))

        bus.dispatch(EventType.CLAIM_IMPORTED, {}, organization_id=1)

        assert calls == ["claim.imported"]

    def test_wildcard_subscriber_receives_every_event_type(self):
        bus = EventBus()
        calls = []
        bus.subscribe(ALL_EVENTS, lambda et, payload, org: calls.append(et))

        bus.dispatch(EventType.CLAIM_IMPORTED, {}, organization_id=1)
        bus.dispatch(EventType.APPEAL_APPROVED, {}, organization_id=1)

        assert calls == ["claim.imported", "appeal.approved"]

    def test_specific_and_wildcard_handlers_both_run_for_same_event(self):
        bus = EventBus()
        calls = []
        bus.subscribe(EventType.PAYMENT_RECEIVED, lambda et, payload, org: calls.append("specific"))
        bus.subscribe(ALL_EVENTS, lambda et, payload, org: calls.append("wildcard"))

        bus.dispatch(EventType.PAYMENT_RECEIVED, {}, organization_id=1)

        assert sorted(calls) == ["specific", "wildcard"]

    def test_multiple_handlers_for_same_event_all_run(self):
        bus = EventBus()
        calls = []
        bus.subscribe(EventType.CLAIM_IMPORTED, lambda et, payload, org: calls.append("a"))
        bus.subscribe(EventType.CLAIM_IMPORTED, lambda et, payload, org: calls.append("b"))

        bus.dispatch(EventType.CLAIM_IMPORTED, {}, organization_id=1)

        assert sorted(calls) == ["a", "b"]

    def test_dispatch_with_no_subscribers_does_not_raise(self):
        bus = EventBus()
        bus.dispatch(
            EventType.CLAIM_IMPORTED, {}, organization_id=1
        )  # no assertion needed — just must not raise

    def test_unsubscribe_removes_handler(self):
        bus = EventBus()
        calls = []

        def handler(event_type, payload, organization_id):
            calls.append(event_type)

        bus.subscribe(EventType.CLAIM_IMPORTED, handler)
        bus.unsubscribe(EventType.CLAIM_IMPORTED, handler)

        bus.dispatch(EventType.CLAIM_IMPORTED, {}, organization_id=1)

        assert calls == []

    def test_clear_removes_all_subscribers(self):
        bus = EventBus()
        calls = []
        bus.subscribe(ALL_EVENTS, lambda et, payload, org: calls.append(et))
        bus.clear()

        bus.dispatch(EventType.CLAIM_IMPORTED, {}, organization_id=1)

        assert calls == []


class TestEventBusFailureIsolation:
    def test_one_raising_handler_does_not_stop_others(self):
        bus = EventBus()
        calls = []

        def bad_handler(et, payload, org):
            raise RuntimeError("boom")

        def good_handler(et, payload, org):
            calls.append("good")

        bus.subscribe(EventType.CLAIM_IMPORTED, bad_handler)
        bus.subscribe(EventType.CLAIM_IMPORTED, good_handler)

        bus.dispatch(EventType.CLAIM_IMPORTED, {}, organization_id=1)  # must not raise

        assert calls == ["good"]

    def test_raising_handler_does_not_propagate_to_caller(self):
        bus = EventBus()

        def bad_handler(et, payload, org):
            raise ValueError("nope")

        bus.subscribe(EventType.CLAIM_IMPORTED, bad_handler)

        bus.dispatch(EventType.CLAIM_IMPORTED, {}, organization_id=1)  # should not raise ValueError


class TestEventPublisherDispatchesThroughBus:
    """EventPublisher.publish() no longer hardcodes any behavior — it must
    delegate every event to the shared event_bus so any registered
    subscriber reacts. Uses a throwaway EventBus (monkeypatched in place of
    the real module-level singleton) so this doesn't touch/leak into
    whatever handlers other test files may have registered globally."""

    def test_publish_dispatches_to_bus_with_org_id_resolved_from_payload(self, monkeypatch):
        test_bus = EventBus()
        monkeypatch.setattr("app.events.publisher.event_bus", test_bus)
        calls = []
        test_bus.subscribe(ALL_EVENTS, lambda et, payload, org: calls.append((et, payload, org)))

        EventPublisher().publish(EventType.CLAIM_IMPORTED, {"claim_id": 5, "organization_id": 9})

        assert calls[0][0] == "claim.imported"
        assert calls[0][1]["claim_id"] == 5
        assert calls[0][1]["organization_id"] == 9
        assert calls[0][1]["event_id"]
        assert calls[0][1]["correlation_id"] == calls[0][1]["event_id"]
        assert calls[0][2] == 9

    def test_publish_prefers_explicit_organization_id_over_payload(self, monkeypatch):
        test_bus = EventBus()
        monkeypatch.setattr("app.events.publisher.event_bus", test_bus)
        calls = []
        test_bus.subscribe(ALL_EVENTS, lambda et, payload, org: calls.append(org))

        EventPublisher().publish(
            EventType.CLAIM_IMPORTED, {"organization_id": 9}, organization_id=42
        )

        assert calls == [42]
