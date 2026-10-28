import { api } from "@/lib/api-client";

export type TaskStatus =
  | "new"
  | "assigned"
  | "in_progress"
  | "waiting"
  | "completed"
  | "overdue"
  | "cancelled";

export interface TaskQueueItem {
  id: number;
  claim_id: number;
  payer_id: number;
  assigned_to: number | null;
  department: string;
  priority_score: number;
  task_type: string;
  status: TaskStatus;
  due_date: string;
  completed_at: string | null;
  notes: string | null;
  escalation_level: number;
  created_at: string;
  updated_at: string;
  claim_number: string;
  payer_name: string;
  billed_amount: number;
  assignee_name: string | null;
}

export interface TaskQueueResponse {
  count: number;
  items: TaskQueueItem[];
}

export interface ManagerTaskDashboard {
  open_tasks: number;
  completed_today: number;
  overdue_tasks: number;
  average_completion_hours: number;
}

export interface StaffTaskPerformance {
  user_id: number;
  user_name: string;
  role: string;
  completed_tasks: number;
  average_completion_hours: number;
  average_priority: number;
  total_claim_value: number;
}

export interface TaskPerformanceResponse {
  caution: string;
  staff: StaffTaskPerformance[];
}

export interface TaskNotification {
  id: number;
  task_id: number;
  notification_type: string;
  title: string;
  message: string;
  level: number;
  read_at: string | null;
  created_at: string;
}

export const tasksService = {
  queue: (params: Record<string, string> = {}) => {
    const search = new URLSearchParams(params).toString();
    return api.get<TaskQueueResponse>(`/api/v1/tasks/queue${search ? `?${search}` : ""}`);
  },
  manager: () => api.get<ManagerTaskDashboard>("/api/v1/tasks/manager"),
  performance: () => api.get<TaskPerformanceResponse>("/api/v1/tasks/performance"),
  transition: (taskId: number, status: TaskStatus, reason: string) =>
    api.post<TaskQueueItem>(`/api/v1/tasks/${taskId}/transition`, { status, reason }),
  notifications: () =>
    api.get<TaskNotification[]>("/api/v1/tasks/notifications?unread_only=true"),
  markNotificationRead: (notificationId: number) =>
    api.post<TaskNotification>(`/api/v1/tasks/notifications/${notificationId}/read`),
};