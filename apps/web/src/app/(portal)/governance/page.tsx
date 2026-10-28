"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Fingerprint,
  KeyRound,
  Loader2,
  Search,
  ShieldCheck,
  ShieldX,
  UserRoundCheck,
  UserRoundX,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/features/auth/context/auth-context";
import { getErrorMessage } from "@/lib/api-client";
import { formatDate, formatNumber } from "@/lib/utils";
import { governanceService } from "@/services/governance-service";
import type { AuditEvent } from "@/types/governance";

function EventTable({ events }: { events: AuditEvent[] }) {
  return (
    <div className="overflow-x-auto border">
      <table className="w-full min-w-[760px] text-sm">
        <thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground">
          <tr><th className="px-4 py-3">Time</th><th className="px-4 py-3">Action</th><th className="px-4 py-3">Resource</th><th className="px-4 py-3">Actor</th><th className="px-4 py-3">Reason</th></tr>
        </thead>
        <tbody className="divide-y">
          {events.map((event) => (
            <tr key={event.id}>
              <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">{formatDate(event.created_at)}</td>
              <td className="px-4 py-3 font-medium">{event.action.replaceAll(".", " / ")}</td>
              <td className="px-4 py-3"><span className="capitalize">{event.entity.replaceAll("_", " ")}</span>{event.entity_id ? ` #${event.entity_id}` : ""}</td>
              <td className="px-4 py-3">User {event.user_id}</td>
              <td className="max-w-64 truncate px-4 py-3 text-muted-foreground">{event.reason ?? "Recorded system action"}</td>
            </tr>
          ))}
          {!events.length && <tr><td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">No matching audit evidence.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

export default function GovernancePage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const canManage = user?.role === "admin" || user?.role === "owner";
  const [correlationId, setCorrelationId] = useState("");
  const [searchedCorrelation, setSearchedCorrelation] = useState("");
  const [resourceType, setResourceType] = useState("audit_logs");
  const [retentionDays, setRetentionDays] = useState(3650);
  const [message, setMessage] = useState<string | null>(null);

  const summary = useQuery({ queryKey: ["governance-summary"], queryFn: governanceService.summary });
  const recentAudit = useQuery({ queryKey: ["governance-audit"], queryFn: governanceService.recentAudit });
  const timeline = useQuery({
    queryKey: ["governance-correlation", searchedCorrelation],
    queryFn: () => governanceService.correlation(searchedCorrelation),
    enabled: searchedCorrelation.length > 0,
  });
  const policies = useQuery({ queryKey: ["retention-policies"], queryFn: governanceService.retentionPolicies });
  const sessions = useQuery({ queryKey: ["governance-sessions"], queryFn: governanceService.sessions, enabled: canManage });
  const createPolicy = useMutation({
    mutationFn: () => governanceService.createRetentionPolicy({
      resource_type: resourceType,
      retention_days: retentionDays,
      disposition: "archive",
      legal_hold_default: false,
      reason: "Hospital governance policy update",
    }),
    onSuccess: () => {
      setMessage("Retention policy version saved.");
      void queryClient.invalidateQueries({ queryKey: ["retention-policies"] });
      void queryClient.invalidateQueries({ queryKey: ["governance-summary"] });
    },
    onError: (error) => setMessage(getErrorMessage(error, "Retention policy could not be saved.")),
  });
  const revokeSession = useMutation({
    mutationFn: (sessionId: string) => governanceService.revokeSession(sessionId, "Terminated by hospital administrator"),
    onSuccess: () => {
      setMessage("Session terminated.");
      void queryClient.invalidateQueries({ queryKey: ["governance-sessions"] });
      void queryClient.invalidateQueries({ queryKey: ["governance-summary"] });
    },
    onError: (error) => setMessage(getErrorMessage(error, "Session could not be terminated.")),
  });

  const report = summary.data;
  const evidence = searchedCorrelation ? (timeline.data ?? []) : (recentAudit.data ?? []);
  const metrics = [
    { label: "Missing documentation", value: report?.missing_document_claims, icon: CircleAlert },
    { label: "Outstanding approvals", value: report?.outstanding_approvals, icon: Clock3 },
    { label: "Inactive users", value: report?.inactive_users, icon: UserRoundX },
    { label: "Audit events", value: report?.total_audit_events, icon: Fingerprint },
  ];

  return (
    <div className="flex h-full flex-col">
      <Header title="Governance" />
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-7xl space-y-8">
          <section className="flex flex-col justify-between gap-5 border-b pb-6 sm:flex-row sm:items-end">
            <div>
              <p className="text-xs font-medium uppercase text-muted-foreground">Compliance readiness</p>
              <div className="mt-2 flex items-center gap-3">
                {report?.audit_status === "PASS" ? <ShieldCheck className="h-8 w-8 text-emerald-700" /> : <ShieldX className="h-8 w-8 text-amber-700" />}
                <h2 className="text-3xl font-semibold">{report?.audit_status ?? "Checking"}</h2>
              </div>
              <p className="mt-2 max-w-2xl text-sm text-muted-foreground">Evidence coverage across user activity, AI calls, approvals, consent, and retention controls.</p>
            </div>
            <Badge variant={report?.audit_status === "PASS" ? "success" : "warning"}>{report?.retention_enforcement_mode.replaceAll("_", " ") ?? "loading"}</Badge>
          </section>

          {message && <div className="border-l-2 border-blue-600 bg-blue-50 px-4 py-3 text-sm text-blue-950">{message}</div>}

          <section className="grid gap-px overflow-hidden border bg-border sm:grid-cols-2 lg:grid-cols-4">
            {metrics.map(({ label, value, icon: Icon }) => <div key={label} className="bg-background p-4"><Icon className="h-4 w-4 text-muted-foreground" /><p className="mt-4 text-2xl font-semibold">{value === undefined ? "—" : formatNumber(value)}</p><p className="mt-1 text-xs text-muted-foreground">{label}</p></div>)}
          </section>

          <section>
            <div className="mb-4 flex flex-col justify-between gap-3 md:flex-row md:items-end">
              <div><h2 className="text-base font-semibold">Audit evidence</h2><p className="mt-1 text-sm text-muted-foreground">Follow one request, task, claim, payment, or appeal through its correlation ID.</p></div>
              <div className="flex w-full gap-2 md:w-auto"><Input value={correlationId} onChange={(event) => setCorrelationId(event.target.value)} placeholder="Correlation ID" className="md:w-72" /><Button variant="outline" title="Search correlation" onClick={() => setSearchedCorrelation(correlationId.trim())}><Search className="h-4 w-4" />Search</Button></div>
            </div>
            <EventTable events={evidence} />
          </section>

          <section className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <div className="mb-4"><h2 className="text-base font-semibold">Security activity</h2><p className="mt-1 text-sm text-muted-foreground">Authentication risk and active access across the hospital.</p></div>
              <div className="grid gap-px overflow-hidden border bg-border sm:grid-cols-2">
                <div className="bg-background p-4"><KeyRound className="h-4 w-4 text-red-700" /><p className="mt-3 text-xl font-semibold">{report?.security.failed_logins_30d ?? "—"}</p><p className="text-xs text-muted-foreground">Failed logins, 30 days</p></div>
                <div className="bg-background p-4"><UserRoundCheck className="h-4 w-4 text-emerald-700" /><p className="mt-3 text-xl font-semibold">{report?.security.active_sessions ?? "—"}</p><p className="text-xs text-muted-foreground">Active sessions</p></div>
                <div className="bg-background p-4"><Clock3 className="h-4 w-4 text-muted-foreground" /><p className="mt-3 text-xl font-semibold">{report?.security.password_resets_30d ?? "—"}</p><p className="text-xs text-muted-foreground">Password resets, 30 days</p></div>
                <div className="bg-background p-4"><CircleAlert className="h-4 w-4 text-amber-700" /><p className="mt-3 text-xl font-semibold">{report?.security.suspicious_users ?? "—"}</p><p className="text-xs text-muted-foreground">Suspicious users</p></div>
              </div>
            </div>
            <div>
              <div className="mb-4"><h2 className="text-base font-semibold">Consent coverage</h2><p className="mt-1 text-sm text-muted-foreground">Patient decisions are versioned and never overwritten.</p></div>
              <div className="border-l-2 border-emerald-600 bg-emerald-50 p-5 text-emerald-950"><p className="text-3xl font-semibold">{report?.consented_patients ?? "—"}</p><p className="mt-1 text-sm">Patients with recorded consent</p></div>
              <div className="mt-3 border-l-2 border-amber-500 bg-amber-50 p-5 text-amber-950"><p className="text-3xl font-semibold">{report?.patients_without_consent ?? "—"}</p><p className="mt-1 text-sm">Patients requiring a consent decision</p></div>
            </div>
          </section>

          <section>
            <div className="mb-4"><h2 className="text-base font-semibold">Retention policy register</h2><p className="mt-1 text-sm text-muted-foreground">Every change creates a new version. Enforcement remains report-only pending legal-hold and archive validation.</p></div>
            {canManage && <div className="mb-4 grid gap-3 border-y bg-muted/20 py-4 sm:grid-cols-[1fr_180px_auto]"><label className="space-y-1 px-3 text-xs font-medium">Resource<select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={resourceType} onChange={(event) => setResourceType(event.target.value)}><option value="clinical_documents">Clinical documents</option><option value="audit_logs">Audit logs</option><option value="invoices">Invoices</option><option value="temporary_uploads">Temporary uploads</option></select></label><label className="space-y-1 px-3 text-xs font-medium">Retention days<Input type="number" min={1} max={36500} value={retentionDays} onChange={(event) => setRetentionDays(Number(event.target.value))} /></label><div className="flex items-end px-3"><Button onClick={() => createPolicy.mutate()} disabled={createPolicy.isPending}>{createPolicy.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Archive className="h-4 w-4" />}Save version</Button></div></div>}
            <div className="overflow-x-auto border"><table className="w-full min-w-[680px] text-sm"><thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground"><tr><th className="px-4 py-3">Resource</th><th className="px-4 py-3">Version</th><th className="px-4 py-3">Retention</th><th className="px-4 py-3">Disposition</th><th className="px-4 py-3">Mode</th></tr></thead><tbody className="divide-y">{policies.data?.map((policy) => <tr key={policy.id}><td className="px-4 py-3 font-medium capitalize">{policy.resource_type.replaceAll("_", " ")}</td><td className="px-4 py-3">v{policy.version}</td><td className="px-4 py-3">{formatNumber(policy.retention_days)} days</td><td className="px-4 py-3 capitalize">{policy.disposition}</td><td className="px-4 py-3"><Badge variant="secondary">{policy.enforcement_mode.replaceAll("_", " ")}</Badge></td></tr>)}{!policies.data?.length && <tr><td colSpan={5} className="px-4 py-10 text-center text-muted-foreground">No retention policies configured.</td></tr>}</tbody></table></div>
          </section>

          {canManage && <section><div className="mb-4"><h2 className="text-base font-semibold">User sessions</h2><p className="mt-1 text-sm text-muted-foreground">Terminate access immediately when a device or account is no longer trusted.</p></div><div className="overflow-x-auto border"><table className="w-full min-w-[720px] text-sm"><thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground"><tr><th className="px-4 py-3">User</th><th className="px-4 py-3">Device</th><th className="px-4 py-3">IP address</th><th className="px-4 py-3">Started</th><th className="px-4 py-3">Status</th><th className="px-4 py-3"></th></tr></thead><tbody className="divide-y">{sessions.data?.map((session) => <tr key={session.id}><td className="px-4 py-3">User {session.user_id}</td><td className="px-4 py-3 capitalize">{session.device ?? "Unknown"}</td><td className="px-4 py-3 font-mono text-xs">{session.ip_address ?? "—"}</td><td className="px-4 py-3">{formatDate(session.created_at)}</td><td className="px-4 py-3">{session.revoked_at ? <Badge variant="secondary">Terminated</Badge> : <Badge variant="success">Active</Badge>}</td><td className="px-4 py-3 text-right"><Button size="sm" variant="outline" disabled={Boolean(session.revoked_at) || revokeSession.isPending} onClick={() => revokeSession.mutate(session.id)}>Terminate</Button></td></tr>)}</tbody></table></div></section>}

          {summary.isLoading && <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Calculating governance controls…</div>}
          {summary.isError && <div className="flex items-center gap-2 text-sm text-red-700"><CircleAlert className="h-4 w-4" />Compliance evidence could not be loaded.</div>}
          {report?.audit_status === "PASS" && <p className="flex items-center gap-2 pb-4 text-xs text-muted-foreground"><CheckCircle2 className="h-4 w-4 text-emerald-700" />No AI prompt or human-approval evidence gaps detected.</p>}
        </div>
      </div>
    </div>
  );
}