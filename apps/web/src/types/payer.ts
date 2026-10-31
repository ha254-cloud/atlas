export type SubmissionMethod = "api" | "sftp" | "email" | "portal" | "manual";
export type StatusMethod = "api" | "portal" | "email" | "manual";
export type PaymentMethod =
  | "api"
  | "sftp"
  | "email"
  | "portal_export"
  | "csv"
  | "excel"
  | "report"
  | "manual";

export type PayerApprovalStatus = "draft" | "pending_approval" | "approved" | "rejected";
export type PayerHealthStatus = "not_configured" | "healthy" | "unhealthy";
export type PolicySourceType =
  | "payer_contract"
  | "benefit_schedule"
  | "operating_guidance"
  | "clinical_guideline"
  | "regulation";
export type PolicySourceStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "retired";

export interface Payer {
  id: number;
  organization_id: number;
  name: string;
  payer_code: string;
  country: string;
  submission_method: SubmissionMethod;
  status_method: StatusMethod;
  payment_method: PaymentMethod;
  portal_url: string | null;
  api_url: string | null;
  submission_email: string | null;
  supports_api: boolean;
  supports_sftp: boolean;
  supports_email: boolean;
  supports_manual: boolean;
  connector_name: string | null;
  integration_id: number | null;
  is_active: boolean;
  approval_status: PayerApprovalStatus;
  submitted_by: number | null;
  submitted_at: string | null;
  approved_by: number | null;
  approved_at: string | null;
  rejected_by: number | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  last_health_checked_at: string | null;
  last_health_status: PayerHealthStatus | null;
  last_health_error: string | null;
  health_check_failure_count: number;
}

export interface PayerHealthCheckResult {
  payer_id: number;
  status: PayerHealthStatus;
  checked_at: string;
  error: string | null;
  failure_count: number;
  latency_ms: number | null;
}

export interface PayerPolicySource {
  id: number;
  organization_id: number;
  payer_id: number;
  policy_code: string;
  title: string;
  source_type: PolicySourceType;
  jurisdiction: string;
  version: number;
  status: PolicySourceStatus;
  source_reference: string;
  source_uri: string | null;
  content: string;
  content_sha256: string;
  effective_from: string;
  effective_to: string | null;
  denial_categories: string[];
  procedure_codes: string[];
  created_by: number;
  change_reason: string;
  submitted_by: number | null;
  submitted_at: string | null;
  approved_by: number | null;
  approved_at: string | null;
  rejected_by: number | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  created_at: string | null;
}
