import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.events.bus import EventBus, event_bus
from app.events.models import DomainEventOutbox, DomainEventOutboxStatus

logger = logging.getLogger(__name__)


class OutboxDispatcher:
    def __init__(
        self,
        db: Session,
        *,
        bus: EventBus = event_bus,
        max_attempts: int = settings.EVENT_OUTBOX_MAX_ATTEMPTS,
        base_retry_seconds: int = settings.EVENT_OUTBOX_BASE_RETRY_SECONDS,
        max_retry_seconds: int = settings.EVENT_OUTBOX_MAX_RETRY_SECONDS,
        lease_seconds: int = settings.EVENT_OUTBOX_LEASE_SECONDS,
    ) -> None:
        self.db = db
        self.bus = bus
        self.max_attempts = max_attempts
        self.base_retry_seconds = base_retry_seconds
        self.max_retry_seconds = max_retry_seconds
        self.lease_seconds = lease_seconds

    def dispatch_batch(self, limit: int = settings.EVENT_OUTBOX_BATCH_SIZE) -> int:
        now = datetime.now(UTC)
        event_ids = [
            row[0]
            for row in self.db.query(DomainEventOutbox.id)
            .filter(
                DomainEventOutbox.available_at <= now,
                or_(
                    DomainEventOutbox.status == DomainEventOutboxStatus.PENDING.value,
                    DomainEventOutbox.status == DomainEventOutboxStatus.PROCESSING.value,
                ),
            )
            .order_by(DomainEventOutbox.created_at, DomainEventOutbox.id)
            .limit(limit)
            .all()
        ]
        published = 0
        for outbox_id in event_ids:
            if self.dispatch_one(outbox_id):
                published += 1
        return published

    def dispatch_one(self, outbox_id: int) -> bool:
        now = datetime.now(UTC)
        query = self.db.query(DomainEventOutbox).filter(
            DomainEventOutbox.id == outbox_id,
            DomainEventOutbox.available_at <= now,
            or_(
                DomainEventOutbox.status == DomainEventOutboxStatus.PENDING.value,
                DomainEventOutbox.status == DomainEventOutboxStatus.PROCESSING.value,
            ),
        )
        if self.db.bind is not None and self.db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        event = query.first()
        if event is None:
            return False

        event.status = DomainEventOutboxStatus.PROCESSING.value
        event.attempts += 1
        event.available_at = now + timedelta(seconds=self.lease_seconds)
        self.db.commit()

        try:
            errors = self.bus.dispatch(
                event.event_type,
                dict(event.payload),
                event.organization_id,
            )
            if errors:
                raise RuntimeError(
                    f"{len(errors)} event handler(s) failed: "
                    + "; ".join(str(error) for error in errors[:3])
                )
        except Exception as exc:
            self.db.rollback()
            event = self.db.get(DomainEventOutbox, outbox_id)
            if event is None:
                return False
            event.last_error = str(exc)[:4000]
            if event.attempts >= self.max_attempts:
                event.status = DomainEventOutboxStatus.DEAD_LETTER.value
            else:
                delay = min(
                    self.max_retry_seconds,
                    self.base_retry_seconds * (2 ** (event.attempts - 1)),
                )
                event.status = DomainEventOutboxStatus.PENDING.value
                event.available_at = datetime.now(UTC) + timedelta(seconds=delay)
            self.db.commit()
            logger.exception("Domain event %s dispatch failed", event.event_id)
            return False

        event = self.db.get(DomainEventOutbox, outbox_id)
        if event is None:
            return False
        event.status = DomainEventOutboxStatus.PUBLISHED.value
        event.published_at = datetime.now(UTC)
        event.last_error = None
        self.db.commit()
        return True
