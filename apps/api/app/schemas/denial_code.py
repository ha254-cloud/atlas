from datetime import datetime

from pydantic import BaseModel


class DenialCodeRead(BaseModel):
    code: str
    category: str
    description: str
    recovery_strategy: str
    ai_guidance: str | None = None
    is_active: bool
    severity: str | None = None
    recoverability: str | None = None
    typical_recovery_rate: float | None = None
    required_documents: list[str] | None = None
    typical_resolution_days: int | None = None
    common_payers: list[str] | None = None
    references: list[str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }
