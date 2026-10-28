from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_organization
from app.db.database import get_db
from app.models.user import User
from app.security.dependencies import require_permission
from app.security.permissions import Permission
from app.webhooks.schemas import (
    WebhookDeliveryLogRead,
    WebhookSubscriptionCreate,
    WebhookSubscriptionCreated,
    WebhookSubscriptionRead,
    WebhookSubscriptionUpdate,
)
from app.webhooks.service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.get("", response_model=list[WebhookSubscriptionRead])
def list_webhooks(
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    return WebhookService(db, organization_id).list_subscriptions()


@router.post("", response_model=WebhookSubscriptionCreated, status_code=201)
def create_webhook(
    payload: WebhookSubscriptionCreate,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    subscription = WebhookService(db, organization_id).create(
        payload.target_url,
        payload.description,
        payload.event_types,
    )
    return subscription


@router.patch("/{subscription_id}", response_model=WebhookSubscriptionRead)
def update_webhook(
    subscription_id: int,
    payload: WebhookSubscriptionUpdate,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    subscription = WebhookService(db, organization_id).update(
        subscription_id,
        **payload.model_dump(exclude_unset=True),
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="Webhook subscription not found")
    return subscription


@router.delete("/{subscription_id}", status_code=204)
def delete_webhook(
    subscription_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    deleted = WebhookService(db, organization_id).delete(subscription_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook subscription not found")


@router.get("/{subscription_id}/deliveries", response_model=list[WebhookDeliveryLogRead])
def list_deliveries(
    subscription_id: int,
    db: Session = Depends(get_db),
    organization_id: int = Depends(get_current_organization),
    current_user: User = Depends(require_permission(Permission.CONFIGURE_INTEGRATIONS)),
):
    service = WebhookService(db, organization_id)
    if service.get(subscription_id) is None:
        raise HTTPException(status_code=404, detail="Webhook subscription not found")
    return service.deliveries(subscription_id)
