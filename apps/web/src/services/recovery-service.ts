import { api } from "@/lib/api-client";

export interface RecoveryOpportunity {
  id: number; claim_id: number; claim_number: string;
  payer_id: number; patient_id: number; recovery_score: number;
  estimated_value: number; status: string; priority: string;
  recommendation: string; billed_amount: number; paid_amount: number; balance: number;
}

export interface RecoveryListResponse {
  items: RecoveryOpportunity[]; total: number; limit: number; offset: number;
}

export interface RecoveryPortfolio {
  currency: string;
  original_amount: string;
  recovered_amount: string;
  outstanding_amount: string;
  recoverable_amount: string;
  expected_recovery_amount: string;
  high_probability_amount: string;
  medium_probability_amount: string;
  low_probability_amount: string;
  recoverable_revenue_index_pct: string;
  atlas_recoveries: string;
  atlas_fees: string;
  return_on_investment_pct: string | null;
  account_count: number;
  as_of: string;
}

export interface RecoveryForecast {
  currency: string;
  outstanding_amount: string;
  expected_recovery_amount: string;
  expected_collection_days: number;
  confidence_pct: string;
  buckets: Array<{
    start_date: string;
    end_date: string;
    expected_amount: string;
  }>;
  as_of: string;
}

export const recoveryService = {
  list: (params?: { status?: string; priority?: string; search?: string; limit?: number; offset?: number }) =>
    api.get<RecoveryListResponse>("/api/v1/recovery", params as Record<string, unknown>),
  updateStatus: (id: number, status: string) =>
    api.patch(`/api/v1/recovery/${id}/status`, { status }),
  getPortfolio: () =>
    api.get<RecoveryPortfolio>("/api/v1/recovery/lifecycle/portfolio"),
  getForecast: (horizonDays = 90) =>
    api.get<RecoveryForecast>("/api/v1/recovery/lifecycle/forecast", { horizon_days: horizonDays }),
};
