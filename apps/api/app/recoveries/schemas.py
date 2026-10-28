from datetime import date

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecoveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    submission_id: int | None
    payment_id: int
    paid_amount: float
    expected_amount: float
    recovered_amount: float
    recovery_percentage: float
    atlas_fee_percentage: float
    atlas_fee_amount: float
    payment_date: date
    verified: bool
    verified_by: int | None
    verified_at: datetime | None
    verification_reason: str | None


class RecoveryVerify(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
