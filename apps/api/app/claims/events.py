from app.events.event_types import EventType
from app.events.publisher import EventPublisher


class ClaimEvents:
    def __init__(self):
        self.pub = EventPublisher()

    def created(self, claim):
        self.pub.publish(
            EventType.CLAIM_CREATED,
            {
                "claim_id": claim.id,
                "claim_number": claim.claim_number,
                "organization_id": claim.organization_id,
            },
        )
