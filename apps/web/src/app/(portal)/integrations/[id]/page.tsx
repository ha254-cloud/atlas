"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CheckCircle2,
  CircleAlert,
  Clock3,
  FileJson2,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getErrorMessage } from "@/lib/api-client";
import { cn, formatDate, formatNumber } from "@/lib/utils";
import { integrationsService, type MappingProfileCreateInput } from "@/services/integrations-service";
import type { IntegrationMappingField, IntegrationSyncRun } from "@/types/integration";

const TARGET_FIELDS = [
  "claim_number",
  "medical_record_number",
  "patient_first_name",
  "patient_last_name",
  "payer_code",
  "billed_amount",
  "paid_amount",
  "service_date",
  "diagnosis_codes",
  "procedure_codes",
  "status",
  "denial_code",
  "denial_reason",
  "authorization_number",
  "authorization_expiration",
];

const REQUIRED = new Set(["claim_number", "payer_code", "billed_amount", "service_date"]);
const INITIAL_FIELDS: Omit<IntegrationMappingField, "id">[] = [
  { source_field: "", target_field: "claim_number", transform: null, required: true, default_value: null },
  { source_field: "", target_field: "payer_code", transform: null, required: true, default_value: null },
  { source_field: "", target_field: "billed_amount", transform: { type: "decimal", currency_symbols: ["KES", "KSh", ","] }, required: true, default_value: null },
  { source_field: "", target_field: "service_date", transform: { type: "date", input_format: "%d/%m/%y" }, required: true, default_value: null },
  { source_field: "", target_field: "medical_record_number", transform: null, required: false, default_value: null },
];

function transformName(transform: Record<string, unknown> | null) {
  if (!transform) return "none";
  if (transform.type === "decimal") return "kes";
  if (transform.type === "date") return "date";
  if (transform.type === "text" && transform.case === "upper") return "upper";
  if (transform.type === "split") return "split";
  return "none";
}

function transformValue(value: string): Record<string, unknown> | null {
  if (value === "kes") return { type: "decimal", currency_symbols: ["KES", "KSh", ","] };
  if (value === "date") return { type: "date", input_format: "%d/%m/%y" };
  if (value === "upper") return { type: "text", case: "upper" };
  if (value === "split") return { type: "split", delimiter: "," };
  return null;
}

function RunStatus({ run }: { run: IntegrationSyncRun }) {
  const variants = {
    success: "success",
    partial: "warning",
    failed: "destructive",
    running: "secondary",
  } as const;
  return <Badge variant={variants[run.status]}>{run.status}</Badge>;
}

export default function IntegrationWorkspacePage() {
  const params = useParams<{ id: string }>();
  const integrationId = Number(params.id);
  const queryClient = useQueryClient();
  const [name, setName] = useState("Hospital claims export");
  const [sourceFormat, setSourceFormat] = useState<MappingProfileCreateInput["source_format"]>("csv");
  const [reason, setReason] = useState("Initial hospital onboarding mapping");
  const [fields, setFields] = useState(INITIAL_FIELDS);
  const [sample, setSample] = useState('{\n  "ClaimNo": "CLM-1001",\n  "Payer": "SHA",\n  "Amount": "KES 20,000",\n  "ServiceDate": "10/08/26"\n}');
  const [selectedRun, setSelectedRun] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const integration = useQuery({ queryKey: ["integration", integrationId], queryFn: () => integrationsService.get(integrationId) });
  const mappings = useQuery({ queryKey: ["integration-mappings", integrationId], queryFn: () => integrationsService.mappings(integrationId) });
  const runs = useQuery({ queryKey: ["integration-runs", integrationId], queryFn: () => integrationsService.runs(integrationId), refetchInterval: 10000 });
  const errors = useQuery({ queryKey: ["integration-run-errors", integrationId, selectedRun], queryFn: () => integrationsService.runErrors(integrationId, selectedRun!), enabled: selectedRun !== null });

  const createMapping = useMutation({
    mutationFn: () => integrationsService.createMapping(integrationId, { name, source_format: sourceFormat, reason, fields }),
    onSuccess: (profile) => {
      setMessage(`Mapping version ${profile.version} saved.`);
      void queryClient.invalidateQueries({ queryKey: ["integration-mappings", integrationId] });
    },
    onError: (error) => setMessage(getErrorMessage(error, "Mapping could not be saved.")),
  });
  const preview = useMutation({
    mutationFn: () => integrationsService.previewMapping(integrationId, mappings.data![0].id, JSON.parse(sample) as Record<string, unknown>),
    onError: (error) => setMessage(getErrorMessage(error, "Sample row is not valid JSON.")),
  });
  const sync = useMutation({
    mutationFn: () => integrationsService.sync(integrationId),
    onSuccess: () => {
      setMessage("Sync queued. History will update when the worker starts.");
      void queryClient.invalidateQueries({ queryKey: ["integration-runs", integrationId] });
    },
    onError: (error) => setMessage(getErrorMessage(error, "Sync could not be queued.")),
  });

  function updateField(index: number, update: Partial<Omit<IntegrationMappingField, "id">>) {
    setFields((current) => current.map((field, fieldIndex) => fieldIndex === index ? { ...field, ...update } : field));
  }

  const latestMapping = mappings.data?.[0];

  return (
    <div className="flex h-full flex-col">
      <Header title="Integration Setup" />
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-7xl space-y-8">
          <section className="border-b pb-5">
            <Button variant="ghost" size="sm" asChild className="mb-3 -ml-2"><Link href="/integrations"><ArrowLeft className="h-4 w-4" />Connections</Link></Button>
            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
              <div><p className="text-xs font-medium uppercase text-muted-foreground">Hospital data source</p><h2 className="mt-1 text-2xl font-semibold capitalize">{integration.data?.provider.replaceAll("_", " ") ?? "Integration"}</h2><p className="mt-1 text-sm text-muted-foreground">Configure canonical claim mapping, test a sample record, and review every sync.</p></div>
              <Button onClick={() => sync.mutate()} disabled={sync.isPending || integration.data?.status === "disconnected"}>{sync.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Sync now</Button>
            </div>
          </section>

          {message && <div className="border-l-2 border-blue-600 bg-blue-50 px-4 py-3 text-sm text-blue-950">{message}</div>}

          <section>
            <div className="mb-4 flex items-end justify-between"><div><h2 className="text-base font-semibold">Field mapping</h2><p className="mt-1 text-sm text-muted-foreground">Map the hospital export to Atlas canonical claim fields. Saving creates a new immutable version.</p></div>{latestMapping && <Badge variant="secondary">Version {latestMapping.version}</Badge>}</div>
            <div className="grid gap-3 border-y bg-muted/20 py-4 md:grid-cols-3">
              <label className="space-y-1 px-3 text-xs font-medium">Profile name<Input value={name} onChange={(event) => setName(event.target.value)} /></label>
              <label className="space-y-1 px-3 text-xs font-medium">Source format<select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={sourceFormat} onChange={(event) => setSourceFormat(event.target.value as MappingProfileCreateInput["source_format"])}><option value="csv">CSV</option><option value="excel">Excel</option><option value="json">JSON</option><option value="xml">XML</option><option value="rest">REST API</option></select></label>
              <label className="space-y-1 px-3 text-xs font-medium">Change reason<Input value={reason} onChange={(event) => setReason(event.target.value)} /></label>
            </div>
            <div className="mt-4 overflow-x-auto border">
              <table className="w-full min-w-[760px] text-sm"><thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground"><tr><th className="px-3 py-2.5">Hospital field</th><th className="px-3 py-2.5">Atlas field</th><th className="px-3 py-2.5">Transform</th><th className="w-16 px-3 py-2.5"></th></tr></thead><tbody className="divide-y">{fields.map((field, index) => <tr key={`${field.target_field}-${index}`}><td className="p-2"><Input value={field.source_field} onChange={(event) => updateField(index, { source_field: event.target.value })} placeholder="HospitalNo" /></td><td className="p-2"><select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={field.target_field} onChange={(event) => updateField(index, { target_field: event.target.value, required: REQUIRED.has(event.target.value) })}>{TARGET_FIELDS.map((target) => <option key={target} value={target}>{target.replaceAll("_", " ")}{REQUIRED.has(target) ? " *" : ""}</option>)}</select></td><td className="p-2"><select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={transformName(field.transform)} onChange={(event) => updateField(index, { transform: transformValue(event.target.value) })}><option value="none">Trim text</option><option value="kes">KES amount</option><option value="date">DD/MM/YY date</option><option value="upper">Uppercase</option><option value="split">Comma-separated list</option></select></td><td className="p-2 text-right"><Button size="icon" variant="ghost" title="Remove mapping" disabled={REQUIRED.has(field.target_field)} onClick={() => setFields((current) => current.filter((_, fieldIndex) => fieldIndex !== index))}><Trash2 className="h-4 w-4" /></Button></td></tr>)}</tbody></table>
            </div>
            <div className="mt-3 flex flex-wrap justify-between gap-2"><Button variant="outline" onClick={() => setFields((current) => [...current, { source_field: "", target_field: "patient_first_name", transform: null, required: false, default_value: null }])}><Plus className="h-4 w-4" />Add field</Button><Button onClick={() => createMapping.mutate()} disabled={createMapping.isPending || fields.some((field) => !field.source_field)}>{createMapping.isPending && <Loader2 className="h-4 w-4 animate-spin" />}Save new version</Button></div>
          </section>

          <section className="grid gap-6 lg:grid-cols-2">
            <div><div className="mb-3 flex items-center gap-2"><FileJson2 className="h-4 w-4 text-blue-700" /><h2 className="text-base font-semibold">Sample preview</h2></div><textarea value={sample} onChange={(event) => setSample(event.target.value)} className="min-h-56 w-full border bg-slate-950 p-3 font-mono text-xs text-slate-100" /><Button className="mt-3" variant="outline" onClick={() => preview.mutate()} disabled={!latestMapping || preview.isPending}>Test latest mapping</Button></div>
            <div><h2 className="mb-3 text-base font-semibold">Canonical result</h2><div className={cn("min-h-56 border p-4", preview.data?.valid === false ? "border-red-200 bg-red-50" : "bg-muted/20")}>{!preview.data ? <p className="text-sm text-muted-foreground">Save a mapping, then test one sample record.</p> : preview.data.valid ? <pre className="overflow-x-auto text-xs">{JSON.stringify(preview.data.mapped_record, null, 2)}</pre> : <div className="flex gap-3 text-sm text-red-800"><CircleAlert className="mt-0.5 h-4 w-4 shrink-0" /><div><p className="font-medium">{preview.data.error_code}</p><p className="mt-1">{preview.data.message}</p></div></div>}</div></div>
          </section>

          <section><div className="mb-4"><h2 className="text-base font-semibold">Sync history</h2><p className="mt-1 text-sm text-muted-foreground">Manual and scheduled runs, including record-level rejection totals.</p></div><div className="overflow-x-auto border"><table className="w-full min-w-[760px] text-sm"><thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground"><tr><th className="px-4 py-3">Started</th><th className="px-4 py-3">Trigger</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Received</th><th className="px-4 py-3 text-right">Imported</th><th className="px-4 py-3 text-right">Rejected</th></tr></thead><tbody className="divide-y">{runs.data?.map((run) => <tr key={run.id} className={cn(run.records_rejected > 0 && "cursor-pointer hover:bg-muted/30")} onClick={() => run.records_rejected > 0 && setSelectedRun(run.id)}><td className="px-4 py-3"><div className="flex items-center gap-2"><Clock3 className="h-3.5 w-3.5 text-muted-foreground" />{formatDate(run.started_at)}</div></td><td className="px-4 py-3 capitalize">{run.trigger}</td><td className="px-4 py-3"><RunStatus run={run} /></td><td className="px-4 py-3 text-right">{formatNumber(run.records_received)}</td><td className="px-4 py-3 text-right text-emerald-700">{formatNumber(run.records_imported)}</td><td className="px-4 py-3 text-right text-red-700">{formatNumber(run.records_rejected)}</td></tr>)}{!runs.data?.length && <tr><td colSpan={6} className="px-4 py-12 text-center text-muted-foreground"><CheckCircle2 className="mx-auto mb-2 h-5 w-5" />No sync runs recorded yet.</td></tr>}</tbody></table></div>{selectedRun && <div className="mt-4 border-l-2 border-red-500 pl-4"><h3 className="text-sm font-semibold">Rejected records</h3><div className="mt-2 space-y-2">{errors.data?.map((error) => <div key={error.id} className="text-sm"><span className="font-mono text-xs text-muted-foreground">Row {error.row_number ?? "—"}</span><span className="mx-2 text-muted-foreground">·</span><span className="font-medium">{error.error_code.replaceAll("_", " ")}</span><p className="mt-0.5 text-muted-foreground">{error.message}</p></div>)}</div></div>}</section>
        </div>
      </div>
    </div>
  );
}
