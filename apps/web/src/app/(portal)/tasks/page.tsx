"use client";

import { useState, type ElementType } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  ListChecks,
  Play,
  TimerReset,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/context/auth-context";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";
import { tasksService, type TaskQueueItem, type TaskStatus } from "@/services/tasks-service";

type QueueWindow = "today" | "tomorrow" | "overdue" | "week";

const MANAGER_ROLES = new Set(["owner", "admin", "manager"]);
const STATUS_LABELS: Record<TaskStatus, string> = {
  new: "New",
  assigned: "Assigned",
  in_progress: "In progress",
  waiting: "Waiting",
  completed: "Completed",
  overdue: "Overdue",
  cancelled: "Cancelled",
};

function dateValue(offset = 0) {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function filtersFor(window: QueueWindow): Record<string, string> {
  if (window === "overdue") return { status: "overdue" };
  if (window === "tomorrow") return { due_from: dateValue(1), due_to: dateValue(1) };
  if (window === "week") return { due_from: dateValue(), due_to: dateValue(7) };
  return { due_to: dateValue() };
}

function titleCase(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function Priority({ score }: { score: number }) {
  return (
    <div
      className={cn(
        "flex h-11 w-11 shrink-0 items-center justify-center rounded-md border text-sm font-bold",
        score >= 90
          ? "border-rose-200 bg-rose-50 text-rose-700"
          : score >= 70
            ? "border-amber-200 bg-amber-50 text-amber-700"
            : "border-slate-200 bg-slate-50 text-slate-700",
      )}
      title={`Priority ${score} of 100`}
    >
      {score}
    </div>
  );
}

function TaskRow({
  task,
  onTransition,
  pending,
}: {
  task: TaskQueueItem;
  onTransition: (task: TaskQueueItem, status: TaskStatus) => void;
  pending: boolean;
}) {
  const overdue = task.status === "overdue" || new Date(task.due_date) < new Date();
  const actionable = ["assigned", "in_progress", "waiting", "overdue"].includes(task.status);

  return (
    <div className="grid gap-4 border-b px-4 py-4 last:border-b-0 lg:grid-cols-[auto_1fr_150px_150px_auto] lg:items-center">
      <Priority score={task.priority_score} />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-semibold">{titleCase(task.task_type)}</p>
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[11px] font-medium",
              overdue ? "bg-rose-50 text-rose-700" : "bg-slate-100 text-slate-600",
            )}
          >
            {STATUS_LABELS[task.status]}
          </span>
        </div>
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className="font-mono">{task.claim_number}</span>
          <span>{task.payer_name}</span>
          <span>{formatCurrency(task.billed_amount)}</span>
        </div>
      </div>
      <div className="text-xs">
        <p className="text-muted-foreground">Due</p>
        <p className={cn("mt-0.5 font-medium", overdue && "text-rose-700")}>
          {new Date(task.due_date).toLocaleDateString("en-KE", {
            day: "numeric",
            month: "short",
            year: "numeric",
          })}
        </p>
      </div>
      <div className="text-xs">
        <p className="text-muted-foreground">Assigned to</p>
        <p className="mt-0.5 truncate font-medium">{task.assignee_name ?? "Unassigned"}</p>
      </div>
      <div className="flex items-center justify-end gap-1">
        {task.status === "assigned" && (
          <Button
            size="sm"
            variant="outline"
            disabled={pending}
            onClick={() => onTransition(task, "in_progress")}
          >
            <Play className="mr-1.5 h-3.5 w-3.5" /> Start
          </Button>
        )}
        {actionable && (
          <Button size="sm" disabled={pending} onClick={() => onTransition(task, "completed")}>
            <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" /> Complete
          </Button>
        )}
        <Button size="icon" variant="ghost" asChild>
          <Link href={`/claims/${task.claim_id}`} title="Open claim">
            <ChevronRight className="h-4 w-4" />
          </Link>
        </Button>
      </div>
    </div>
  );
}

export default function TasksPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [window, setWindow] = useState<QueueWindow>("today");
  const [payerId, setPayerId] = useState("");
  const manager = MANAGER_ROLES.has(user?.role ?? "");
  const params = { ...filtersFor(window), ...(payerId ? { payer_id: payerId } : {}) };
  const queue = useQuery({
    queryKey: ["task-queue", params],
    queryFn: () => tasksService.queue(params),
  });
  const managerMetrics = useQuery({
    queryKey: ["task-manager"],
    queryFn: tasksService.manager,
    enabled: manager,
  });
  const performance = useQuery({
    queryKey: ["task-performance"],
    queryFn: tasksService.performance,
    enabled: manager,
  });
  const transition = useMutation({
    mutationFn: ({ task, status }: { task: TaskQueueItem; status: TaskStatus }) =>
      tasksService.transition(task.id, status, `${STATUS_LABELS[status]} from daily work queue`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["task"] }),
  });
  const items = queue.data?.items ?? [];
  const payers = Array.from(new Map(items.map((task) => [task.payer_id, task.payer_name])).entries());
  const managerCards: Array<{
    label: string;
    value: string | number | undefined;
    icon: ElementType;
  }> = [
    { label: "Open tasks", value: managerMetrics.data?.open_tasks, icon: ListChecks },
    {
      label: "Completed today",
      value: managerMetrics.data?.completed_today,
      icon: CheckCircle2,
    },
    { label: "Overdue", value: managerMetrics.data?.overdue_tasks, icon: AlertTriangle },
    {
      label: "Average completion",
      value: managerMetrics.data
        ? `${managerMetrics.data.average_completion_hours}h`
        : undefined,
      icon: TimerReset,
    },
  ];

  return (
    <div className="flex h-full flex-col">
      <Header title="Today's Work" />
      <div className="flex-1 space-y-6 overflow-y-auto p-4 sm:p-6">
        <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="text-xs font-medium uppercase text-muted-foreground">
              {new Date().toLocaleDateString("en-KE", {
                weekday: "long",
                day: "numeric",
                month: "long",
              })}
            </p>
            <h2 className="mt-1 text-2xl font-semibold">Good morning, {user?.first_name}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Ranked by recoverability, claim value, and urgency.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {(["today", "tomorrow", "overdue", "week"] as QueueWindow[]).map((value) => (
              <Button
                key={value}
                size="sm"
                variant={window === value ? "default" : "outline"}
                onClick={() => setWindow(value)}
              >
                {value === "week" ? "Next week" : titleCase(value)}
              </Button>
            ))}
            <select
              aria-label="Filter by payer"
              value={payerId}
              onChange={(event) => setPayerId(event.target.value)}
              className="h-9 rounded-md border bg-background px-3 text-sm"
            >
              <option value="">All payers</option>
              {payers.map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </div>
        </section>

        {manager && (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {managerCards.map(({ label, value, icon: Icon }) => (
              <Card key={label}>
                <CardContent className="flex items-center justify-between p-4">
                  <div>
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="mt-1 text-2xl font-bold">{value ?? "—"}</p>
                  </div>
                  <Icon className="h-5 w-5 text-muted-foreground" />
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        <section>
          <div className="mb-3 flex items-end justify-between">
            <div>
              <h2 className="text-sm font-semibold">Priority queue</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {formatNumber(queue.data?.count ?? 0)} tasks in this view
              </p>
            </div>
          </div>
          <Card>
            <CardContent className="p-0">
              {queue.isLoading ? (
                <div className="space-y-3 p-4">
                  {Array.from({ length: 5 }).map((_, index) => (
                    <Skeleton key={index} className="h-20 w-full" />
                  ))}
                </div>
              ) : items.length === 0 ? (
                <div className="py-16 text-center">
                  <CheckCircle2 className="mx-auto h-7 w-7 text-emerald-600" />
                  <p className="mt-3 text-sm font-medium">This view is clear</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    New work will appear here automatically.
                  </p>
                </div>
              ) : (
                items.map((task) => (
                  <TaskRow
                    key={task.id}
                    task={task}
                    pending={transition.isPending}
                    onTransition={(item, status) => transition.mutate({ task: item, status })}
                  />
                ))
              )}
            </CardContent>
          </Card>
        </section>

        {manager && performance.data && (
          <section>
            <h2 className="text-sm font-semibold">Team flow</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">{performance.data.caution}</p>
            <div className="mt-3 overflow-x-auto rounded-lg border bg-card">
              <table className="w-full min-w-[680px] text-sm">
                <thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">Staff member</th>
                    <th className="px-4 py-3 text-right">Completed</th>
                    <th className="px-4 py-3 text-right">Avg. time</th>
                    <th className="px-4 py-3 text-right">Avg. priority</th>
                    <th className="px-4 py-3 text-right">Claim value handled</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {performance.data.staff.map((member) => (
                    <tr key={member.user_id}>
                      <td className="px-4 py-3">
                        <p className="font-medium">{member.user_name}</p>
                        <p className="text-xs text-muted-foreground">{titleCase(member.role)}</p>
                      </td>
                      <td className="px-4 py-3 text-right">{member.completed_tasks}</td>
                      <td className="px-4 py-3 text-right">{member.average_completion_hours}h</td>
                      <td className="px-4 py-3 text-right">{member.average_priority}</td>
                      <td className="px-4 py-3 text-right font-medium">
                        {formatCurrency(member.total_claim_value)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}