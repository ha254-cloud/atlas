from sqlalchemy.orm import Session

from app.models.webhook import WebhookDeliveryLog, WebhookSubscription
from app.webhooks.schemas import generate_secret


class WebhookService:
    def __init__(self, db: Session, organization_id: int):
        self.db = db
        self.organization_id = organization_id

    def list_subscriptions(self) -> list[WebhookSubscription]:
        return (
            self.db.query(WebhookSubscription)
            .filter(WebhookSubscription.organization_id == self.organization_id)
            .order_by(WebhookSubscription.id.desc())
            .all()
        )

    def get(self, subscription_id: int) -> WebhookSubscription | None:
        return (
            self.db.query(WebhookSubscription)
            .filter(
                WebhookSubscription.id == subscription_id,
                WebhookSubscription.organization_id == self.organization_id,
            )
            .first()
        )

    def create(
        self, target_url: str, description: str | None, event_types: list[str] | None
    ) -> WebhookSubscription:
        subscription = WebhookSubscription(
            organization_id=self.organization_id,
            target_url=target_url,
            description=description,
            event_types=event_types or None,
            secret=generate_secret(),
        )
        self.db.add(subscription)
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def update(self, subscription_id: int, **fields) -> WebhookSubscription | None:
        subscription = self.get(subscription_id)
        if subscription is None:
            return None
        for key, value in fields.items():
            if value is not None:
                setattr(subscription, key, value)
        self.db.commit()
        self.db.refresh(subscription)
        return subscription

    def delete(self, subscription_id: int) -> bool:
        subscription = self.get(subscription_id)
        if subscription is None:
            return False
        self.db.delete(subscription)
        self.db.commit()
        return True

    def deliveries(self, subscription_id: int, limit: int = 50) -> list[WebhookDeliveryLog]:
        return (
            self.db.query(WebhookDeliveryLog)
            .filter(WebhookDeliveryLog.subscription_id == subscription_id)
            .order_by(WebhookDeliveryLog.id.desc())
            .limit(limit)
            .all()
        )
