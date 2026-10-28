from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ClaimStatusLiteral = Literal["imported", "pending", "paid", "denied", "appealed", "closed"]
ClaimPriorityLiteral = Literal["low", "medium", "high", "critical"]


class ClaimLineInput(BaseModel):
    cpt_code: str
    modifier: str | None = None
    description: str | None = None
    units: int = 1
    charge_amount: float
    allowed_amount: float | None = None
    paid_amount: float | None = None
    status: str | None = None


class ClaimLineRead(BaseModel):
    id: int
    cpt_code: str
    modifier: str | None = None
    description: str | None = None
    units: int
    charge_amount: float
    allowed_amount: float | None = None
    paid_amount: float | None = None
    status: str | None = None

    class Config:
        orm_mode = True


class ClaimDiagnosisInput(BaseModel):
    icd_code: str
    description: str | None = None
    is_primary: bool = False


class ClaimDiagnosisRead(BaseModel):
    id: int
    icd_code: str
    description: str | None = None
    is_primary: bool

    class Config:
        orm_mode = True


class ClaimCreate(BaseModel):
    branch_id: int | None = Field(default=None, gt=0)
    department_id: int | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    patient_id: int
    payer_id: int
    claim_number: str | None = None
    status: ClaimStatusLiteral | None = "imported"
    billed_amount: float
    paid_amount: float | None = 0.0
    service_date: date | None = None
    provider: str | None = None
    priority: ClaimPriorityLiteral | None = "medium"
    assigned_user_id: int | None = None
    ai_risk_score: float | None = None
    recovery_probability: float | None = None
    claim_lines: list[ClaimLineInput] | None = None
    claim_diagnoses: list[ClaimDiagnosisInput] | None = None


class ClaimUpdate(BaseModel):
    reason: str | None = None
    branch_id: int | None = Field(default=None, gt=0)
    department_id: int | None = Field(default=None, gt=0)
    claim_number: str | None = None
    status: ClaimStatusLiteral | None = None
    billed_amount: float | None = None
    paid_amount: float | None = None
    service_date: date | None = None
    provider: str | None = None
    priority: ClaimPriorityLiteral | None = None
    assigned_user_id: int | None = None
    ai_risk_score: float | None = None
    recovery_probability: float | None = None


class DenialRead(BaseModel):
    id: int
    denial_code: str
    denial_type: str
    description: str | None = None

    class Config:
        orm_mode = True


class ClaimAnalysisRead(BaseModel):
    analysis_status: str
    risk_score: float | None = None
    priority: str | None = None
    denial_category: str | None = None
    root_cause: str | None = None
    recovery_probability: float | None = None
    estimated_recovery_amount: float | None = None
    recommended_action: str | None = None
    confidence_score: float | None = None
    ai_summary: str | None = None
    model_version: str | None = None
    required_documents: list[str] = []
    model: str | None = None
    prompt_version: str | None = None

    class Config:
        orm_mode = True


class RecoveryCaseRead(BaseModel):
    id: int
    claim_id: int
    recovery_score: float
    estimated_value: float
    status: str
    recommendation: str | None = None

    class Config:
        orm_mode = True


class ClaimValidationIssueRead(BaseModel):
    id: int
    code: str
    severity: str
    field: str
    message: str
    resolved: bool

    class Config:
        orm_mode = True


class ClaimRead(BaseModel):
    id: int
    organization_id: int
    branch_id: int | None = None
    department_id: int | None = None
    currency: str
    patient_id: int
    payer_id: int
    patient_name: str | None = None
    payer_name: str | None = None
    claim_number: str | None = None
    status: str | None = None
    billed_amount: float
    paid_amount: float | None = None
    service_date: date | None = None
    provider: str | None = None
    priority: str | None = None
    assigned_user_id: int | None = None
    assigned_user_name: str | None = None
    ai_risk_score: float | None = None
    recovery_probability: float | None = None
    diagnosis_codes: list[str] = []
    procedure_codes: list[str] = []
    denial_code: str | None = None
    appeal_status: str | None = None
    recovery_status: str | None = None
    ai_score: float | None = None
    analysis_status: str = "pending"

    class Config:
        orm_mode = True


class ClaimDetailRead(ClaimRead):
    denials: list[DenialRead] = []
    recovery_cases: list[RecoveryCaseRead] = []
    claim_lines: list[ClaimLineRead] = []
    claim_diagnoses: list[ClaimDiagnosisRead] = []
    analysis: ClaimAnalysisRead | None = None
    validation_issues: list[ClaimValidationIssueRead] = []


class ClaimAnalysisResponse(BaseModel):
    status: str
    risk_score: float | None = None
    priority: str | None = None
    confidence: float | None = None
    recovery_probability: float | None = None
    recommended_action: str | None = None
    summary: str | None = None
    required_documents: list[str] = []


class PatientLookup(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


class PayerLookup(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True
