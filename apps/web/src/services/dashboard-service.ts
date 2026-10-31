import { api } from "@/lib/api-client";
import type { DashboardSummary } from "@/types";

export interface DashboardResponse {
  metrics: DashboardSummary;
  recent_claims: Array<{
    id: number; claim_number: string; status: string;
    billed_amount: number; paid_amount: number; service_date: string | null;
  }>;
  recent_imports: Array<{
    id: number; source: string; status: string;
    total_records: number; successful_records: number;
  }>;
  recovery_trend: Array<{ month: string; claims: number; estimated_value: number }>;
}

export interface ExecutiveSummary {
  outstanding_recoverable_revenue: number;
  outstanding_recoverable_revenue_trend_pct: number;
  claims_awaiting_review: number;
  appeals_ready: number;
  recovery_probability_pct: number;
  avg_recovery_time_days: number;
}

export interface FinancialKpis {
  gross_charges: number;
  denied_revenue: number;
  recoverable_revenue: number;
  recovered_revenue: number;
  net_recovered_revenue: number;
  appeal_success_rate_pct: number;
  avg_reimbursement_time_days: number;
  cost_per_recovered_dollar: number;
}

export interface PayerPerformance {
  payer_id: number;
  payer: string;
  denied_claims: number;
  recovery_rate_pct: number;
  avg_days_to_recovery: number;
  most_common_denial_code: string | null;
  avg_revenue_lost: number;
}

export interface SubmissionSummary {
  pending: number;
  submitted: number;
  waiting: number;
  denied: number;
  paid: number;
  average_processing_time: number | null;
  recovery_pipeline: Record<string, number>;
}

export interface FinanceOverview {
  executive: {
    as_of: string;
    currency: string;
    todays_collections: number;
    potential_revenue: number;
    collected_revenue: number;
    outstanding_claims: number;
    recoverable_revenue: number;
    atlas_attributed_recoveries: number;
    unclassified_leakage: number;
    collection_rate_pct: number;
    denial_rate_pct: number;
    average_payment_days: number;
    hospital_revenue_health_pct: number;
    data_gaps: Array<{ dimension: string; reason: string }>;
  };
  payers: Array<{
    payer_id: number;
    payer: string;
    claim_count: number;
    outstanding_amount: number;
    recovered_amount: number;
    average_payment_days: number;
    denial_rate_pct: number;
  }>;
  denial_leakage: Array<{
    denial_type: string;
    claim_count: number;
    outstanding_amount: number;
  }>;
  forecast: {
    generated_at: string;
    through_date: string;
    currency: string;
    expected_collections: number;
    confidence_pct: number;
    case_count: number;
    method: string;
    assumptions: string[];
  };
  reconciliation: {
    unmatched_payment_count: number;
    unmatched_payment_amount: number;
    matched_payment_count: number;
    matched_payment_amount: number;
    overpaid_claim_count: number;
    currencies: string[];
  };
}

export interface ForecastPoint { month: string; expected_recovery: number }
export interface AnalyticsInsight { category: string; message: string }

export const dashboardService = {
  getDashboard: () => api.get<DashboardResponse>("/api/v1/dashboard"),
  getDenialBreakdown: () => api.get<Array<{ type: string; count: number }>>("/api/v1/dashboard/analytics/denials"),
  getRecoveryByPayer: () => api.get("/api/v1/dashboard/analytics/recovery-by-payer"),
  getRecoveryRate: () => api.get("/api/v1/dashboard/analytics/recovery-rate"),
  getExecutiveSummary: () => api.get<ExecutiveSummary>("/api/v1/dashboard/analytics/executive-summary"),
  getFinancialKpis: () => api.get<FinancialKpis>("/api/v1/dashboard/analytics/financial-kpis"),
  getPayerPerformance: () => api.get<PayerPerformance[]>("/api/v1/dashboard/analytics/payer-performance"),
  getForecast: () => api.get<ForecastPoint[]>("/api/v1/dashboard/analytics/forecast", { months: 6 }),
  getInsights: () => api.get<AnalyticsInsight[]>("/api/v1/dashboard/analytics/insights"),
  getSubmissionSummary: () => api.get<SubmissionSummary>("/api/v1/payer-connectivity/analytics/executive-summary"),
  getFinanceOverview: () => api.get<FinanceOverview>("/api/v1/finance/overview"),
};
