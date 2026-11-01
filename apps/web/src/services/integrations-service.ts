import { api } from "@/lib/api-client";
import type {
  Integration,
  IntegrationMappingField,
  IntegrationMappingProfile,
  IntegrationSyncError,
  IntegrationSyncRun,
} from "@/types/integration";

export interface IntegrationCreateInput {
  provider: string;
  settings?: Record<string, unknown>;
  access_token?: string;
  refresh_token?: string;
  credentials?:
    | { kind: "oauth2_client_credentials"; client_secret: string }
    | { kind: "oauth2"; access_token?: string; refresh_token?: string; expires_at?: string }
    | { kind: "api_key"; api_key: string }
    | { kind: "sftp"; password?: string; private_key?: string };
}

export interface MappingProfileCreateInput {
  name: string;
  source_format: "csv" | "excel" | "json" | "xml" | "rest";
  reason: string;
  fields: Omit<IntegrationMappingField, "id">[];
}

export const integrationsService = {
  providers: () => api.get<string[]>("/api/v1/integrations/providers"),
  list: () => api.get<Integration[]>("/api/v1/integrations"),
  get: (id: number) => api.get<Integration>(`/api/v1/integrations/${id}`),
  health: (id: number) =>
    api.get<{
      connected: boolean;
      latency_ms: number | null;
      provider: string;
      status: string;
      last_sync_at: string | null;
      last_error: string | null;
    }>(`/api/v1/integrations/${id}/health`),
  create: (input: string | IntegrationCreateInput) =>
    api.post<Integration>("/api/v1/integrations", typeof input === "string" ? { provider: input } : input),
  sync: (id: number) => api.post<{ status: string; integration_id: number }>(`/api/v1/integrations/${id}/sync`),
  disconnect: (id: number) => api.post<Integration>(`/api/v1/integrations/${id}/disconnect`),
  mappings: (id: number) =>
    api.get<IntegrationMappingProfile[]>(`/api/v1/integrations/${id}/mappings`),
  createMapping: (id: number, input: MappingProfileCreateInput) =>
    api.post<IntegrationMappingProfile>(`/api/v1/integrations/${id}/mappings`, input),
  previewMapping: (id: number, profileId: number, rawRecord: Record<string, unknown>) =>
    api.post<{
      valid: boolean;
      mapped_record: Record<string, unknown> | null;
      error_code: string | null;
      source_field: string | null;
      message: string | null;
    }>(`/api/v1/integrations/${id}/mappings/preview`, {
      profile_id: profileId,
      raw_record: rawRecord,
    }),
  runs: (id: number) =>
    api.get<IntegrationSyncRun[]>(`/api/v1/integrations/${id}/runs`),
  runErrors: (id: number, runId: number) =>
    api.get<IntegrationSyncError[]>(`/api/v1/integrations/${id}/runs/${runId}/errors`),
};