import { api } from "@/lib/api-client";

export interface MoneyTotal {
  currency: string;
  amount: string;
}

export interface PlatformAlert {
  severity: string;
  message: string;
  organization_id: number | null;
}

export interface PlatformAdminSummary {
  customers: { total: number; active: number; trial: number; suspended: number };
  platform: {
    claims_processed: number;
    claims_today: number;
    verified_recovery: MoneyTotal[];
    atlas_fees_earned: MoneyTotal[];
  };
  atlas_revenue: {
    paid_invoices: MoneyTotal[];
    outstanding_invoices: MoneyTotal[];
    overdue_invoices: MoneyTotal[];
  };
  ai_operations: {
    requests_today: number;
    tokens_today: number;
    estimated_cost_usd_today: string;
    average_latency_ms_today: number | null;
  };
  integration_errors: number;
  system_health: Record<string, string>;
  alerts: PlatformAlert[];
  unavailable_metrics: string[];
}

export interface HospitalSummary {
  id: number;
  name: string;
  status: string;
  subscription_plan: string;
  currency: string;
  claim_count: number;
  verified_recovery: MoneyTotal[];
  atlas_revenue: MoneyTotal[];
  created_at: string;
}

export const platformAdminService = {
  getSummary: () => api.get<PlatformAdminSummary>("/api/v1/platform-admin/summary"),
  getHospitals: () => api.get<HospitalSummary[]>("/api/v1/platform-admin/hospitals"),
};