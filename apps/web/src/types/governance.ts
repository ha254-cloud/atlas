export interface SecuritySummary {
  failed_logins_30d: number;
  password_resets_30d: number;
  inactive_users_90d: number;
  suspicious_users: number;
  active_sessions: number;
}

export interface ComplianceSummary {
  audit_status: "PASS" | "REVIEW";
  total_audit_events: number;
  missing_document_claims: number;
  outstanding_approvals: number;
  inactive_users: number;
  ai_calls_without_prompt_version: number;
  approved_appeals_without_approver: number;
  consented_patients: number;
  patients_without_consent: number;
  configured_retention_policies: number;
  retention_enforcement_mode: string;
  security: SecuritySummary;
}

export interface AuditEvent {
  id: number;
  organization_id: number;
  user_id: number;
  action: string;
  entity: string;
  entity_id: number | null;
  ip_address: string | null;
  user_agent: string | null;
  device: string | null;
  correlation_id: string | null;
  reason: string | null;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
}

export interface RetentionPolicy {
  id: number;
  organization_id: number;
  resource_type: string;
  version: number;
  retention_days: number;
  disposition: "archive" | "delete";
  legal_hold_default: boolean;
  enforcement_mode: string;
  created_by: number;
  reason: string;
  correlation_id: string;
  created_at: string;
}

export interface UserSession {
  id: string;
  user_id: number;
  ip_address: string | null;
  device: string | null;
  location: string | null;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  revoked_at: string | null;
}