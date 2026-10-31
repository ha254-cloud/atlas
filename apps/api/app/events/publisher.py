from uuid import uuid4

from sqlalchemy.orm import Session

from app.events.bus import event_bus
from app.events.event_types import EventType
from app.events.models import DomainEventOutbox


class EventPublisher:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def publish(
        self,
        event_type: EventType | str,
        payload: dict,
        organization_id: int | None = None,
    ) -> str:
        envelope = dict(payload)
        event_id = str(envelope.get("event_id") or uuid4())
        envelope["event_id"] = event_id
        envelope.setdefault("correlation_id", event_id)
        org_id = organization_id or envelope.get("organization_id")
        event_name = event_type.value if hasattr(event_type, "value") else str(event_type)

        if self.db is None:
            event_bus.dispatch(event_name, envelope, org_id)
            return event_id
        if org_id is None:
            raise ValueError("Durable domain events require organization_id")

        envelope.setdefault("organization_id", org_id)
        self.db.add(
            DomainEventOutbox(
                event_id=event_id,
                organization_id=org_id,
                event_type=event_name,
                payload=envelope,
                correlation_id=str(envelope["correlation_id"]),
                actor_id=envelope.get("actor_id"),
            )
        )
        self.db.flush()
        return event_id
