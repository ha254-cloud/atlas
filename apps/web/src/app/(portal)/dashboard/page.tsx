"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Banknote, AlertCircle, ClipboardCheck, Clock,
  ChevronRight, TrendingUp, Send, Eye, BadgeCheck,
  Ban, CircleDollarSign, Timer,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/common/page-container";
import { Card, CardContent } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { Skeleton } from "@/components/ui/skeleton";
import { ClaimsOverviewChart } from "@/features/dashboard/components/charts/claims-overview-chart";
import { dashboardService } from "@/services/dashboard-service";
import { workspaceService } from "@/services/workspace-service";
import { PriorityBadge } from "@/features/recovery/components/PriorityBadge";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";

export default function CommandCenterPage() {
  const { data: dash, isLoading: dashLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => dashboardService.getDashboard(),
  });

  const { data: workspace, isLoading: wsLoading } = useQuery({
    queryKey: ["recovery-workspace", { limit: 10 }],
    queryFn: () => workspaceService.getWorkspace({ limit: 10 }),
  });

  const { data: submissions, isLoading: submissionsLoading } = useQuery({
    queryKey: ["submission-summary"],
    queryFn: () => dashboardService.getSubmissionSummary(),
  });

  const m = dash?.metrics;
  const topCases = workspace?.cases.slice(0, 8) ?? [];

  return (
    <div className="flex flex-col h-full">
      <Header title="Recovery Command Center" />
      <div className="flex-1 overflow-y-auto">
        <PageContainer>

        {/* KPI row */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Recoverable Revenue"
            value={m ? formatCurrency(m.estimated_recovery) : "—"}
            detail={`${m ? formatNumber(m.recovery_opportunities) : "—"} open cases`}
            icon={Banknote}
            accent="teal"
            loading={dashLoading}
          />
          <MetricCard
            label="Claims Requiring Attention"
            value={m ? formatNumber(m.claims_requiring_attention) : "—"}
            detail="Denied or pending"
            icon={AlertCircle}
            accent="amber"
            loading={dashLoading}
          />
          <MetricCard
            label="Recommendation Accuracy"
            value={m ? `${m.ai_success_rate}%` : "—"}
            detail="Accepted recommendations"
            icon={ClipboardCheck}
            accent="violet"
            loading={dashLoading}
          />
          <MetricCard
            label="Appeals Pending"
            value={m ? formatNumber(m.appeals_pending) : "—"}
            detail="Awaiting payer response"
            icon={Clock}
            accent="blue"
            loading={dashLoading}
          />
        </div>

        <section>
          <div className="mb-3 flex items-end justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold">Recovery Pipeline</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">Approved appeals moving through payer review and payment</p>
            </div>
            <div className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex">
              <Timer className="h-3.5 w-3.5" />
              Average {submissions?.average_processing_time ?? "—"} days
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            {[
              { label: "Pending", value: submissions?.pending, icon: Clock, tone: "text-amber-700 bg-amber-50 ring-amber-100" },
              { label: "Submitted", value: submissions?.submitted, icon: Send, tone: "text-blue-700 bg-blue-50 ring-blue-100" },
              { label: "Waiting", value: submissions?.waiting, icon: Eye, tone: "text-indigo-700 bg-indigo-50 ring-indigo-100" },
              { label: "Denied", value: submissions?.denied, icon: Ban, tone: "text-rose-700 bg-rose-50 ring-rose-100" },
              { label: "Paid", value: submissions?.paid, icon: CircleDollarSign, tone: "text-emerald-700 bg-emerald-50 ring-emerald-100" },
              { label: "Avg. Processing", value: submissions?.average_processing_time, icon: BadgeCheck, tone: "text-slate-700 bg-slate-50 ring-slate-200", suffix: " days" },
            ].map(({ label, value, icon: Icon, tone, suffix }) => (
              <div key={label} className="flex min-h-24 items-center justify-between rounded-lg border bg-card px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-muted-foreground">{label}</p>
                  {submissionsLoading ? (
                    <Skeleton className="mt-2 h-6 w-12" />
                  ) : (
                    <p className="mt-1 text-xl font-bold">{value ?? "—"}{value != null ? suffix : ""}</p>
                  )}
                </div>
                <div className={cn("ml-3 rounded-md p-2 ring-1 ring-inset", tone)}>
                  <Icon className="h-4 w-4" strokeWidth={1.8} />
                </div>
              </div>
            ))}
          </div>

          <div className="mt-3 grid grid-cols-3 overflow-hidden rounded-lg border bg-card sm:grid-cols-5 lg:grid-cols-9">
            {[
              ["Pending", "pending"],
              ["Submitting", "submitting"],
              ["Submitted", "submitted"],
              ["Acknowledged", "acknowledged"],
              ["In review", "in_review"],
              ["Approved", "approved"],
              ["Denied", "denied"],
              ["Paid", "paid"],
              ["Failed", "failed"],
            ].map(([label, key], index) => (
              <div key={key} className={cn("border-b px-3 py-3 sm:border-b-0", index > 0 && "border-l")}>
                <p className="truncate text-[11px] text-muted-foreground">{label}</p>
                <p className="mt-0.5 text-sm font-semibold">{submissions?.recovery_pipeline[key] ?? 0}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Priority work queue */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-sm">Critical Recovery Opportunities</h2>
            <Link href="/recovery" className="text-xs text-primary hover:underline flex items-center gap-0.5">
              View all <ChevronRight className="h-3 w-3" />
            </Link>
          </div>

          <Card>
            <CardContent className="p-0">
              {wsLoading ? (
                <div className="p-4 space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 w-full" />
                  ))}
                </div>
              ) : topCases.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground">
                  <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted ring-1 ring-inset ring-border">
                    <TrendingUp className="h-5 w-5 text-muted-foreground/60" strokeWidth={1.75} />
                  </div>
                  <p className="text-sm">No open recovery opportunities. Import claims to get started.</p>
                </div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="border-b bg-muted/40">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Priority</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Claim</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Payer</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Patient</th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wide">Amount</th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wide">Confidence</th>
                      <th className="px-4 py-3" />
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {topCases.map((c) => (
                      <tr key={c.id} className="hover:bg-muted/30 transition-colors">
                        <td className="px-4 py-3">
                          <PriorityBadge priority={c.priority} />
                        </td>
                        <td className="px-4 py-3 font-mono font-medium text-xs">{c.claim_number}</td>
                        <td className="px-4 py-3 text-muted-foreground text-xs">{c.payer_name}</td>
                        <td className="px-4 py-3 text-muted-foreground text-xs">{c.patient_name}</td>
                        <td className="px-4 py-3 text-right font-semibold">{formatCurrency(c.estimated_recovery)}</td>
                        <td className="px-4 py-3 text-right text-muted-foreground text-xs">{c.confidence}%</td>
                        <td className="px-4 py-3 text-right">
                          <Link
                            href={`/claims/${c.claim_id}`}
                            className="inline-flex items-center gap-0.5 text-xs text-primary hover:underline font-medium"
                          >
                            Open <ChevronRight className="h-3 w-3" />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Trend chart */}
        <ClaimsOverviewChart data={dash?.recovery_trend} />
        </PageContainer>
      </div>
    </div>
  );
}
