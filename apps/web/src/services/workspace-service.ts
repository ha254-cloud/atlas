import { api } from "@/lib/api-client";

export interface WorkspaceDenial { denial_code: string | null; denial_type: string | null; description: string | null; }
export interface WorkspaceCase {
  id: number; claim_id: number; claim_number: string; payer_name: string; payer_code: string;
  patient_name: string; patient_mrn: string; service_date: string | null;
  billed_amount: number; paid_amount: number; balance: number; estimated_recovery: number;
  recovery_score: number; confidence: number; priority: "critical" | "high" | "medium" | "low";
  status: string; recommendation: string; denial: WorkspaceDenial | null;
  ai_review: string | null; recovered_amount: number | null; invoice_generated: boolean;
}
export interface WorkspaceSummary {
  critical: number; high: number; medium: number; low: number; total: number;
  estimated_recovery: number; open_cases: number; in_progress_cases: number;
}
export interface WorkspaceResponse {
  summary: WorkspaceSummary; cases: WorkspaceCase[]; total: number; limit: number; offset: number;
}

export const workspaceService = {
  getWorkspace: (params?: { priority?: string; status?: string; search?: string; limit?: number; offset?: number }) =>
    api.get<WorkspaceResponse>("/api/v1/recovery-workspace", params as Record<string, unknown>),
  submitAIReview: (recovery_case_id: number, decision: "accepted" | "edited" | "rejected", reason?: string) =>
    api.post("/api/v1/recovery-workspace/ai-review", { recovery_case_id, decision, reason }),
};
