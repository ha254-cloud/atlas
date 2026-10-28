"""
DashboardHandler — reacts to every event and forwards it to the real-time
SSE notification stream (`GET /api/v1/notifications/stream`).

This is a straight port of the logic that used to live hardcoded inside
`EventPublisher.publish()` (see app/events/publisher.py) — same condition
(skip if no organization_id), same call, same payload. Moving it here is
the concrete "before/after" from the Sprint 8 spec: the publisher no longer
knows the dashboard exists, it just publishes; this handler decides to care.
"""

import logging

logger = logging.getLogger(__name__)


class DashboardHandler:
    def __call__(self, event_type: str, payload: dict, organization_id: int | None) -> None:
        if organization_id is None:
            return
        try:
            from app.api.v1.notifications import publish_notification

            publish_notification(organization_id, event_type, payload)
        except Exception:
            logger.exception("DashboardHandler failed to forward %s", event_type)
