export type IntegrationStatus = "pending" | "active" | "syncing" | "disconnected" | "error";

export interface Integration {
  id: number;
  provider: string;
  status: IntegrationStatus;
  last_sync_at: string | null;
  last_error: string | null;
  claims_imported_count: number;
  settings: Record<string, unknown> | null;
  created_at: string;
}

export interface IntegrationHealth {
  connected: boolean;
  latency_ms: number | null;
  provider: string;
  status: IntegrationStatus;
  last_sync_at: string | null;
  last_error: string | null;
}

export interface IntegrationMappingField {
  id?: number;
  source_field: string;
  target_field: string;
  transform: Record<string, unknown> | null;
  required: boolean;
  default_value: string | null;
}

export interface IntegrationMappingProfile {
  id: number;
  integration_id: number;
  version: number;
  name: string;
  source_format: string;
  reason: string;
  correlation_id: string;
  created_at: string;
  fields: IntegrationMappingField[];
}

export interface IntegrationSyncRun {
  id: number;
  integration_id: number;
  mapping_profile_id: number | null;
  trigger: string;
  status: "running" | "success" | "partial" | "failed";
  records_received: number;
  records_imported: number;
  records_rejected: number;
  error_summary: string | null;
  initiated_by: number | null;
  correlation_id: string;
  started_at: string;
  completed_at: string | null;
}

export interface IntegrationSyncError {
  id: number;
  row_number: number | null;
  source_field: string | null;
  error_code: string;
  message: string;
  created_at: string;
}