from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class MoneyTotal(BaseModel):
    currency: str
    amount: Decimal


class CustomerMetrics(BaseModel):
    total: int
    active: int
    trial: int
    suspended: int


class PlatformMetrics(BaseModel):
    claims_processed: int
    claims_today: int
    verified_recovery: list[MoneyTotal]
    atlas_fees_earned: list[MoneyTotal]


class AtlasRevenueMetrics(BaseModel):
    paid_invoices: list[MoneyTotal]
    outstanding_invoices: list[MoneyTotal]
    overdue_invoices: list[MoneyTotal]


class AIOperationsMetrics(BaseModel):
    requests_today: int
    tokens_today: int
    estimated_cost_usd_today: Decimal
    average_latency_ms_today: float | None


class PlatformAlert(BaseModel):
    severity: str
    message: str
    organization_id: int | None = None


class PlatformAdminSummary(BaseModel):
    customers: CustomerMetrics
    platform: PlatformMetrics
    atlas_revenue: AtlasRevenueMetrics
    ai_operations: AIOperationsMetrics
    integration_errors: int
    system_health: dict[str, str]
    alerts: list[PlatformAlert]
    unavailable_metrics: list[str]


class HospitalSummary(BaseModel):
    id: int
    name: str
    status: str
    subscription_plan: str
    currency: str
    claim_count: int
    verified_recovery: list[MoneyTotal]
    atlas_revenue: list[MoneyTotal]
    created_at: datetime
