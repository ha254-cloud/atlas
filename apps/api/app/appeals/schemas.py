from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.appeal import AppealStatus


class AppealCreate(BaseModel):
    claim_id: int
    recovery_case_id: int | None = None
    require_evidence: bool = False
    analysis_id: int | None = None
    title: str | None = None
    body: str | None = None
    confidence: float | None = Field(None, ge=0, le=1)
    required_documents: list[str] = Field(default_factory=list)
    missing_documents: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class AppealUpdate(BaseModel):
    appeal_text: str | None = None
    sections: dict[str, str] | None = None
    body: str | None = None
    title: str | None = None
    confidence: float | None = Field(None, ge=0, le=1)
    required_documents: list[str] | None = None
    missing_documents: list[str] | None = None
    references: list[str] | None = None
    status: AppealStatus | None = None


class AppealResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    letter: str
    confidence: float = Field(ge=0, le=1)
    required_documents: list[str]
    missing_documents: list[str]
    references: list[str]


class AppealSubmitRequest(BaseModel):
    confirmation_number: str = Field(..., min_length=1, max_length=255)


class AppealRead(BaseModel):
    id: int
    organization_id: int
    claim_id: int
    recovery_case_id: int | None = None
    analysis_id: int | None = None
    status: str
    appeal_text: str
    body: str
    title: str | None = None
    summary: str | None = None
    sections: dict | None = None
    citations: list | None = None
    attachments: list[str] | None = None
    missing_information: list[str] | None = None
    missing_documents: list[str] | None = None
    required_documents: list[str] | None = None
    references: list[str] | None = None
    confidence: float | None = None
    quality_score: dict | None = None
    ai_provider: str | None = None
    generated_by: str | None = None
    submitted_by: int | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    pdf_document_id: int | None = None
    confirmation_number: str | None = None
    response_due_date: datetime | None = None
    current_version: int = 1
    version: int = 1
    submitted_at: datetime | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


AppealResponse = AppealRead


class AppealListItem(AppealRead):
    claim_number: str
    payer_name: str
    patient_name: str
    billed_amount: float
    service_date: date | None = None
