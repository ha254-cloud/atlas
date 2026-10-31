"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  BookOpenCheck,
  CircleAlert,
  Landmark,
  Loader2,
  PlusCircle,
  ShieldCheck,
  ShieldX,
  Stethoscope,
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
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/features/auth/context/auth-context";
import { getErrorMessage } from "@/lib/api-client";
import { cn, formatDate } from "@/lib/utils";
import { payersService } from "@/services/payers-service";
import type {
  Payer,
  PayerApprovalStatus,
  PayerHealthStatus,
  PolicySourceStatus,
  PolicySourceType,
} from "@/types/payer";

const APPROVAL_STATE: Record<
  PayerApprovalStatus,
  { label: string; variant: "success" | "warning" | "destructive" | "secondary" }
> = {
  draft: { label: "Draft", variant: "secondary" },
  pending_approval: { label: "Pending approval", variant: "warning" },
  approved: { label: "Approved", variant: "success" },
  rejected: { label: "Rejected", variant: "destructive" },
};

const HEALTH_STATE: Record<
  PayerHealthStatus,
  { label: string; variant: "success" | "warning" | "destructive" | "secondary" }
> = {
  not_configured: { label: "Not configured", variant: "secondary" },
  healthy: { label: "Healthy", variant: "success" },
  unhealthy: { label: "Unhealthy", variant: "destructive" },
};

const POLICY_STATE: Record<
  PolicySourceStatus,
  { label: string; variant: "success" | "warning" | "destructive" | "secondary" }
> = {
  draft: { label: "Draft", variant: "secondary" },
  pending_approval: { label: "Pending approval", variant: "warning" },
  approved: { label: "Approved", variant: "success" },
  rejected: { label: "Rejected", variant: "destructive" },
  retired: { label: "Retired", variant: "secondary" },
};

// Owner/admin/manager hold both `configure_integrations` (maker) and
// `approve_payers` (checker) permissions; see app/security/permissions.py.
const CAN_MANAGE_ROLES = new Set(["owner", "admin", "manager"]);

function CreatePayerDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [payerCode, setPayerCode] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => payersService.create({ name, payer_code: payerCode, reason }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["payers"] });
      setName("");
      setPayerCode("");
      setReason("");
      setError(null);
      onOpenChange(false);
    },
    onError: (err) => setError(getErrorMessage(err, "Payer could not be created.")),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add payer</DialogTitle>
          <DialogDescription>
            New payers start in draft and must be submitted for approval before they can be used.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="payer-name">Name</Label>
            <Input id="payer-name" value={name} onChange={(event) => setName(event.target.value)} className="mt-1" />
          </div>
          <div>
            <Label htmlFor="payer-code">Payer code</Label>
            <Input
              id="payer-code"
              value={payerCode}
              onChange={(event) => setPayerCode(event.target.value)}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="payer-reason">Reason</Label>
            <Textarea
              id="payer-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              className="mt-1"
              maxLength={500}
              placeholder="Why is this payer being added?"
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button
            className="w-full"
            disabled={!name.trim() || !payerCode.trim() || reason.trim().length < 3 || create.isPending}
            onClick={() => create.mutate()}
          >
            {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlusCircle className="h-4 w-4" />}
            Add payer
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function RejectPayerDialog({
  payer,
  onOpenChange,
  onRejected,
}: {
  payer: Payer | null;
  onOpenChange: (open: boolean) => void;
  onRejected: () => void;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reject = useMutation({
    mutationFn: () => payersService.reject(payer!.id, reason),
    onSuccess: () => {
      setReason("");
      setError(null);
      onRejected();
    },
    onError: (err) => setError(getErrorMessage(err, "Payer could not be rejected.")),
  });

  return (
    <Dialog open={payer !== null} onOpenChange={(open) => { if (!open) { setReason(""); setError(null); } onOpenChange(open); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reject {payer?.name}</DialogTitle>
          <DialogDescription>A reason is required and is recorded on the audit trail.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <Textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            maxLength={500}
            placeholder="Why is this payer being rejected?"
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button
            variant="destructive"
            className="w-full"
            disabled={reason.trim().length < 3 || reject.isPending}
            onClick={() => reject.mutate()}
          >
            {reject.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldX className="h-4 w-4" />}
            Reject payer
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function PolicySourcesDialog({
  payer,
  currentUserId,
  canManage,
  onOpenChange,
}: {
  payer: Payer | null;
  currentUserId: number | undefined;
  canManage: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [policyCode, setPolicyCode] = useState("");
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<PolicySourceType>("operating_guidance");
  const [sourceReference, setSourceReference] = useState("");
  const [sourceUri, setSourceUri] = useState("");
  const [content, setContent] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState("");
  const [effectiveTo, setEffectiveTo] = useState("");
  const [denialCategories, setDenialCategories] = useState("");
  const [procedureCodes, setProcedureCodes] = useState("");
  const [reason, setReason] = useState("");
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const queryKey = ["payer-policy-sources", payer?.id];
  const sources = useQuery({
    queryKey,
    queryFn: () => payersService.listPolicySources(payer!.id),
    enabled: payer !== null,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey });

  const create = useMutation({
    mutationFn: () =>
      payersService.createPolicySource(payer!.id, {
        policy_code: policyCode,
        title,
        source_type: sourceType,
        source_reference: sourceReference,
        source_uri: sourceUri.trim() || null,
        content,
        effective_from: effectiveFrom,
        effective_to: effectiveTo || null,
        denial_categories: denialCategories.split(",").map((item) => item.trim()).filter(Boolean),
        procedure_codes: procedureCodes.split(",").map((item) => item.trim()).filter(Boolean),
        reason,
      }),
    onSuccess: () => {
      setPolicyCode("");
      setTitle("");
      setSourceReference("");
      setSourceUri("");
      setContent("");
      setEffectiveFrom("");
      setEffectiveTo("");
      setDenialCategories("");
      setProcedureCodes("");
      setReason("");
      setMessage("Immutable policy version created in draft.");
      void refresh();
    },
    onError: (error) => setMessage(getErrorMessage(error, "Policy version could not be created.")),
  });
  const submit = useMutation({
    mutationFn: (sourceId: number) => payersService.submitPolicySource(payer!.id, sourceId),
    onSuccess: () => { setMessage("Policy version submitted for independent approval."); void refresh(); },
    onError: (error) => setMessage(getErrorMessage(error, "Policy version could not be submitted.")),
  });
  const approve = useMutation({
    mutationFn: (sourceId: number) => payersService.approvePolicySource(payer!.id, sourceId),
    onSuccess: () => { setMessage("Policy version approved for appeal grounding."); void refresh(); },
    onError: (error) => setMessage(getErrorMessage(error, "Policy version could not be approved.")),
  });
  const reject = useMutation({
    mutationFn: (sourceId: number) =>
      payersService.rejectPolicySource(payer!.id, sourceId, rejectionReason),
    onSuccess: () => {
      setRejectingId(null);
      setRejectionReason("");
      setMessage("Policy version rejected.");
      void refresh();
    },
    onError: (error) => setMessage(getErrorMessage(error, "Policy version could not be rejected.")),
  });

  const canCreate =
    payer?.approval_status === "approved"
    && policyCode.trim().length >= 2
    && title.trim().length >= 3
    && sourceReference.trim().length >= 3
    && content.trim().length >= 20
    && Boolean(effectiveFrom)
    && reason.trim().length >= 3;

  return (
    <Dialog open={payer !== null} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-5xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Governed policy sources · {payer?.name}</DialogTitle>
          <DialogDescription>
            Only independently approved, effective Kenya sources can ground an appeal. New
            revisions create immutable versions and retire the prior approved version.
          </DialogDescription>
        </DialogHeader>

        {message && <p className="rounded-md border bg-muted/40 px-3 py-2 text-sm">{message}</p>}

        {canManage && payer?.approval_status === "approved" && (
          <div className="space-y-4 rounded-lg border p-4">
            <div>
              <p className="text-sm font-semibold">Create a policy version</p>
              <p className="text-xs text-muted-foreground">
                Enter reviewed source text, not an AI summary. Reuse a policy code to create its
                next version.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="policy-code">Policy code</Label>
                <Input id="policy-code" value={policyCode} onChange={(event) => setPolicyCode(event.target.value)} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="policy-title">Title</Label>
                <Input id="policy-title" value={title} onChange={(event) => setTitle(event.target.value)} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="policy-type">Source type</Label>
                <select
                  id="policy-type"
                  value={sourceType}
                  onChange={(event) => setSourceType(event.target.value as PolicySourceType)}
                  className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm"
                >
                  <option value="payer_contract">Payer contract</option>
                  <option value="benefit_schedule">Benefit schedule</option>
                  <option value="operating_guidance">Operating guidance</option>
                  <option value="clinical_guideline">Clinical guideline</option>
                  <option value="regulation">Regulation</option>
                </select>
              </div>
              <div>
                <Label htmlFor="policy-reference">Source reference</Label>
                <Input id="policy-reference" value={sourceReference} onChange={(event) => setSourceReference(event.target.value)} className="mt-1" placeholder="Document and section" />
              </div>
              <div className="sm:col-span-2">
                <Label htmlFor="policy-uri">Source URL (optional)</Label>
                <Input id="policy-uri" type="url" value={sourceUri} onChange={(event) => setSourceUri(event.target.value)} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="effective-from">Effective from</Label>
                <Input id="effective-from" type="date" value={effectiveFrom} onChange={(event) => setEffectiveFrom(event.target.value)} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="effective-to">Effective to (optional)</Label>
                <Input id="effective-to" type="date" value={effectiveTo} onChange={(event) => setEffectiveTo(event.target.value)} className="mt-1" />
              </div>
              <div>
                <Label htmlFor="denial-categories">Denial categories</Label>
                <Input id="denial-categories" value={denialCategories} onChange={(event) => setDenialCategories(event.target.value)} className="mt-1" placeholder="PRIOR_AUTHORIZATION, CODING" />
              </div>
              <div>
                <Label htmlFor="procedure-codes">Procedure codes</Label>
                <Input id="procedure-codes" value={procedureCodes} onChange={(event) => setProcedureCodes(event.target.value)} className="mt-1" placeholder="99213, 93000" />
              </div>
              <div className="sm:col-span-2">
                <Label htmlFor="policy-content">Reviewed source text</Label>
                <Textarea id="policy-content" value={content} onChange={(event) => setContent(event.target.value)} className="mt-1 min-h-32" maxLength={20000} />
              </div>
              <div className="sm:col-span-2">
                <Label htmlFor="policy-reason">Change reason</Label>
                <Textarea id="policy-reason" value={reason} onChange={(event) => setReason(event.target.value)} className="mt-1" maxLength={500} />
              </div>
            </div>
            <Button disabled={!canCreate || create.isPending} onClick={() => create.mutate()}>
              {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PlusCircle className="h-4 w-4" />}
              Create draft version
            </Button>
          </div>
        )}

        {payer?.approval_status !== "approved" && (
          <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            Approve the payer configuration before approving policy sources.
          </p>
        )}

        <div className="space-y-3">
          <p className="text-sm font-semibold">Version history</p>
          {sources.isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : sources.isError ? (
            <p className="text-sm text-destructive">Policy sources could not be loaded.</p>
          ) : sources.data?.length ? (
            sources.data.map((source) => {
              const state = POLICY_STATE[source.status];
              const isSubmitter = source.submitted_by === currentUserId;
              return (
                <div key={source.id} className="rounded-lg border p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold">{source.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {source.policy_code} · version {source.version} · {source.source_reference}
                      </p>
                    </div>
                    <Badge variant={state.variant}>{state.label}</Badge>
                  </div>
                  <p className="mt-3 line-clamp-3 whitespace-pre-wrap text-xs leading-5">{source.content}</p>
                  <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
                    <span>Effective {formatDate(source.effective_from)}</span>
                    <span>{source.denial_categories.join(", ") || "All denial categories"}</span>
                    <span>{source.procedure_codes.join(", ") || "All procedures"}</span>
                  </div>
                  <p className="mt-2 truncate font-mono text-[10px] text-muted-foreground">
                    SHA-256 {source.content_sha256}
                  </p>
                  {source.rejection_reason && (
                    <p className="mt-2 text-xs text-destructive">{source.rejection_reason}</p>
                  )}
                  {canManage && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(source.status === "draft" || source.status === "rejected") && (
                        <Button size="sm" variant="outline" disabled={submit.isPending} onClick={() => submit.mutate(source.id)}>
                          Submit for approval
                        </Button>
                      )}
                      {source.status === "pending_approval" && (
                        <>
                          <Button size="sm" disabled={approve.isPending || isSubmitter} onClick={() => approve.mutate(source.id)}>
                            Approve source
                          </Button>
                          <Button size="sm" variant="ghost" className="text-destructive" disabled={isSubmitter} onClick={() => { setRejectingId(source.id); setRejectionReason(""); }}>
                            Reject
                          </Button>
                        </>
                      )}
                    </div>
                  )}
                  {rejectingId === source.id && (
                    <div className="mt-3 flex flex-col gap-2 border-t pt-3 sm:flex-row">
                      <Input value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} placeholder="Required rejection reason" maxLength={500} />
                      <Button variant="destructive" disabled={rejectionReason.trim().length < 3 || reject.isPending} onClick={() => reject.mutate(source.id)}>
                        Confirm rejection
                      </Button>
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
              No reviewed policy source has been added for this payer.
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function PayersPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<Payer | null>(null);
  const [policyTarget, setPolicyTarget] = useState<Payer | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const canManage = user ? CAN_MANAGE_ROLES.has(user.role) : false;

  const payers = useQuery({ queryKey: ["payers"], queryFn: () => payersService.list(false) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["payers"] });

  const submit = useMutation({
    mutationFn: payersService.submitForApproval,
    onSuccess: () => { setMessage("Payer submitted for approval."); void refresh(); },
    onError: (error) => setMessage(getErrorMessage(error, "Payer could not be submitted for approval.")),
  });
  const approve = useMutation({
    mutationFn: payersService.approve,
    onSuccess: () => { setMessage("Payer approved."); void refresh(); },
    onError: (error) => setMessage(getErrorMessage(error, "Payer could not be approved.")),
  });
  const checkHealth = useMutation({
    mutationFn: payersService.checkHealth,
    onSuccess: (result) => {
      setMessage(
        result.status === "healthy"
          ? `Connection healthy${result.latency_ms !== null ? ` (${Math.round(result.latency_ms)}ms)` : ""}.`
          : result.status === "not_configured"
            ? "No connector is bound to this payer."
            : `Connection unhealthy: ${result.error ?? "unknown error"}.`,
      );
      void refresh();
    },
    onError: (error) => setMessage(getErrorMessage(error, "Health check could not be completed.")),
  });

  const draftCount = payers.data?.filter((item) => item.approval_status === "draft").length ?? 0;
  const pendingCount = payers.data?.filter((item) => item.approval_status === "pending_approval").length ?? 0;
  const unhealthyCount = payers.data?.filter((item) => item.last_health_status === "unhealthy").length ?? 0;

  return (
    <div className="flex h-full flex-col">
      <Header title="Payers" />
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-7xl space-y-6">
          <div className="flex flex-col justify-between gap-4 border-b pb-5 sm:flex-row sm:items-end">
            <div>
              <h2 className="text-lg font-semibold">Payer registry</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Maker/checker approval and live connectivity monitoring for every payer.
              </p>
            </div>
            {canManage && (
              <Button onClick={() => setCreateOpen(true)}>
                <PlusCircle className="h-4 w-4" />
                Add payer
              </Button>
            )}
          </div>

          {message && (
            <div
              className={cn(
                "rounded-md border px-4 py-3 text-sm",
                message.includes("could not") || message.includes("unhealthy")
                  ? "border-red-200 bg-red-50 text-red-800"
                  : "border-blue-200 bg-blue-50 text-blue-900",
              )}
            >
              {message}
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="flex items-center gap-3 rounded-md border p-4">
              <Activity className="h-4 w-4 text-amber-600" />
              <div>
                <p className="text-sm font-medium">{draftCount} draft</p>
                <p className="text-xs text-muted-foreground">Not yet submitted for approval</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-md border p-4">
              <ShieldCheck className="h-4 w-4 text-blue-600" />
              <div>
                <p className="text-sm font-medium">{pendingCount} pending approval</p>
                <p className="text-xs text-muted-foreground">Awaiting a maker/checker decision</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-md border p-4">
              <CircleAlert className="h-4 w-4 text-rose-600" />
              <div>
                <p className="text-sm font-medium">{unhealthyCount} unhealthy</p>
                <p className="text-xs text-muted-foreground">Connector reported a failure</p>
              </div>
            </div>
          </div>

          {payers.isLoading ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-56" />
              ))}
            </div>
          ) : payers.isError ? (
            <div className="py-20 text-center text-sm text-destructive">
              <CircleAlert className="mx-auto mb-2 h-6 w-6" />
              Payers could not be loaded.
            </div>
          ) : payers.data?.length ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {payers.data.map((payer) => {
                const approvalState = APPROVAL_STATE[payer.approval_status] ?? APPROVAL_STATE.draft;
                const healthState = payer.last_health_status ? HEALTH_STATE[payer.last_health_status] ?? null : null;
                const isSubmitter = payer.submitted_by != null && payer.submitted_by === user?.id;
                return (
                  <Card key={payer.id}>
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <Landmark className="h-5 w-5 text-muted-foreground" strokeWidth={1.75} />
                          <div>
                            <h3 className="font-semibold">{payer.name}</h3>
                            <p className="text-xs text-muted-foreground">{payer.payer_code}</p>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1.5">
                          <Badge variant={approvalState.variant}>{approvalState.label}</Badge>
                          {healthState && <Badge variant={healthState.variant}>{healthState.label}</Badge>}
                        </div>
                      </div>

                      <div className="my-5 grid grid-cols-2 gap-3 border-y py-4 text-xs">
                        <div>
                          <p className="text-muted-foreground">Submission</p>
                          <p className="mt-1 font-medium capitalize">{payer.submission_method}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Last health check</p>
                          <p className="mt-1 font-medium">
                            {payer.last_health_checked_at ? formatDate(payer.last_health_checked_at) : "Never"}
                          </p>
                        </div>
                      </div>

                      {payer.rejection_reason && payer.approval_status === "rejected" && (
                        <p className="mb-4 line-clamp-2 text-xs text-destructive">{payer.rejection_reason}</p>
                      )}
                      {payer.last_health_error && (
                        <p className="mb-4 line-clamp-2 text-xs text-destructive">{payer.last_health_error}</p>
                      )}

                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setPolicyTarget(payer)}
                        >
                          <BookOpenCheck className="h-3.5 w-3.5" />
                          Policy sources
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => checkHealth.mutate(payer.id)}
                          disabled={checkHealth.isPending}
                        >
                          <Stethoscope className="h-3.5 w-3.5" />
                          Check health
                        </Button>
                        {canManage && (payer.approval_status === "draft" || payer.approval_status === "rejected") && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => submit.mutate(payer.id)}
                            disabled={submit.isPending}
                          >
                            Submit for approval
                          </Button>
                        )}
                        {canManage && payer.approval_status === "pending_approval" && (
                          <>
                            <Button
                              size="sm"
                              onClick={() => approve.mutate(payer.id)}
                              disabled={approve.isPending || isSubmitter}
                              title={isSubmitter ? "The submitter cannot approve their own payer" : undefined}
                            >
                              <ShieldCheck className="h-3.5 w-3.5" />
                              Approve
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-destructive"
                              onClick={() => setRejectTarget(payer)}
                              disabled={isSubmitter}
                              title={isSubmitter ? "The submitter cannot reject their own payer" : undefined}
                            >
                              <ShieldX className="h-3.5 w-3.5" />
                              Reject
                            </Button>
                          </>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          ) : (
            <div className="flex min-h-72 flex-col items-center justify-center border-y text-center">
              <div className="mb-3 rounded-md bg-muted p-3 text-muted-foreground">
                <Landmark className="h-6 w-6" />
              </div>
              <h3 className="text-sm font-semibold">No payers configured</h3>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                Add a payer to begin tracking approval status and connectivity health.
              </p>
            </div>
          )}
        </div>
      </div>

      <CreatePayerDialog open={createOpen} onOpenChange={setCreateOpen} />
      <RejectPayerDialog
        payer={rejectTarget}
        onOpenChange={(open) => { if (!open) setRejectTarget(null); }}
        onRejected={() => { setMessage("Payer rejected."); setRejectTarget(null); void refresh(); }}
      />
      <PolicySourcesDialog
        payer={policyTarget}
        currentUserId={user?.id}
        canManage={canManage}
        onOpenChange={(open) => { if (!open) setPolicyTarget(null); }}
      />
    </div>
  );
}
