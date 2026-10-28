import { api } from "@/lib/api-client";
import type {
  AuditEvent,
  ComplianceSummary,
  RetentionPolicy,
  UserSession,
} from "@/types/governance";

export interface RetentionPolicyInput {
  resource_type: string;
  retention_days: number;
  disposition: "archive" | "delete";
  legal_hold_default: boolean;
  reason: string;
}

export const governanceService = {
  summary: () => api.get<ComplianceSummary>("/api/v1/governance/summary"),
  recentAudit: () => api.get<AuditEvent[]>("/api/v1/audit-logs", { limit: 25 }),
  correlation: (correlationId: string) =>
    api.get<AuditEvent[]>(`/api/v1/governance/audit/correlations/${encodeURIComponent(correlationId)}`),
  retentionPolicies: () =>
    api.get<RetentionPolicy[]>("/api/v1/governance/retention-policies"),
  createRetentionPolicy: (input: RetentionPolicyInput) =>
    api.post<RetentionPolicy>("/api/v1/governance/retention-policies", input),
  sessions: () => api.get<UserSession[]>("/api/v1/governance/sessions"),
  revokeSession: (sessionId: string, reason: string) =>
    api.post<UserSession>(`/api/v1/governance/sessions/${sessionId}/revoke`, { reason }),
};