export type WorkflowStepType =
  | "ai_analysis"
  | "generate_appeal"
  | "condition"
  | "human_approval"
  | "wait"
  | "email"
  | "notification"
  | "publish_event"
  | "assign_user"
  | "upload_document"
  | "call_api"
  | "loop"
  | "end";

export type WorkflowTrigger =
  | "claim.created"
  | "claim.imported"
  | "claim.analyzed"
  | "appeal.generated"
  | "appeal.approved"
  | "submission.created"
  | "submission.failed"
  | "payment.received"
  | "payment.verified"
  | "invoice.generated";

export interface WorkflowStep {
  id: number;
  step_order: number;
  step_type: WorkflowStepType;
  name: string;
  configuration: Record<string, unknown>;
  next_step_id: number | null;
  failure_step_id: number | null;
  max_retries: number;
  retry_delay_seconds: number;
}

export interface WorkflowDefinition {
  id: number;
  name: string;
  description: string | null;
  trigger_event: WorkflowTrigger | null;
  trigger_conditions: string | null;
  is_active: boolean;
  version: number;
  steps: WorkflowStep[];
}

export type WorkflowExecutionStatus =
  | "pending"
  | "running"
  | "waiting_approval"
  | "completed"
  | "failed";

export interface WorkflowExecution {
  id: number;
  workflow_id: number;
  claim_id: number | null;
  trigger_event: string | null;
  trigger_event_id: string | null;
  trigger_payload: Record<string, unknown>;
  duration_ms: number | null;
  status: WorkflowExecutionStatus;
  current_step_id: number | null;
  context: Record<string, unknown>;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  step_executions: Array<{
    id: number;
    step_id: number;
    status: string;
    attempt: number;
    output: Record<string, unknown> | null;
    error_message: string | null;
    started_at: string;
    completed_at: string | null;
  }>;
}

export interface WorkflowCreateInput {
  name: string;
  description?: string;
  trigger_event?: WorkflowTrigger;
  trigger_conditions?: string;
  is_active: boolean;
}

export interface WorkflowStepCreateInput {
  step_order: number;
  step_type: WorkflowStepType;
  name: string;
  configuration: Record<string, unknown>;
  max_retries: number;
  retry_delay_seconds: number;
}
