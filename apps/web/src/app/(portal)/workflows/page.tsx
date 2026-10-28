"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  CircleAlert,
  GitBranch,
  History,
  Loader2,
  PauseCircle,
  Play,
  Plus,
  Power,
  Trash2,
  Workflow as WorkflowIcon,
  X,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/features/auth/context/auth-context";
import { getErrorMessage } from "@/lib/api-client";
import { cn, formatDate } from "@/lib/utils";
import { workflowsService } from "@/services/workflows-service";
import type { WorkflowStepType, WorkflowTrigger } from "@/types/workflow";

const TRIGGERS: Array<{ value: WorkflowTrigger; label: string }> = [
  { value: "claim.created", label: "Claim created" },
  { value: "claim.imported", label: "Claim imported" },
  { value: "claim.analyzed", label: "Claim analyzed" },
  { value: "appeal.generated", label: "Appeal generated" },
  { value: "appeal.approved", label: "Appeal approved" },
  { value: "submission.created", label: "Submission created" },
  { value: "submission.failed", label: "Submission failed" },
  { value: "payment.received", label: "Payment received" },
  { value: "payment.verified", label: "Payment verified" },
  { value: "invoice.generated", label: "Invoice generated" },
];

const CONTROL_ACTIONS = ["condition", "human_approval", "wait", "end"];
const ACTION_LABELS: Record<string, string> = {
  ai_analysis: "AI analysis",
  generate_appeal: "Generate appeal",
  assign_user: "Assign user",
  condition: "Condition",
  email: "Email",
  end: "End",
  human_approval: "Human approval",
  notification: "Notification",
  publish_event: "Publish event",
  wait: "Wait",
};

const STATUS_VARIANTS = {
  pending: "secondary",
  running: "warning",
  waiting_approval: "warning",
  completed: "success",
  failed: "destructive",
} as const;

const fieldClass = "h-10 w-full rounded-md border bg-background px-3 text-sm";

export default function WorkflowsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [view, setView] = useState<"definitions" | "history">("definitions");
  const [createOpen, setCreateOpen] = useState(false);
  const [stepWorkflowId, setStepWorkflowId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [trigger, setTrigger] = useState<WorkflowTrigger | "">("");
  const [condition, setCondition] = useState("");
  const [stepName, setStepName] = useState("");
  const [stepType, setStepType] = useState<WorkflowStepType>("human_approval");
  const [configuration, setConfiguration] = useState("{}");
  const [maxRetries, setMaxRetries] = useState(0);
  const canManage = user ? ["admin", "manager", "owner"].includes(user.role) : false;

  const definitions = useQuery({ queryKey: ["workflows"], queryFn: workflowsService.list });
  const history = useQuery({ queryKey: ["workflow-history"], queryFn: workflowsService.history });
  const actions = useQuery({ queryKey: ["workflow-actions"], queryFn: workflowsService.actions });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["workflows"] });
    void queryClient.invalidateQueries({ queryKey: ["workflow-history"] });
  };

  const create = useMutation({
    mutationFn: workflowsService.create,
    onSuccess: () => {
      setCreateOpen(false);
      setName("");
      setDescription("");
      setTrigger("");
      setCondition("");
      setMessage("Workflow definition created.");
      refresh();
    },
    onError: (error) => setMessage(getErrorMessage(error, "Workflow could not be created.")),
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      active ? workflowsService.disable(id) : workflowsService.enable(id),
    onSuccess: refresh,
    onError: (error) => setMessage(getErrorMessage(error, "Workflow status could not be changed.")),
  });
  const remove = useMutation({
    mutationFn: workflowsService.remove,
    onSuccess: () => {
      setMessage("Workflow deleted.");
      refresh();
    },
    onError: (error) => setMessage(getErrorMessage(error, "Workflow could not be deleted.")),
  });
  const addStep = useMutation({
    mutationFn: ({ id, config }: { id: number; config: Record<string, unknown> }) => {
      const workflow = definitions.data?.find((item) => item.id === id);
      return workflowsService.addStep(id, {
        step_order: (workflow?.steps.length ?? 0) + 1,
        step_type: stepType,
        name: stepName,
        configuration: config,
        max_retries: maxRetries,
        retry_delay_seconds: maxRetries > 0 ? 30 : 0,
      });
    },
    onSuccess: () => {
      setStepWorkflowId(null);
      setStepName("");
      setConfiguration("{}");
      setMaxRetries(0);
      setMessage("Action added to workflow.");
      refresh();
    },
    onError: (error) => setMessage(getErrorMessage(error, "Action could not be added.")),
  });
  const approve = useMutation({
    mutationFn: ({ id, approved }: { id: number; approved: boolean }) =>
      workflowsService.approve(id, approved),
    onSuccess: refresh,
    onError: (error) => setMessage(getErrorMessage(error, "Approval decision could not be recorded.")),
  });

  const availableActions = Array.from(new Set([...CONTROL_ACTIONS, ...(actions.data ?? [])])).sort();

  function submitStep() {
    if (stepWorkflowId === null || !stepName.trim()) return;
    try {
      const parsed = JSON.parse(configuration) as unknown;
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
        throw new Error();
      }
      addStep.mutate({ id: stepWorkflowId, config: parsed as Record<string, unknown> });
    } catch {
      setMessage("Action configuration must be a JSON object.");
    }
  }

  return (
    <div className="flex h-full flex-col">
      <Header title="Workflow Engine" />
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-7xl space-y-5">
          <div className="flex flex-col justify-between gap-4 border-b pb-5 sm:flex-row sm:items-end">
            <div>
              <h2 className="text-lg font-semibold">Automation control plane</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                {definitions.data?.filter((item) => item.is_active).length ?? 0} active definitions
                <span className="mx-2">·</span>
                {history.data?.filter((item) => item.status === "waiting_approval").length ?? 0} awaiting approval
              </p>
            </div>
            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
              <div className="flex h-10 w-full rounded-md border bg-muted/40 p-1 sm:w-auto">
                <button
                  className={cn("flex flex-1 items-center justify-center gap-2 rounded px-3 text-sm sm:flex-none", view === "definitions" && "bg-background shadow-sm")}
                  onClick={() => setView("definitions")}
                >
                  <GitBranch className="h-4 w-4" /> Definitions
                </button>
                <button
                  className={cn("flex flex-1 items-center justify-center gap-2 rounded px-3 text-sm sm:flex-none", view === "history" && "bg-background shadow-sm")}
                  onClick={() => setView("history")}
                >
                  <History className="h-4 w-4" /> History
                </button>
              </div>
              {canManage && view === "definitions" && (
                <Button className="w-full sm:w-auto" onClick={() => setCreateOpen(true)}><Plus className="h-4 w-4" />New workflow</Button>
              )}
            </div>
          </div>

          {message && (
            <div className={cn("rounded-md border px-4 py-3 text-sm", message.includes("could not") || message.includes("must be") ? "border-red-200 bg-red-50 text-red-800" : "border-blue-200 bg-blue-50 text-blue-900")}>
              {message}
            </div>
          )}

          {view === "definitions" ? (
            definitions.isLoading ? (
              <div className="space-y-3">{Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-40" />)}</div>
            ) : definitions.isError ? (
              <div className="py-20 text-center text-sm text-destructive"><CircleAlert className="mx-auto mb-2 h-6 w-6" />Workflow definitions could not be loaded.</div>
            ) : definitions.data?.length ? (
              <div className="space-y-3">
                {definitions.data.map((workflow) => (
                  <Card key={workflow.id}>
                    <CardContent className="p-0">
                      <div className="flex flex-col gap-4 p-5 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-semibold">{workflow.name}</h3>
                            <Badge variant={workflow.is_active ? "success" : "secondary"}>{workflow.is_active ? "Enabled" : "Disabled"}</Badge>
                            <span className="text-xs text-muted-foreground">v{workflow.version}</span>
                          </div>
                          {workflow.description && <p className="mt-1 text-sm text-muted-foreground">{workflow.description}</p>}
                          <div className="mt-4 flex flex-wrap items-center gap-2">
                            <div className="flex h-9 items-center gap-2 rounded-md border border-dashed px-3 text-xs font-medium">
                              <Play className="h-3.5 w-3.5 text-emerald-600" />
                              {workflow.trigger_event ? TRIGGERS.find((item) => item.value === workflow.trigger_event)?.label : "Manual trigger"}
                            </div>
                            {workflow.steps.map((step) => (
                              <div key={step.id} className="contents">
                                <ArrowRight className="h-4 w-4 text-muted-foreground/50" />
                                <div className="flex h-9 items-center gap-2 rounded-md border bg-muted/30 px-3 text-xs font-medium">
                                  {step.step_type === "human_approval" && <PauseCircle className="h-3.5 w-3.5 text-amber-600" />}
                                  {step.name}
                                  <span className="text-muted-foreground">{ACTION_LABELS[step.step_type] ?? step.step_type}</span>
                                </div>
                              </div>
                            ))}
                            {!workflow.steps.length && <span className="text-xs text-muted-foreground">No actions</span>}
                          </div>
                          {workflow.trigger_conditions && <code className="mt-3 block text-xs text-muted-foreground">{workflow.trigger_conditions}</code>}
                        </div>
                        {canManage && (
                          <div className="flex shrink-0 gap-1">
                            <Button variant="outline" size="sm" onClick={() => setStepWorkflowId(workflow.id)}><Plus className="h-3.5 w-3.5" />Action</Button>
                            <Button variant="ghost" size="icon" title={workflow.is_active ? "Disable workflow" : "Enable workflow"} onClick={() => toggle.mutate({ id: workflow.id, active: workflow.is_active })} disabled={toggle.isPending}><Power className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="icon" title="Delete workflow" className="text-destructive" onClick={() => window.confirm(`Delete ${workflow.name}?`) && remove.mutate(workflow.id)} disabled={remove.isPending}><Trash2 className="h-4 w-4" /></Button>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="flex min-h-72 flex-col items-center justify-center border-y text-center">
                <WorkflowIcon className="mb-3 h-7 w-7 text-muted-foreground/60" />
                <h3 className="text-sm font-semibold">No workflow definitions</h3>
              </div>
            )
          ) : history.isLoading ? (
            <Skeleton className="h-80" />
          ) : history.isError ? (
            <div className="py-20 text-center text-sm text-destructive">Workflow history could not be loaded.</div>
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader><TableRow><TableHead>Started</TableHead><TableHead>Workflow</TableHead><TableHead>Trigger</TableHead><TableHead>Claim</TableHead><TableHead>Duration</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Decision</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {history.data?.length ? history.data.map((execution) => {
                      const definition = definitions.data?.find((item) => item.id === execution.workflow_id);
                      return (
                        <TableRow key={execution.id}>
                          <TableCell className="text-muted-foreground">{formatDate(execution.started_at)}</TableCell>
                          <TableCell className="font-medium">{definition?.name ?? `Workflow ${execution.workflow_id}`}</TableCell>
                          <TableCell className="font-mono text-xs">{execution.trigger_event ?? "manual"}</TableCell>
                          <TableCell>{execution.claim_id ?? "—"}</TableCell>
                          <TableCell>{execution.duration_ms !== null ? `${execution.duration_ms} ms` : "—"}</TableCell>
                          <TableCell><Badge variant={STATUS_VARIANTS[execution.status]}>{execution.status.replaceAll("_", " ")}</Badge></TableCell>
                          <TableCell className="text-right">
                            {execution.status === "waiting_approval" && canManage && (
                              <div className="flex justify-end gap-1">
                                <Button size="sm" onClick={() => approve.mutate({ id: execution.id, approved: true })} disabled={approve.isPending}><Check className="h-3.5 w-3.5" />Approve</Button>
                                <Button size="sm" variant="outline" onClick={() => approve.mutate({ id: execution.id, approved: false })} disabled={approve.isPending}><X className="h-3.5 w-3.5" />Reject</Button>
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    }) : <TableRow><TableCell colSpan={7} className="h-40 text-center text-sm text-muted-foreground">No workflow executions recorded.</TableCell></TableRow>}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[calc(100vh-2rem)] overflow-y-auto">
          <DialogHeader><DialogTitle>New workflow</DialogTitle><DialogDescription>Create a versioned automation definition.</DialogDescription></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2"><Label htmlFor="workflow-name">Name</Label><Input id="workflow-name" value={name} onChange={(event) => setName(event.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor="workflow-description">Description</Label><Textarea id="workflow-description" value={description} onChange={(event) => setDescription(event.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor="workflow-trigger">Trigger</Label><select id="workflow-trigger" className={fieldClass} value={trigger} onChange={(event) => setTrigger(event.target.value as WorkflowTrigger | "")}><option value="">Manual</option>{TRIGGERS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></div>
            {trigger && <div className="space-y-2"><Label htmlFor="workflow-condition">Trigger condition</Label><Input id="workflow-condition" value={condition} onChange={(event) => setCondition(event.target.value)} placeholder="event.recovery_probability >= 80" /></div>}
            <Button className="w-full" disabled={name.trim().length < 2 || create.isPending} onClick={() => create.mutate({ name: name.trim(), description: description.trim() || undefined, trigger_event: trigger || undefined, trigger_conditions: condition.trim() || undefined, is_active: true })}>{create.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Create workflow</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={stepWorkflowId !== null} onOpenChange={(open) => !open && setStepWorkflowId(null)}>
        <DialogContent className="max-h-[calc(100vh-2rem)] overflow-y-auto">
          <DialogHeader><DialogTitle>Add action</DialogTitle><DialogDescription>Append an ordered action to this workflow version.</DialogDescription></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2"><Label htmlFor="step-name">Action name</Label><Input id="step-name" value={stepName} onChange={(event) => setStepName(event.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor="step-type">Action type</Label><select id="step-type" className={fieldClass} value={stepType} onChange={(event) => setStepType(event.target.value as WorkflowStepType)}>{availableActions.map((item) => <option key={item} value={item}>{ACTION_LABELS[item] ?? item.replaceAll("_", " ")}</option>)}</select></div>
            <div className="space-y-2"><Label htmlFor="step-config">Configuration</Label><Textarea id="step-config" className="min-h-28 font-mono text-xs" value={configuration} onChange={(event) => setConfiguration(event.target.value)} /></div>
            <div className="space-y-2"><Label htmlFor="step-retries">Retries</Label><Input id="step-retries" type="number" min={0} max={10} value={maxRetries} onChange={(event) => setMaxRetries(Number(event.target.value))} /></div>
            <Button className="w-full" disabled={!stepName.trim() || addStep.isPending} onClick={submitStep}>{addStep.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Add action</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
