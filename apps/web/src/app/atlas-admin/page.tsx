"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Banknote,
  BrainCircuit,
  Building2,
  CheckCircle2,
  CircleDollarSign,
  DatabaseZap,
  Gauge,
  HeartPulse,
  RefreshCw,
  ServerCog,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  platformAdminService,
  type MoneyTotal,
  type PlatformAdminSummary,
} from "@/services/platform-admin-service";

type View = "ceo" | "operations" | "platform";

const views: Array<{ id: View; label: string }> = [
  { id: "ceo", label: "CEO / Founder" },
  { id: "operations", label: "Operations" },
  { id: "platform", label: "Platform" },
];

function formatMoney(total: MoneyTotal) {
  return new Intl.NumberFormat("en-KE", {
    style: "currency",
    currency: total.currency,
    maximumFractionDigits: 0,
  }).format(Number(total.amount));
}

function MoneyStack({ totals, empty = "No recorded value" }: { totals: MoneyTotal[]; empty?: string }) {
  if (!totals.length) return <span className="text-base font-medium text-[#767b78]">{empty}</span>;
  return (
    <span className="flex flex-col gap-0.5">
      {totals.map((total) => <span key={total.currency}>{formatMoney(total)}</span>)}
    </span>
  );
}

function Metric({
  label,
  value,
  detail,
  icon: Icon,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  detail: string;
  icon: React.ElementType;
  accent: string;
}) {
  return (
    <div className="min-h-36 border border-[#d8d8d2] bg-white p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase text-[#5f6561]">{label}</p>
          <div className="mt-2 break-words text-2xl font-semibold tabular-nums">{value}</div>
          <p className="mt-2 text-xs text-[#767b78]">{detail}</p>
        </div>
        <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center", accent)}><Icon className="h-4 w-4" /></div>
      </div>
    </div>
  );
}

function ExecutiveView({ summary }: { summary: PlatformAdminSummary }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Hospital customers" value={summary.customers.total} detail={`${summary.customers.active} active · ${summary.customers.trial} trial`} icon={Building2} accent="bg-[#d8ff54]" />
        <Metric label="Claims processed" value={summary.platform.claims_processed.toLocaleString()} detail={`${summary.platform.claims_today.toLocaleString()} recorded today`} icon={Activity} accent="bg-[#bce8ff]" />
        <Metric label="Verified recovery" value={<MoneyStack totals={summary.platform.verified_recovery} />} detail="Recovered value verified in hospital ledgers" icon={Banknote} accent="bg-[#ffd9b8]" />
        <Metric label="Atlas fees earned" value={<MoneyStack totals={summary.platform.atlas_fees_earned} />} detail="Success fees from verified recoveries" icon={CircleDollarSign} accent="bg-[#e4d9ff]" />
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
        <section className="border border-[#d8d8d2] bg-white">
          <div className="flex items-center justify-between border-b border-[#e4e4de] px-5 py-4">
            <div><h2 className="font-semibold">Atlas revenue position</h2><p className="text-xs text-[#767b78]">Invoice-backed company revenue, kept separate by currency</p></div>
            <Gauge className="h-5 w-5 text-[#686d6a]" />
          </div>
          <div className="grid divide-y divide-[#e4e4de] sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {[
              ["Paid", summary.atlas_revenue.paid_invoices],
              ["Outstanding", summary.atlas_revenue.outstanding_invoices],
              ["Overdue", summary.atlas_revenue.overdue_invoices],
            ].map(([label, totals]) => (
              <div className="p-5" key={label as string}>
                <p className="text-xs uppercase text-[#767b78]">{label as string}</p>
                <div className="mt-2 text-xl font-semibold tabular-nums"><MoneyStack totals={totals as MoneyTotal[]} /></div>
              </div>
            ))}
          </div>
        </section>
        <section className="border border-[#d8d8d2] bg-white p-5">
          <div className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-[#9b5d00]" /><h2 className="font-semibold">Attention required</h2></div>
          <div className="mt-4 space-y-3">
            {summary.alerts.length ? summary.alerts.slice(0, 4).map((alert, index) => (
              <div className="border-l-2 border-[#d49a31] pl-3 text-sm text-[#5f6561]" key={`${alert.message}-${index}`}>{alert.message}</div>
            )) : <div className="flex items-center gap-2 text-sm text-[#5f6561]"><CheckCircle2 className="h-4 w-4 text-[#4d7c0f]" />No aggregate platform alerts.</div>}
          </div>
        </section>
      </div>
    </div>
  );
}

function OperationsView({ summary }: { summary: PlatformAdminSummary }) {
  const hospitals = useQuery({ queryKey: ["platform-admin", "hospitals"], queryFn: platformAdminService.getHospitals });
  const statusLabel = (status: string) => status.replaceAll("_", " ");
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <Metric label="Active hospitals" value={summary.customers.active} detail="Organizations currently enabled" icon={HeartPulse} accent="bg-[#d8ff54]" />
        <Metric label="Suspended" value={summary.customers.suspended} detail="Organizations requiring review" icon={Users} accent="bg-[#ffd9b8]" />
        <Metric label="Integration errors" value={summary.integration_errors} detail="Current connector records in error" icon={DatabaseZap} accent="bg-[#ffcbc5]" />
      </div>
      <section className="overflow-hidden border border-[#d8d8d2] bg-white">
        <div className="border-b border-[#e4e4de] px-5 py-4"><h2 className="font-semibold">Customer operations</h2><p className="text-xs text-[#767b78]">Commercial and aggregate activity only; no patient or claim detail</p></div>
        {hospitals.isLoading ? <div className="space-y-2 p-5"><Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" /></div> : hospitals.isError ? <p className="p-5 text-sm text-red-700">Hospital operations could not be loaded.</p> : (
          <>
          <div className="divide-y divide-[#e8e8e2] md:hidden">
            {hospitals.data?.map((hospital) => (
              <div className="space-y-3 p-4" key={hospital.id}>
                <div className="flex items-start justify-between gap-3">
                  <div><p className="font-medium">{hospital.name}</p><p className="mt-0.5 text-xs capitalize text-[#767b78]">{hospital.subscription_plan} plan</p></div>
                  <span className={cn("inline-flex px-2 py-1 text-xs font-medium capitalize", hospital.status === "active" ? "bg-[#e9f8cb] text-[#365200]" : "bg-[#f3e4df] text-[#7a2d21]")}>{statusLabel(hospital.status)}</span>
                </div>
                <div className="grid grid-cols-2 gap-3 border-t border-[#eeeeea] pt-3 text-xs">
                  <div><p className="text-[#767b78]">Claims</p><p className="mt-1 font-semibold tabular-nums">{hospital.claim_count.toLocaleString()}</p></div>
                  <div className="text-right"><p className="text-[#767b78]">Atlas revenue</p><p className="mt-1 font-semibold tabular-nums"><MoneyStack totals={hospital.atlas_revenue} /></p></div>
                </div>
              </div>
            ))}
          </div>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="bg-[#f6f6f2] text-[11px] uppercase text-[#686d6a]"><tr><th className="px-5 py-3">Hospital</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Plan</th><th className="px-4 py-3 text-right">Claims</th><th className="px-5 py-3 text-right">Atlas revenue</th></tr></thead>
              <tbody className="divide-y divide-[#e8e8e2]">
                {hospitals.data?.map((hospital) => <tr className="hover:bg-[#fafaf7]" key={hospital.id}><td className="px-5 py-4 font-medium">{hospital.name}</td><td className="px-4 py-4"><span className={cn("inline-flex px-2 py-1 text-xs font-medium capitalize", hospital.status === "active" ? "bg-[#e9f8cb] text-[#365200]" : "bg-[#f3e4df] text-[#7a2d21]")}>{statusLabel(hospital.status)}</span></td><td className="px-4 py-4 capitalize text-[#686d6a]">{hospital.subscription_plan}</td><td className="px-4 py-4 text-right tabular-nums">{hospital.claim_count.toLocaleString()}</td><td className="px-5 py-4 text-right font-medium tabular-nums"><MoneyStack totals={hospital.atlas_revenue} /></td></tr>)}
              </tbody>
            </table>
          </div>
          </>
        )}
      </section>
    </div>
  );
}

function PlatformView({ summary }: { summary: PlatformAdminSummary }) {
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="AI requests today" value={summary.ai_operations.requests_today.toLocaleString()} detail={`${summary.ai_operations.tokens_today.toLocaleString()} tokens`} icon={BrainCircuit} accent="bg-[#e4d9ff]" />
        <Metric label="AI cost today" value={new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 4 }).format(Number(summary.ai_operations.estimated_cost_usd_today))} detail="Persisted provider cost estimates" icon={CircleDollarSign} accent="bg-[#d8ff54]" />
        <Metric label="AI latency" value={summary.ai_operations.average_latency_ms_today === null ? "Unavailable" : `${Math.round(summary.ai_operations.average_latency_ms_today)} ms`} detail="Average completed call latency today" icon={Activity} accent="bg-[#bce8ff]" />
        <Metric label="Integration errors" value={summary.integration_errors} detail="Connector records requiring attention" icon={ServerCog} accent="bg-[#ffcbc5]" />
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        <section className="border border-[#d8d8d2] bg-white p-5"><h2 className="font-semibold">Infrastructure signals</h2><div className="mt-4 divide-y divide-[#e8e8e2]">{Object.entries(summary.system_health).map(([service, state]) => <div className="flex items-center justify-between py-3" key={service}><span className="capitalize">{service.replaceAll("_", " ")}</span><span className="flex items-center gap-2 text-xs capitalize text-[#686d6a]"><span className={cn("h-2 w-2", state === "healthy" ? "bg-[#65a30d]" : "bg-[#a4a7a5]")} />{state.replaceAll("_", " ")}</span></div>)}</div></section>
        <section className="border border-[#d8d8d2] bg-white p-5"><h2 className="font-semibold">Data readiness</h2><p className="mt-1 text-xs text-[#767b78]">Metrics remain unavailable until an authoritative source is integrated.</p><div className="mt-4 space-y-2">{summary.unavailable_metrics.map((metric) => <div className="flex items-center gap-3 bg-[#f6f6f2] px-3 py-2.5 text-sm" key={metric}><span className="h-2 w-2 shrink-0 bg-[#a4a7a5]" />{metric}</div>)}</div></section>
      </div>
    </div>
  );
}

export default function AtlasAdminPage() {
  const [view, setView] = useState<View>("ceo");
  const summary = useQuery({ queryKey: ["platform-admin", "summary"], queryFn: platformAdminService.getSummary });
  const updatedAt = summary.dataUpdatedAt
    ? new Date(summary.dataUpdatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : null;

  return (
    <div className="min-h-screen">
      <header className="border-b border-[#d8d8d2] bg-white px-4 py-5 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-[1600px]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div><p className="text-[11px] font-semibold uppercase text-[#67706b]">Atlas company operations</p><h1 className="mt-1 text-2xl font-semibold sm:text-3xl">Platform command center</h1><p className="mt-1 text-sm text-[#686d6a]">Company performance, customer operations, and platform signals.</p></div>
            <div className="flex items-center justify-between gap-3 lg:justify-end">
              {updatedAt && <p className="text-xs text-[#767b78]">Updated {updatedAt}</p>}
              <Button variant="outline" size="sm" className="h-8 bg-white" onClick={() => void summary.refetch()} disabled={summary.isFetching}>
                <RefreshCw className={cn("mr-2 h-3.5 w-3.5", summary.isFetching && "animate-spin")} />Refresh
              </Button>
            </div>
          </div>
          <div className="mt-5 grid w-full grid-cols-3 border border-[#cfcfc8] bg-[#f6f6f2] p-1 sm:w-fit" role="tablist" aria-label="Command center view">
            {views.map((item) => <button className={cn("min-w-0 px-3 py-2 text-xs font-medium transition-colors sm:min-w-28", view === item.id ? "bg-[#151918] text-white" : "text-[#686d6a] hover:bg-white")} key={item.id} onClick={() => setView(item.id)} role="tab" aria-selected={view === item.id}>{item.label}</button>)}
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-[1600px] p-4 sm:p-6 lg:p-8">
        {summary.isLoading ? <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 8 }).map((_, index) => <Skeleton className="h-32" key={index} />)}</div> : summary.isError || !summary.data ? <div className="flex min-h-72 flex-col items-center justify-center border border-[#d8d8d2] bg-white text-center"><AlertTriangle className="h-7 w-7 text-[#b24a36]" /><p className="mt-3 font-medium">Platform aggregates could not be loaded.</p><Button variant="outline" className="mt-4" onClick={() => void summary.refetch()}><RefreshCw className="mr-2 h-4 w-4" />Retry</Button></div> : view === "ceo" ? <ExecutiveView summary={summary.data} /> : view === "operations" ? <OperationsView summary={summary.data} /> : <PlatformView summary={summary.data} />}
      </div>
    </div>
  );
}