from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    user_id: int
    action: str
    entity: str
    entity_id: int | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    device: str | None = None
    correlation_id: str | None = None
    reason: str | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    metadata_json: dict | None = None
    created_at: datetime
