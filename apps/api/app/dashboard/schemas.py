from datetime import datetime

from pydantic import BaseModel


class ClaimSummary(BaseModel):
    id: int
    claim_number: str
    status: str
    billed_amount: float
    paid_amount: float
    service_date: str | None
    created_at: datetime | None

    class Config:
        from_attributes = True


class ImportSummary(BaseModel):
    id: int
    source: str
    status: str
    total_records: int
    successful_records: int
    failed_records: int
    created_at: datetime | None

    class Config:
        from_attributes = True


class RecoveryTrendPoint(BaseModel):
    month: str
    claims: int
    recovered: int
    estimated_value: float


class DashboardMetrics(BaseModel):
    claims: int
    denied_claims: int
    recovery_opportunities: int
    estimated_recovery: float
    high_priority: int
    recovery_rate: float
    ai_success_rate: float
    appeals_pending: int
    claims_requiring_attention: int
    analyzed_claims: int
    pending_analysis: int


class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    recent_claims: list[ClaimSummary]
    recent_imports: list[ImportSummary]
    recovery_trend: list[RecoveryTrendPoint]
