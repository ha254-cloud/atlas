from pydantic import BaseModel


class WorkspaceSummary(BaseModel):
    critical: int
    high: int
    medium: int
    low: int
    total: int
    estimated_recovery: float
    open_cases: int
    in_progress_cases: int


class WorkspaceDenial(BaseModel):
    denial_code: str | None = None
    denial_type: str | None = None
    description: str | None = None


class WorkspaceCase(BaseModel):
    id: int
    claim_id: int
    claim_number: str
    payer_name: str
    payer_code: str
    patient_name: str
    patient_mrn: str
    service_date: str | None = None
    billed_amount: float
    paid_amount: float
    balance: float
    estimated_recovery: float
    recovery_score: float
    confidence: int
    priority: str
    status: str
    recommendation: str
    denial: WorkspaceDenial | None = None
    ai_review: str | None = None
    recovered_amount: float | None = None
    invoice_generated: bool = False


class WorkspaceResponse(BaseModel):
    summary: WorkspaceSummary
    cases: list[WorkspaceCase]
    total: int
    limit: int
    offset: int
