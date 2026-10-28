"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Cable, CircleAlert, Loader2, Plug, Power, RefreshCw, Settings2, Server } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/features/auth/context/auth-context";
import { getErrorMessage } from "@/lib/api-client";
import { cn, formatDate, formatNumber } from "@/lib/utils";
import { integrationsService } from "@/services/integrations-service";
import type { IntegrationStatus } from "@/types/integration";
import { SftpIntegrationForm } from "@/features/integrations/components/SftpIntegrationForm";

const STATUS: Record<IntegrationStatus, { label: string; variant: "success" | "warning" | "destructive" | "secondary" }> = {
  active: { label: "Active", variant: "success" }, pending: { label: "Pending setup", variant: "warning" },
  syncing: { label: "Syncing", variant: "warning" },
  disconnected: { label: "Disconnected", variant: "secondary" }, error: { label: "Attention needed", variant: "destructive" },
};

export default function IntegrationsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const canConfigure = user ? ["admin", "manager", "owner"].includes(user.role) : false;
  const integrations = useQuery({ queryKey: ["integrations"], queryFn: integrationsService.list });
  const providers = useQuery({ queryKey: ["integration-providers"], queryFn: integrationsService.providers });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["integrations"] });
  const create = useMutation({ mutationFn: (selectedProvider: string) => integrationsService.create(selectedProvider), onSuccess: () => { setProvider(""); setMessage("Integration added. Complete provider authorization before the first sync."); void refresh(); }, onError: (error) => setMessage(getErrorMessage(error, "Integration could not be added.")) });
  const sync = useMutation({ mutationFn: integrationsService.sync, onSuccess: () => setMessage("Sync queued. Status will update when the worker completes."), onError: (error) => setMessage(getErrorMessage(error, "Sync could not be queued.")) });
  const disconnect = useMutation({ mutationFn: integrationsService.disconnect, onSuccess: () => { setMessage("Integration disconnected."); void refresh(); }, onError: (error) => setMessage(getErrorMessage(error, "Integration could not be disconnected.")) });
  const configured = new Set(integrations.data?.map((item) => item.provider) ?? []);
  const available = providers.data?.filter((item) => !configured.has(item)) ?? [];

  return (
    <div className="flex h-full flex-col"><Header title="Integrations" /><div className="flex-1 overflow-y-auto p-4 sm:p-6"><div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-col justify-between gap-4 border-b pb-5 sm:flex-row sm:items-end"><div><h2 className="text-lg font-semibold">Connection health</h2><p className="mt-1 text-sm text-muted-foreground">Monitor claim imports and control configured data connections.</p></div>{canConfigure && <div className="flex gap-2"><select value={provider} onChange={(event) => setProvider(event.target.value)} className="h-10 min-w-48 rounded-md border bg-background px-3 text-sm"><option value="">Select provider</option>{available.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ").toUpperCase()}</option>)}</select>{provider !== "sftp" && <Button onClick={() => provider && create.mutate(provider)} disabled={!provider || create.isPending}>{create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plug className="h-4 w-4" />}Add</Button>}</div>}</div>
      {provider === "sftp" && <SftpIntegrationForm onCancel={() => setProvider("")} onCreated={() => { setProvider(""); setMessage("SFTP claim feed saved. Use Sync now to test the connection."); void refresh(); }} />}
      {message && <div className={cn("rounded-md border px-4 py-3 text-sm", message.includes("could not") ? "border-red-200 bg-red-50 text-red-800" : "border-blue-200 bg-blue-50 text-blue-900")}>{message}</div>}
      {integrations.isLoading ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-48" />)}</div> : integrations.isError ? <div className="py-20 text-center text-sm text-destructive"><CircleAlert className="mx-auto mb-2 h-6 w-6" />Integrations could not be loaded.</div> : integrations.data?.length ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{integrations.data.map((item) => {
        const state = STATUS[item.status];
        return <Card key={item.id}><CardContent className="p-5"><div className="flex items-start justify-between"><div className="flex items-center gap-3"><div className="rounded-md bg-blue-50 p-2.5 text-blue-700"><Server className="h-5 w-5" /></div><div><h3 className="font-semibold capitalize">{item.provider.replaceAll("_", " ")}</h3><p className="text-xs text-muted-foreground">Connected {formatDate(item.created_at)}</p></div></div><Badge variant={state.variant}>{state.label}</Badge></div><div className="my-5 grid grid-cols-2 gap-3 border-y py-4"><div><p className="text-xs text-muted-foreground">Claims imported</p><p className="mt-1 font-semibold">{formatNumber(item.claims_imported_count)}</p></div><div><p className="text-xs text-muted-foreground">Last sync</p><p className="mt-1 text-sm font-medium">{item.last_sync_at ? formatDate(item.last_sync_at) : "Never"}</p></div></div>{item.last_error && <p className="mb-4 line-clamp-2 text-xs text-destructive">{item.last_error}</p>}{canConfigure && <div className="flex flex-wrap gap-2"><Button variant="outline" size="sm" asChild><Link href={`/integrations/${item.id}`}><Settings2 className="h-3.5 w-3.5" />Configure</Link></Button>{item.status !== "disconnected" && <><Button variant="outline" size="sm" onClick={() => sync.mutate(item.id)} disabled={sync.isPending}><RefreshCw className="h-3.5 w-3.5" />Sync now</Button><Button variant="ghost" size="sm" className="text-destructive" onClick={() => disconnect.mutate(item.id)} disabled={disconnect.isPending}><Power className="h-3.5 w-3.5" />Disconnect</Button></>}</div>}</CardContent></Card>;
      })}</div> : <div className="flex min-h-72 flex-col items-center justify-center border-y text-center"><div className="mb-3 rounded-md bg-muted p-3 text-muted-foreground"><Cable className="h-6 w-6" /></div><h3 className="text-sm font-semibold">No integrations configured</h3><p className="mt-1 max-w-sm text-sm text-muted-foreground">Choose a provider to establish the connection record and begin authorization.</p></div>}
      <div className="grid gap-4 sm:grid-cols-3"><div className="flex items-center gap-3 border-t pt-4"><Activity className="h-4 w-4 text-emerald-600" /><div><p className="text-sm font-medium">{integrations.data?.filter((item) => item.status === "active").length ?? 0} active</p><p className="text-xs text-muted-foreground">Healthy connections</p></div></div><div className="flex items-center gap-3 border-t pt-4"><RefreshCw className="h-4 w-4 text-blue-600" /><div><p className="text-sm font-medium">{formatNumber(integrations.data?.reduce((sum, item) => sum + item.claims_imported_count, 0) ?? 0)} claims</p><p className="text-xs text-muted-foreground">Imported across providers</p></div></div><div className="flex items-center gap-3 border-t pt-4"><CircleAlert className="h-4 w-4 text-amber-600" /><div><p className="text-sm font-medium">{integrations.data?.filter((item) => item.status === "error").length ?? 0} need attention</p><p className="text-xs text-muted-foreground">Connection errors</p></div></div></div>
    </div></div></div>
  );
}
