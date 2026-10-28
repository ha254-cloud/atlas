import { api } from "@/lib/api-client";
import type { Claim, ClaimAnalysisResult, ClaimDetail, ClaimCreateInput, ClaimTimelineEvent, Lookup, ImportJob } from "@/types";

export interface ClaimListParams {
  limit?: number;
  offset?: number;
  search?: string;
  status?: string;
  payer_id?: number;
  priority?: string;
  assigned_user_id?: number;
  min_risk_score?: number;
}

export const claimsService = {
  list: (params?: ClaimListParams) =>
    api.get<Claim[]>(`/api/v1/claims/`, {
      limit: params?.limit ?? 100,
      offset: params?.offset ?? 0,
      ...(params?.search ? { search: params.search } : {}),
      ...(params?.status ? { status: params.status } : {}),
      ...(params?.payer_id ? { payer_id: params.payer_id } : {}),
      ...(params?.priority ? { priority: params.priority } : {}),
      ...(params?.assigned_user_id ? { assigned_user_id: params.assigned_user_id } : {}),
      ...(params?.min_risk_score !== undefined ? { min_risk_score: params.min_risk_score } : {}),
    }),
  get: (id: number) => api.get<ClaimDetail>(`/api/v1/claims/${id}`),
  analysis: (id: number) => api.get<ClaimAnalysisResult>(`/api/v1/claims/${id}/analysis`),
  create: (payload: ClaimCreateInput) => api.post<Claim>(`/api/v1/claims/`, payload),
  update: (id: number, payload: Partial<ClaimCreateInput>) =>
    api.patch<Claim>(`/api/v1/claims/${id}`, payload),
  updateStatus: (id: number, status: string) =>
    api.patch<Claim>(`/api/v1/claims/${id}`, { status }),
  delete: (id: number) => api.delete<{ deleted: boolean }>(`/api/v1/claims/${id}`),
  timeline: (id: number) => api.get<ClaimTimelineEvent[]>(`/api/v1/claims/${id}/timeline`),
  listPatients: () => api.get<Lookup[]>(`/api/v1/claims/lookups/patients`),
  listPayers: () => api.get<Lookup[]>(`/api/v1/claims/lookups/payers`),
  uploadCsv: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.upload<{ job_id: number; filename: string; status: string }>(
      `/api/v1/uploads/claims`,
      formData,
    );
  },
  getImportJob: (jobId: number) => api.get<ImportJob>(`/api/v1/imports/${jobId}`),
};
