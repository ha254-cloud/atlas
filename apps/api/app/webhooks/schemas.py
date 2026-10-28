import secrets

from pydantic import BaseModel, Field


class WebhookSubscriptionCreate(BaseModel):
    target_url: str = Field(..., max_length=500)
    description: str | None = Field(None, max_length=255)
    # Empty/omitted == subscribe to every event type.
    event_types: list[str] | None = None


class WebhookSubscriptionUpdate(BaseModel):
    target_url: str | None = Field(None, max_length=500)
    description: str | None = Field(None, max_length=255)
    event_types: list[str] | None = None
    is_active: bool | None = None


class WebhookSubscriptionRead(BaseModel):
    id: int
    target_url: str
    description: str | None
    event_types: list[str] | None
    is_active: bool

    class Config:
        from_attributes = True


class WebhookSubscriptionCreated(WebhookSubscriptionRead):
    # The signing secret is only ever returned once, at creation time —
    # same convention as API keys elsewhere in this codebase.
    secret: str


class WebhookDeliveryLogRead(BaseModel):
    id: int
    event_type: str
    success: bool
    status_code: int | None
    error: str | None

    class Config:
        from_attributes = True


def generate_secret() -> str:
    return secrets.token_hex(32)
