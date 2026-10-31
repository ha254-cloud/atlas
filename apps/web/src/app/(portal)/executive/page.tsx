"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertCircle,
  BadgeDollarSign,
  Banknote,
  CalendarClock,
  CircleGauge,
  HandCoins,
  Landmark,
  ReceiptText,
  TrendingUp,
  WalletCards,
} from "lucide-react";
import { PageContainer } from "@/components/common/page-container";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { recoveryService } from "@/services/recovery-service";

function money(value: string | number) {
  return formatCurrency(Number(value));
}

export default function ExecutiveCommandCenterPage() {
  const portfolioQuery = useQuery({
    queryKey: ["recovery-lifecycle-portfolio"],
    queryFn: recoveryService.getPortfolio,
  });
  const forecastQuery = useQuery({
    queryKey: ["recovery-lifecycle-forecast", 90],
    queryFn: () => recoveryService.getForecast(90),
  });
  const portfolio = portfolioQuery.data;
  const forecast = forecastQuery.data;
  const loading = portfolioQuery.isLoading || forecastQuery.isLoading;
  const failed = portfolioQuery.isError || forecastQuery.isError || !portfolio || !forecast;
  const bands = portfolio
    ? [
        { label: "High", value: Number(portfolio.high_probability_amount), color: "bg-emerald-600" },
        { label: "Medium", value: Number(portfolio.medium_probability_amount), color: "bg-amber-500" },
        { label: "Low", value: Number(portfolio.low_probability_amount), color: "bg-zinc-400" },
      ]
    : [];
  const bandTotal = bands.reduce((total, band) => total + band.value, 0);
  const forecastData = forecast?.buckets.map((bucket) => ({
    date: new Date(bucket.start_date).toLocaleDateString("en-KE", { day: "numeric", month: "short" }),
    expected: Number(bucket.expected_amount),
  })) ?? [];

  return (
    <div className="flex h-full flex-col">
      <Header title="Executive Command Center" />
      <div className="flex-1 overflow-y-auto">
        <PageContainer width="standard">
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, index) => <Skeleton key={index} className="h-28" />)}
          </div>
        ) : failed ? (
          <div className="flex h-64 items-center justify-center text-sm text-destructive">
            <AlertCircle className="mr-2 h-4 w-4" />Executive recovery metrics could not be loaded.
          </div>
        ) : (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Net Revenue Collected" value={money(portfolio.recovered_amount)} detail="Verified cash across lifecycle accounts" icon={Landmark} />
              <MetricCard label="Outstanding" value={money(portfolio.outstanding_amount)} detail={`${formatNumber(portfolio.account_count)} financial positions`} icon={WalletCards} />
              <MetricCard label="Expected Recovery" value={money(portfolio.expected_recovery_amount)} detail={`${forecast.expected_collection_days} expected collection days`} icon={HandCoins} />
              <MetricCard label="Forecast Confidence" value={`${Number(forecast.confidence_pct).toFixed(1)}%`} detail="Payer timing evidence coverage" icon={CircleGauge} />
            </div>

            <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
              <Card>
                <CardHeader><CardTitle className="text-base">Recoverable Revenue Index</CardTitle></CardHeader>
                <CardContent>
                  <div className="flex items-end justify-between border-b pb-5">
                    <div>
                      <p className="text-5xl font-bold tabular-nums">{Number(portfolio.recoverable_revenue_index_pct).toFixed(1)}%</p>
                      <p className="mt-2 text-sm text-muted-foreground">Expected recovery as a share of outstanding revenue</p>
                    </div>
                    <TrendingUp className="h-9 w-9 text-emerald-600" />
                  </div>
                  <div className="grid gap-4 pt-5 sm:grid-cols-2">
                    <div><p className="text-lg font-semibold">{money(portfolio.recoverable_amount)}</p><p className="text-xs text-muted-foreground">Recoverable</p></div>
                    <div><p className="text-lg font-semibold">{money(portfolio.original_amount)}</p><p className="text-xs text-muted-foreground">Original billed</p></div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="text-base">Recovery portfolio</CardTitle></CardHeader>
                <CardContent className="space-y-5">
                  <div className="flex h-4 w-full overflow-hidden rounded-sm bg-muted" aria-label="Recovery probability distribution">
                    {bands.map((band) => (
                      <div key={band.label} className={band.color} style={{ width: bandTotal ? `${(band.value / bandTotal) * 100}%` : "0%" }} />
                    ))}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    {bands.map((band) => (
                      <div key={band.label} className="border-l-2 pl-3">
                        <div className="flex items-center gap-2"><span className={`h-2 w-2 rounded-sm ${band.color}`} /><span className="text-xs font-medium uppercase text-muted-foreground">{band.label}</span></div>
                        <p className="mt-1 text-lg font-semibold">{money(band.value)}</p>
                      </div>
                    ))}
                  </div>
                  {!bandTotal && <p className="text-sm text-muted-foreground">Probability bands will appear as recovery accounts are scored.</p>}
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><CalendarClock className="h-4 w-4" />Expected cash flow</CardTitle></CardHeader>
              <CardContent className="h-72">
                {forecastData.length ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={forecastData} margin={{ left: 8, right: 12, top: 8 }}>
                      <defs><linearGradient id="cashFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#168064" stopOpacity={0.3} /><stop offset="100%" stopColor="#168064" stopOpacity={0.02} /></linearGradient></defs>
                      <CartesianGrid vertical={false} strokeDasharray="3 3" className="stroke-border" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(value: number) => `KSh ${Math.round(value / 1000)}k`} />
                      <Tooltip formatter={(value) => money(Number(value))} contentStyle={{ borderRadius: 6, border: "1px solid hsl(var(--border))" }} />
                      <Area type="monotone" dataKey="expected" name="Expected collection" stroke="#168064" strokeWidth={2} fill="url(#cashFill)" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : <div className="flex h-full items-center justify-center text-sm text-muted-foreground">Cash timing will appear when scored accounts have expected recoveries.</div>}
              </CardContent>
            </Card>

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Atlas Recoveries" value={money(portfolio.atlas_recoveries)} detail="Verified attributed cash" icon={Banknote} />
              <MetricCard label="Atlas Fees" value={money(portfolio.atlas_fees)} detail="Snapshotted fee terms" icon={ReceiptText} />
              <MetricCard label="Return on Investment" value={portfolio.return_on_investment_pct === null ? "Not available" : `${Number(portfolio.return_on_investment_pct).toFixed(1)}%`} detail="Net verified recovery divided by Atlas fees" icon={BadgeDollarSign} />
              <MetricCard label="Remaining at Risk" value={money(Math.max(Number(portfolio.outstanding_amount) - Number(portfolio.recoverable_amount), 0))} detail="Outstanding beyond current expected recovery" icon={WalletCards} />
            </div>
          </div>
        )}
        </PageContainer>
      </div>
    </div>
  );
}
