"""
EventBus — the actual pub/sub registry Sprint 8 asks for.

`EventPublisher` (app/events/publisher.py) already existed and is kept as
the single call-site API every module uses (`EventPublisher().publish(...)`)
so none of its 10+ existing callers need to change. What was genuinely
missing was a *subscription* mechanism: `EventPublisher.publish()` used to
hardcode exactly two things that happen on every event (stdout log + SSE
forward) with no way for a new consumer (analytics, webhooks, a future
fraud-detection module, ...) to react without editing `publisher.py` itself.

`EventBus` fixes that: any number of handlers can `subscribe()` to a
specific event type (or `"*"` for every event), and `EventPublisher.publish()`
calls `dispatch()` so every subscriber reacts — without the publisher (or
the code that called it) ever knowing who's listening.

Handlers are plain callables: `handler(event_type, payload, organization_id)`.
A class-based handler implements `__call__` with that signature (matches the
spec's `EventBus.subscribe("claim.analyzed", DashboardHandler())` shape).

Dispatch is synchronous and in-process (no broker) — appropriate here since
handlers either do cheap local work or hand off to Celery themselves (see
`app/events/handlers/claims.py`/`webhooks.py`). One handler raising an
exception must never break the publisher or any other handler, so every
call is individually wrapped and logged, never re-raised.
"""

import logging
from collections.abc import Callable

from app.events.event_types import EventType

logger = logging.getLogger(__name__)

Handler = Callable[[str, dict, int | None], None]

# Wildcard subscription key — handlers registered under this key run for
# every event type, regardless of the specific event.
ALL_EVENTS = "*"


def _event_key(event_type: EventType | str) -> str:
    return event_type.value if hasattr(event_type, "value") else str(event_type)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = {}

    def subscribe(self, event_type: EventType | str, handler: Handler) -> None:
        key = _event_key(event_type)
        self._subscribers.setdefault(key, []).append(handler)

    def unsubscribe(self, event_type: EventType | str, handler: Handler) -> None:
        key = _event_key(event_type)
        handlers = self._subscribers.get(key)
        if handlers and handler in handlers:
            handlers.remove(handler)

    def clear(self) -> None:
        """Test-only helper: drop every registered subscriber."""
        self._subscribers.clear()

    def dispatch(
        self, event_type: EventType | str, payload: dict, organization_id: int | None = None
    ) -> None:
        key = _event_key(event_type)
        handlers = list(self._subscribers.get(key, [])) + list(
            self._subscribers.get(ALL_EVENTS, [])
        )
        for handler in handlers:
            try:
                handler(key, payload, organization_id)
            except Exception:
                logger.exception("Event handler %r failed while handling %s", handler, key)


# Single process-wide bus. Handlers register onto this instance via
# app.events.handlers.register_all() (called once at process startup, from
# both app.main and the Celery worker entrypoint — events can be published
# from either process).
event_bus = EventBus()
