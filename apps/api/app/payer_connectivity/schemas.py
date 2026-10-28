from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.appeal_submission import AppealSubmissionStatus


class ElectronicSubmissionRequest(BaseModel):
    connector: str = Field(..., examples=["sandbox", "availity", "waystar"])
    integration_id: int | None = None
    connector_options: dict | None = None


class SubmissionEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: AppealSubmissionStatus
    message: str | None
    payload: dict | None
    occurred_at: datetime


class AppealSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    appeal_id: int
    integration_id: int | None
    connector: str
    external_tracking_id: str | None
    status: AppealSubmissionStatus
    submitted_at: datetime | None
    last_checked_at: datetime | None
    next_follow_up_at: datetime | None
    response_payload: dict | None
    retry_count: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class AppealSubmissionDetail(AppealSubmissionRead):
    events: list[SubmissionEventRead]
