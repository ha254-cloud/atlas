import { api } from "@/lib/api-client";
import type { Payer, PayerHealthCheckResult, PaymentMethod, StatusMethod, SubmissionMethod } from "@/types/payer";

export interface PayerCreateInput {
  name: string;
  payer_code: string;
  country?: string;
  submission_method?: SubmissionMethod;
  status_method?: StatusMethod;
  payment_method?: PaymentMethod;
  portal_url?: string | null;
  api_url?: string | null;
  submission_email?: string | null;
  supports_api?: boolean;
  supports_sftp?: boolean;
  supports_email?: boolean;
  supports_manual?: boolean;
  connector_name?: string | null;
  integration_id?: number | null;
  is_active?: boolean;
  reason: string;
}

export type PayerUpdateInput = Partial<Omit<PayerCreateInput, "reason">> & { reason: string };

export const payersService = {
  list: (activeOnly = true) => api.get<Payer[]>("/api/v1/payers", { active_only: activeOnly }),
  get: (id: number) => api.get<Payer>(`/api/v1/payers/${id}`),
  create: (input: PayerCreateInput) => api.post<Payer>("/api/v1/payers", input),
  update: (id: number, input: PayerUpdateInput) => api.patch<Payer>(`/api/v1/payers/${id}`, input),
  submitForApproval: (id: number) => api.post<Payer>(`/api/v1/payers/${id}/submit-for-approval`),
  approve: (id: number) => api.post<Payer>(`/api/v1/payers/${id}/approve`),
  reject: (id: number, reason: string) => api.post<Payer>(`/api/v1/payers/${id}/reject`, { reason }),
  checkHealth: (id: number) => api.get<PayerHealthCheckResult>(`/api/v1/payers/${id}/health-check`),
};
