from datetime import date, datetime

from pydantic import BaseModel, Field

from app.finance.models import FinanceDataDimension, ForecastMethod


class FinanceDataGap(BaseModel):
    dimension: FinanceDataDimension
    reason: str


class ExecutiveFinanceSnapshot(BaseModel):
    as_of: datetime
    currency: str
    todays_collections: float
    potential_revenue: float
    collected_revenue: float
    outstanding_claims: float
    recoverable_revenue: float
    atlas_attributed_recoveries: float
    unclassified_leakage: float
    collection_rate_pct: float
    denial_rate_pct: float
    average_payment_days: float
    hospital_revenue_health_pct: float
    data_gaps: list[FinanceDataGap]


class PayerFinanceScorecard(BaseModel):
    payer_id: int
    payer: str
    claim_count: int
    outstanding_amount: float
    recovered_amount: float
    average_payment_days: float
    denial_rate_pct: float


class DenialLeakageItem(BaseModel):
    denial_type: str
    claim_count: int
    outstanding_amount: float


class CashForecast(BaseModel):
    generated_at: datetime
    through_date: date
    currency: str
    expected_collections: float
    confidence_pct: float
    case_count: int
    method: ForecastMethod
    assumptions: list[str]


class ReconciliationSummary(BaseModel):
    unmatched_payment_count: int
    unmatched_payment_amount: float
    matched_payment_count: int
    matched_payment_amount: float
    overpaid_claim_count: int
    currencies: list[str]


class FinanceOverview(BaseModel):
    executive: ExecutiveFinanceSnapshot
    payers: list[PayerFinanceScorecard]
    denial_leakage: list[DenialLeakageItem]
    forecast: CashForecast
    reconciliation: ReconciliationSummary


class ForecastQuery(BaseModel):
    days: int = Field(default=30, ge=1, le=90)
