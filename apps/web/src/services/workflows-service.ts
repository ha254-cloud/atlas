import { api } from "@/lib/api-client";
import type {
  WorkflowCreateInput,
  WorkflowDefinition,
  WorkflowExecution,
  WorkflowStep,
  WorkflowStepCreateInput,
} from "@/types/workflow";

export const workflowsService = {
  list: () => api.get<WorkflowDefinition[]>("/api/v1/workflows"),
  history: () => api.get<WorkflowExecution[]>("/api/v1/workflow-history"),
  actions: () => api.get<string[]>("/api/v1/workflow-actions"),
  create: (input: WorkflowCreateInput) =>
    api.post<WorkflowDefinition>("/api/v1/workflows", input),
  addStep: (workflowId: number, input: WorkflowStepCreateInput) =>
    api.post<WorkflowStep>(`/api/v1/workflow-definitions/${workflowId}/steps`, input),
  enable: (workflowId: number) =>
    api.post<WorkflowDefinition>(`/api/v1/workflows/${workflowId}/enable`),
  disable: (workflowId: number) =>
    api.post<WorkflowDefinition>(`/api/v1/workflows/${workflowId}/disable`),
  remove: (workflowId: number) => api.delete<void>(`/api/v1/workflows/${workflowId}`),
  approve: (executionId: number, approved: boolean) =>
    api.post<WorkflowExecution>(`/api/v1/workflow-executions/${executionId}/approve`, {
      approved,
    }),
};
