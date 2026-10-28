from uuid import uuid4

from app.events.bus import event_bus
from app.events.event_types import EventType


class EventPublisher:
    def publish(
        self,
        event_type: EventType | str,
        payload: dict,
        organization_id: int | None = None,
    ):
        envelope = dict(payload)
        event_id = str(envelope.get("event_id") or uuid4())
        envelope["event_id"] = event_id
        envelope.setdefault("correlation_id", event_id)

        # For now, simple stdout publisher — replace with broker later
        print(f"[EVENT] {event_type}", envelope)

        # Not every payload carries organization_id yet — those events
        # simply reach handlers with organization_id=None.
        org_id = organization_id or envelope.get("organization_id")

        # Every actual consumer (dashboard SSE push, notifications,
        # analytics, webhooks, ...) reacts via the event bus now — this
        # publisher no longer hardcodes what happens on an event. See
        # app/events/handlers/ for the registered subscribers.
        event_bus.dispatch(event_type, envelope, org_id)
