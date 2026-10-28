export type ImportJobStatus = "queued" | "processing" | "completed" | "failed" | string;

export interface ImportJobError {
  row: number;
  claim_number?: string | null;
  error: string;
}

export interface ImportJob {
  job_id: number;
  status: ImportJobStatus;
  filename: string | null;
  processed: number;
  total: number | null;
  total_rows: number;
  valid_rows: number;
  imported: number;
  duplicates: number;
  invalid: number;
  queued_for_ai: number;
  duration_ms: number | null;
  errors: ImportJobError[] | null;
  error_message: string | null;
}
