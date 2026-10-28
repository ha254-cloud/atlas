"""
WebhookHandler — subscribes to every event ("*") and, for each active
WebhookSubscription in the event's organization whose `event_types` list is
empty (wildcard) or contains this event type, queues a `deliver_webhook`
Celery task. Delivery itself (the actual HTTP POST) always happens in the
background worker, never inline in the request/import path, so a slow or
unreachable customer endpoint can never add latency to claim processing.
"""

import logging

logger = logging.getLogger(__name__)


class WebhookHandler:
    def __call__(self, event_type: str, payload: dict, organization_id: int | None) -> None:
        if organization_id is None:
            return

        from app.db.database import get_db
        from app.models.webhook import WebhookSubscription

        db = next(get_db())
        try:
            subscriptions = (
                db.query(WebhookSubscription)
                .filter(
                    WebhookSubscription.organization_id == organization_id,
                    WebhookSubscription.is_active.is_(True),
                )
                .all()
            )
            matching = [
                sub for sub in subscriptions if not sub.event_types or event_type in sub.event_types
            ]
            if not matching:
                return

            try:
                from app.workers.tasks import deliver_webhook
            except Exception:
                logger.debug("WebhookHandler could not import deliver_webhook task")
                return

            for sub in matching:
                try:
                    deliver_webhook.delay(sub.id, event_type, payload)
                except Exception:
                    # Worker not running in dev/test — non-fatal.
                    logger.debug(
                        "WebhookHandler could not queue delivery for subscription %s", sub.id
                    )
        except Exception:
            logger.exception("WebhookHandler failed while processing %s", event_type)
        finally:
            db.close()
