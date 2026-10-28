"""
WebhookSubscription — an organization-registered HTTP endpoint that Atlas
POSTs event payloads to (the "customer wants updates" use case from the
Sprint 8 spec — e.g. a hospital system subscribing to `claim.analyzed`).

`event_types` is a JSON list of EventType string values the subscription
cares about; an empty/null list means "every event" (a wildcard
subscription), matching the same `ALL_EVENTS` convention used by the
in-process EventBus.

`secret` is used to HMAC-sign the delivered payload (see
app/webhooks/delivery.py) so the receiving endpoint can verify the request
actually came from Atlas.
"""

from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin
from app.db.database import Base


class WebhookSubscription(Base, TimestampMixin):
    __tablename__ = "webhook_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # None/empty list == subscribed to every event type.
    event_types: Mapped[list | None] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WebhookDeliveryLog(Base, TimestampMixin):
    """One row per delivery attempt — for troubleshooting/observability.
    No retry/DLQ mechanism yet (deliberately out of scope for this round,
    see local dev notes); a failed delivery is logged here and not retried."""

    __tablename__ = "webhook_delivery_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("webhook_subscriptions.id"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status_code: Mapped[int | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
