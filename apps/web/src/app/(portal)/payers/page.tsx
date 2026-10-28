"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
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
import type { Payer, PayerApprovalStatus, PayerHealthStatus } from "@/types/payer";

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

export default function PayersPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [rejectTarget, setRejectTarget] = useState<Payer | null>(null);
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
                          <div className="rounded-md bg-blue-50 p-2.5 text-blue-700">
                            <Landmark className="h-5 w-5" />
                          </div>
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
    </div>
  );
}
