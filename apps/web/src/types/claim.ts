export type ClaimStatus =
  | "imported"
  | "pending"
  | "paid"
  | "denied"
  | "appealed"
  | "closed";

export type Priority = "low" | "medium" | "high" | "critical";
export type AnalysisStatus = "pending" | "running" | "completed" | "failed";

export interface Claim {
  id: number;
  organization_id: number;
  branch_id?: number | null;
  department_id?: number | null;
  currency: string;
  patient_id: number;
  payer_id: number;
  patient_name?: string | null;
  payer_name?: string | null;
  claim_number: string;
  status: ClaimStatus;
  billed_amount: number;
  paid_amount: number;
  service_date: string;
  provider?: string | null;
  priority: Priority;
  assigned_user_id?: number | null;
  assigned_user_name?: string | null;
  ai_risk_score?: number | null;
  recovery_probability?: number | null;
  diagnosis_codes?: string[];
  procedure_codes?: string[];
  denial_code?: string | null;
  appeal_status?: string | null;
  recovery_status?: string | null;
  ai_score?: number | null;
  analysis_status: AnalysisStatus;
  created_at?: string;
}

export interface ClaimCreateInput {
  branch_id?: number;
  department_id?: number;
  patient_id: number;
  payer_id: number;
  claim_number?: string;
  status?: string;
  billed_amount: number;
  paid_amount?: number;
  service_date?: string;
  provider?: string;
  priority?: Priority;
  assigned_user_id?: number;
  ai_risk_score?: number;
  recovery_probability?: number;
}

export interface ClaimTimelineEvent {
  id: number;
  event_type: string;
  description: string;
  actor_id?: number | null;
  metadata?: Record<string, unknown> | null;
  occurred_at: string;
}

export interface Lookup {
  id: number;
  name: string;
}

export interface ClaimDetail extends Claim {
  recovery_cases: RecoveryCase[];
  denials: Denial[];
}

export interface ClaimAnalysisResult {
  status: AnalysisStatus;
  risk_score?: number | null;
  priority?: string | null;
  confidence?: number | null;
  recovery_probability?: number | null;
  recommended_action?: string | null;
  summary?: string | null;
  required_documents: string[];
}

export interface Denial {
  id: number;
  denial_type: string;
  denial_code: string;
  description: string;
}

export interface RecoveryCase {
  id: number;
  claim_id: number;
  recovery_score: number;
  estimated_value: number;
  status: string;
  recommendation: string;
}
