from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.invoices.schemas import InvoiceLineRead, InvoicePeriodRequest, InvoiceRead
from app.models.submission import SubmissionStatus
from app.recoveries.schemas import RecoveryRead


class SubmissionRequest(BaseModel):
    connector: str | None = None
    integration_id: int | None = None
    connector_options: dict = Field(default_factory=dict)


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    claim_id: int | None
    appeal_id: int
    connector: str
    external_reference: str | None
    status: SubmissionStatus
    submitted_at: datetime | None
    acknowledged_at: datetime | None
    completed_at: datetime | None
    last_checked_at: datetime | None
    failure_reason: str | None
    retry_count: int
    created_at: datetime


__all__ = [
    "InvoiceLineRead",
    "InvoicePeriodRequest",
    "InvoiceRead",
    "RecoveryRead",
    "SubmissionRead",
    "SubmissionRequest",
]
