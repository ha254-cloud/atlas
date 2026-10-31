"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertCircle, Banknote, CalendarClock, CircleDollarSign, Gauge, Landmark, Scale, ShieldAlert, WalletCards } from "lucide-react";
import { PageContainer } from "@/components/common/page-container";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { dashboardService } from "@/services/dashboard-service";
import { formatCurrency, formatNumber } from "@/lib/utils";

export default function AnalyticsPage() {
  const query = useQuery({
    queryKey: ["finance-overview"],
    queryFn: dashboardService.getFinanceOverview,
  });
  const data = query.data;
  const denialChart = data?.denial_leakage.map((item) => ({
    ...item,
    label: item.denial_type.replaceAll("_", " "),
  })) ?? [];

  return (
    <div className="flex h-full flex-col"><Header title="Finance Intelligence" /><div className="flex-1 overflow-y-auto"><PageContainer width="standard">
      {query.isLoading ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div>
      : query.isError || !data ? <div className="flex h-64 items-center justify-center text-sm text-destructive"><AlertCircle className="mr-2 h-4 w-4" />Finance intelligence could not be loaded.</div>
      : <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard label="Today's Collections" value={formatCurrency(data.executive.todays_collections)} detail="Posted payment records" icon={CircleDollarSign} />
          <MetricCard label="Outstanding Claims" value={formatCurrency(data.executive.outstanding_claims)} detail={`${data.executive.collection_rate_pct}% collection rate`} icon={WalletCards} />
          <MetricCard label="Recoverable" value={formatCurrency(data.executive.recoverable_revenue)} detail="Open scored opportunities" icon={Gauge} />
          <MetricCard label="Atlas Recoveries" value={formatCurrency(data.executive.atlas_attributed_recoveries)} detail="Attributed payment events" icon={Landmark} />
          <MetricCard label="Unclassified Leakage" value={formatCurrency(data.executive.unclassified_leakage)} detail="Outstanding, not classified as lost" icon={ShieldAlert} />
        </div>
        <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
          <Card><CardHeader><CardTitle className="text-base">Hospital revenue health</CardTitle></CardHeader><CardContent>
            <div className="flex items-end justify-between border-b pb-5"><div><p className="text-4xl font-bold">{data.executive.hospital_revenue_health_pct}%</p><p className="mt-1 text-xs text-muted-foreground">Composite operating indicator</p></div><Scale className="h-8 w-8 text-emerald-600" /></div>
            <div className="grid grid-cols-3 gap-3 pt-5 text-center"><div><p className="text-lg font-semibold">{data.executive.collection_rate_pct}%</p><p className="text-xs text-muted-foreground">Collection</p></div><div><p className="text-lg font-semibold">{data.executive.denial_rate_pct}%</p><p className="text-xs text-muted-foreground">Denial</p></div><div><p className="text-lg font-semibold">{data.executive.average_payment_days}</p><p className="text-xs text-muted-foreground">Payment days</p></div></div>
          </CardContent></Card>
          <Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><CalendarClock className="h-4 w-4" />Expected collections through {new Date(data.forecast.through_date).toLocaleDateString("en-KE", { day: "numeric", month: "short" })}</CardTitle></CardHeader><CardContent>
            <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end"><div><p className="text-3xl font-bold">{formatCurrency(data.forecast.expected_collections)}</p><p className="mt-1 text-sm text-muted-foreground">{data.forecast.confidence_pct}% average recovery confidence across {formatNumber(data.forecast.case_count)} cases</p></div><div className="max-w-md text-xs leading-5 text-muted-foreground">{data.forecast.assumptions[1]}</div></div>
          </CardContent></Card>
        </div>
        <Card><CardHeader><CardTitle className="text-base">Payer cash flow</CardTitle></CardHeader><CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>Payer</TableHead><TableHead className="text-right">Claims</TableHead><TableHead className="text-right">Outstanding</TableHead><TableHead className="text-right">Recovered</TableHead><TableHead className="text-right">Avg. payment</TableHead><TableHead className="text-right">Denial rate</TableHead></TableRow></TableHeader><TableBody>
          {data.payers.length ? data.payers.map((payer) => <TableRow key={payer.payer_id}><TableCell className="font-medium">{payer.payer}</TableCell><TableCell className="text-right">{formatNumber(payer.claim_count)}</TableCell><TableCell className="text-right">{formatCurrency(payer.outstanding_amount)}</TableCell><TableCell className="text-right">{formatCurrency(payer.recovered_amount)}</TableCell><TableCell className="text-right">{payer.average_payment_days} days</TableCell><TableCell className="text-right">{payer.denial_rate_pct}%</TableCell></TableRow>) : <TableRow><TableCell colSpan={6} className="h-28 text-center text-muted-foreground">Payer metrics will appear as claim and payment records accumulate.</TableCell></TableRow>}
        </TableBody></Table></CardContent></Card>
        <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
          <Card><CardHeader><CardTitle className="text-base">Denial leakage</CardTitle></CardHeader><CardContent className="h-72">
            {denialChart.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={denialChart} layout="vertical" margin={{ left: 16, right: 16 }}><CartesianGrid horizontal={false} strokeDasharray="3 3" className="stroke-border" /><XAxis type="number" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} tickFormatter={(value: number) => `KSh ${Math.round(value / 1000)}k`} /><YAxis dataKey="label" type="category" width={130} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} /><Tooltip formatter={(value) => formatCurrency(Number(value))} contentStyle={{ borderRadius: 6, border: "1px solid hsl(var(--border))" }} /><Bar dataKey="outstanding_amount" name="Outstanding" fill="#dc6b2f" radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer> : <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No denial leakage has been classified.</div>}
          </CardContent></Card>
          <Card><CardHeader><CardTitle className="text-base">Payment reconciliation</CardTitle></CardHeader><CardContent className="space-y-4">
            <div className="flex items-center justify-between border-b pb-3"><span className="text-sm text-muted-foreground">Matched payments</span><span className="font-semibold">{formatNumber(data.reconciliation.matched_payment_count)}</span></div>
            <div className="flex items-center justify-between border-b pb-3"><span className="text-sm text-muted-foreground">Matched amount</span><span className="font-semibold">{formatCurrency(data.reconciliation.matched_payment_amount)}</span></div>
            <div className="flex items-center justify-between border-b pb-3"><span className="text-sm text-muted-foreground">Unmatched payments</span><span className={data.reconciliation.unmatched_payment_count ? "font-semibold text-amber-700" : "font-semibold"}>{formatNumber(data.reconciliation.unmatched_payment_count)}</span></div>
            <div className="flex items-center justify-between"><span className="text-sm text-muted-foreground">Overpaid claims</span><span className={data.reconciliation.overpaid_claim_count ? "font-semibold text-amber-700" : "font-semibold"}>{formatNumber(data.reconciliation.overpaid_claim_count)}</span></div>
          </CardContent></Card>
        </div>
        <div className="grid gap-4 sm:grid-cols-3"><MetricCard label="Potential Revenue" value={formatCurrency(data.executive.potential_revenue)} detail="Total submitted claim value" icon={Banknote} /><MetricCard label="Collected Revenue" value={formatCurrency(data.executive.collected_revenue)} detail="Cumulative claim payments" icon={Landmark} /><MetricCard label="Payment Currencies" value={data.reconciliation.currencies.join(", ") || data.executive.currency} detail="Currencies remain separately reconciled" icon={WalletCards} /></div>
      </div>}
    </PageContainer></div></div>
  );
}
