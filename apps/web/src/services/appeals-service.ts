import { api } from "@/lib/api-client";

export interface Appeal {
  id: number; claim_id: number; status: string; appeal_text: string;
  summary: string | null; sections: Record<string, string> | null;
  citations: Array<{
    source: string;
    reference: string;
    relevance: string;
    policy_source_id?: number;
    policy_code?: string;
    version?: number;
    content_sha256?: string;
  }> | null;
  attachments: string[] | null;
  missing_information: string[] | null;
  missing_documents: string[] | null;
  quality_score: {
    completeness?: number;
    evidence?: number;
    tone?: number;
    compliance?: number;
    confidence?: number;
    grounding?: number;
    overall?: number;
    flagged_for_review?: boolean;
  } | null;
  grounding_report: {
    jurisdiction: "KE";
    payer_id: number;
    claim_service_date: string;
    denial_category: string | null;
    procedure_codes: string[];
    grounded: boolean;
    policy_section_mode: "verified_sources" | "verification_required";
    source_count: number;
    sources: Array<{
      id: number;
      policy_code: string;
      title: string;
      version: number;
      source_reference: string;
      content_sha256: string;
      effective_from: string;
      effective_to: string | null;
      approved_at: string | null;
    }>;
    accepted_citation_count: number;
    rejected_model_citation_count: number;
  } | null;
  analysis_id: number | null;
  confirmation_number: string | null;
  response_due_date: string | null;
  generated_by: string | null;
  submitted_by: number | null;
  current_version: number;
  created_at: string | null;
}

export interface AppealListItem extends Appeal {
  claim_number: string;
  payer_name: string;
  patient_name: string;
  billed_amount: number;
  service_date: string | null;
  submitted_at?: string | null;
}

export interface AppealSubmission {
  id: number;
  appeal_id: number;
  connector: string;
  external_reference: string | null;
  status: string;
}

export const appealsService = {
  list: () => api.get<AppealListItem[]>("/api/v1/appeals", { limit: 200 }),
  generate: (claim_id: number, recovery_case_id?: number) =>
    api.post<Appeal>("/api/v1/appeals", { claim_id, recovery_case_id }),
  generateSectioned: (claim_id: number, recovery_case_id?: number) =>
    api.post<Appeal>("/api/v1/appeals/sectioned", { claim_id, recovery_case_id }),
  listForClaim: (claim_id: number) =>
    api.get<Appeal[]>(`/api/v1/appeals/claim/${claim_id}`),
  get: (id: number) => api.get<Appeal>(`/api/v1/appeals/${id}`),
  update: (id: number, appeal_text: string, sections?: Record<string, string>) =>
    api.patch<Appeal>(`/api/v1/appeals/${id}`, { appeal_text, sections }),
  sendForReview: (id: number) => api.post<Appeal>(`/api/v1/appeals/${id}/review`, {}),
  approve: (id: number) => api.post<Appeal>(`/api/v1/appeals/${id}/approve`, {}),
  reject: (id: number) => api.post<Appeal>(`/api/v1/appeals/${id}/reject`, {}),
  recordManualSubmission: (id: number, confirmation_number: string) =>
    api.post<Appeal>(`/api/v1/appeals/${id}/submit`, { confirmation_number }),
  submitElectronically: async (id: number) => {
    await api.post<AppealSubmission>(`/api/v1/appeals/${id}/submissions`, {});
    return api.get<Appeal>(`/api/v1/appeals/${id}`);
  },
};
