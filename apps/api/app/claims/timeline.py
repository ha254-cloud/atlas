from datetime import datetime

from sqlalchemy.orm import Session

from app.models.claim_event import ClaimEvent, ClaimEventType


class ClaimTimeline:
    """
    Write and read the immutable event history for a claim.
    Events are append-only — never update or delete.
    """

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        organization_id: int,
        claim_id: int,
        event_type: ClaimEventType,
        description: str,
        actor_id: int | None = None,
        metadata: dict | None = None,
    ) -> ClaimEvent:
        event = ClaimEvent(
            organization_id=organization_id,
            claim_id=claim_id,
            event_type=event_type,
            description=description,
            actor_id=actor_id,
            event_metadata=metadata,
            occurred_at=datetime.utcnow(),
        )
        self.db.add(event)
        self.db.flush()
        return event

    def get_timeline(self, claim_id: int, organization_id: int) -> list[ClaimEvent]:
        return (
            self.db.query(ClaimEvent)
            .filter(
                ClaimEvent.claim_id == claim_id,
                ClaimEvent.organization_id == organization_id,
            )
            .order_by(ClaimEvent.occurred_at.asc())
            .all()
        )
