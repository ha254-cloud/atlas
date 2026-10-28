from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.governance.models import RetentionEnforcementMode
from app.models.document import (
    DocumentClassificationReviewStatus,
    DocumentHoldType,
    DocumentType,
)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    document_type: DocumentType
    filename: str
    content_type: str
    file_size: int
    checksum: str
    tags: list[str]
    extracted_text: str | None = None
    extraction_status: str
    extraction_method: str
    extraction_engine: str
    extraction_engine_version: str
    extraction_confidence: float | None = None
    ai_summary: str | None = None
    predicted_document_type: DocumentType | None = None
    classification_confidence: float | None = None
    classification_provider: str | None = None
    classification_model: str | None = None
    classification_prompt_version: str | None = None
    classification_review_status: DocumentClassificationReviewStatus | None = None
    classification_reviewed_by_id: int | None = None
    classification_reviewed_at: datetime | None = None
    classification_review_reason: str | None = None
    uploaded_by_id: int | None = None
    created_at: datetime


class DocumentUpdate(BaseModel):
    document_type: DocumentType | None = None
    tags: list[str] | None = None


class DocumentClassificationReview(BaseModel):
    document_type: DocumentType
    reason: str = Field(min_length=1, max_length=500)


class DocumentHoldCreate(BaseModel):
    hold_type: DocumentHoldType
    active: bool
    reason: str = Field(min_length=1, max_length=500)


class DocumentHoldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    hold_type: DocumentHoldType
    version: int
    active: bool
    reason: str
    recorded_by_id: int
    correlation_id: str
    created_at: datetime


class DocumentRetentionDecision(BaseModel):
    document_id: int
    action: str
    reason: str
    policy_version: int
    expires_at: datetime


class DocumentRetentionRun(BaseModel):
    policy_version: int
    enforcement_mode: RetentionEnforcementMode
    as_of: datetime
    decisions: list[DocumentRetentionDecision]


class RetentionRunRequest(BaseModel):
    as_of: datetime | None = None


class RetentionEnforceRequest(RetentionRunRequest):
    expected_policy_version: int = Field(gt=0)
    confirm: bool
    reason: str = Field(min_length=1, max_length=500)
