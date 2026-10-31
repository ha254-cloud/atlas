"use client";

import Link from "next/link";
import { useDeferredValue, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, FileCheck2, FileText, Search } from "lucide-react";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { appealsService, type AppealListItem } from "@/services/appeals-service";
import { cn, formatCurrency, formatDate } from "@/lib/utils";

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  review: "In review",
  approved: "Approved",
  submitted: "Submitted",
  accepted: "Accepted",
  rejected: "Rejected",
  denied: "Denied",
  withdrawn: "Withdrawn",
  closed: "Closed",
};

const STATUS_STYLES: Record<string, string> = {
  draft: "border-slate-200 bg-slate-50 text-slate-700",
  review: "border-amber-200 bg-amber-50 text-amber-800",
  approved: "border-blue-200 bg-blue-50 text-blue-800",
  submitted: "border-indigo-200 bg-indigo-50 text-indigo-800",
  accepted: "border-emerald-200 bg-emerald-50 text-emerald-800",
  rejected: "border-red-200 bg-red-50 text-red-800",
  denied: "border-red-200 bg-red-50 text-red-800",
  withdrawn: "border-slate-200 bg-slate-50 text-slate-600",
  closed: "border-slate-200 bg-slate-50 text-slate-600",
};

function StatusBadge({ appeal }: { appeal: AppealListItem }) {
  const isUnverified = appeal.status === "submitted" && !appeal.confirmation_number;

  return (
    <span className={cn(
      "inline-flex rounded border px-2 py-0.5 text-xs font-medium",
      isUnverified
        ? "border-red-200 bg-red-50 text-red-800"
        : STATUS_STYLES[appeal.status] ?? STATUS_STYLES.draft,
    )}>
      {isUnverified
        ? "Unverified submission record"
        : STATUS_LABELS[appeal.status] ?? appeal.status.replace(/_/g, " ")}
    </span>
  );
}

function AppealRow({ appeal }: { appeal: AppealListItem }) {
  const quality = appeal.quality_score?.overall;

  return (
    <div className="grid gap-3 border-t px-4 py-3 first:border-t-0 hover:bg-muted/20 md:grid-cols-[minmax(170px,1.1fr)_minmax(180px,1.2fr)_115px_100px_120px_88px] md:items-center">
      <div className="min-w-0">
        <p className="truncate font-mono text-sm font-semibold">{appeal.claim_number}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {appeal.service_date ? formatDate(appeal.service_date) : "No service date"}
        </p>
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{appeal.payer_name}</p>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">{appeal.patient_name}</p>
      </div>
      <div><StatusBadge appeal={appeal} /></div>
      <div className="md:text-right">
        <p className="text-sm font-medium tabular-nums">{quality == null ? "Not scored" : `${quality}%`}</p>
        <p className="text-xs text-muted-foreground">Quality</p>
      </div>
      <div className="md:text-right">
        <p className="text-sm font-semibold tabular-nums">{formatCurrency(appeal.billed_amount)}</p>
        <p className="text-xs text-muted-foreground">Claim value</p>
      </div>
      <Link href={`/claims/detail?id=${appeal.claim_id}`} className="justify-self-start md:justify-self-end">
        <Button variant="ghost" size="sm" className="gap-1.5 text-xs">
          Open <ArrowRight className="h-3.5 w-3.5" />
        </Button>
      </Link>
    </div>
  );
}

export default function AppealsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const deferredSearch = useDeferredValue(search.trim().toLowerCase());

  const { data: appeals = [], isLoading, isError } = useQuery({
    queryKey: ["appeals"],
    queryFn: appealsService.list,
    staleTime: 30_000,
  });

  const visibleAppeals = appeals.filter((appeal) => {
    const matchesStatus = !status || appeal.status === status;
    const haystack = `${appeal.claim_number} ${appeal.payer_name} ${appeal.patient_name}`.toLowerCase();
    return matchesStatus && (!deferredSearch || haystack.includes(deferredSearch));
  });

  const needsReview = appeals.filter((appeal) => appeal.status === "draft" || appeal.status === "review").length;
  const approved = appeals.filter((appeal) => appeal.status === "approved").length;
  const submitted = appeals.filter((appeal) =>
    ["accepted", "denied", "closed"].includes(appeal.status)
    || (appeal.status === "submitted" && !!appeal.confirmation_number)
  ).length;

  return (
    <div className="flex flex-col h-full">
      <Header title="Appeals" />
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-6xl space-y-4">
          <section className="overflow-hidden rounded-lg border bg-card" aria-label="Appeal summary">
            <div className="grid divide-y sm:grid-cols-4 sm:divide-x sm:divide-y-0">
              {[
                { label: "Total appeals", value: appeals.length },
                { label: "Needs review", value: needsReview },
                { label: "Approved", value: approved },
                { label: "Submitted", value: submitted },
              ].map((metric) => (
                <div key={metric.label} className="flex items-center justify-between px-5 py-4 sm:block">
                  <p className="text-xs font-medium text-muted-foreground">{metric.label}</p>
                  <p className="mt-1 text-2xl font-semibold tabular-nums">{isLoading ? "—" : metric.value}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="overflow-hidden rounded-lg border bg-card" aria-label="Appeals queue">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <div>
                <h2 className="text-sm font-semibold">Appeals queue</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">Review, approve, and track payer submissions</p>
              </div>
              {!isLoading && <span className="text-xs tabular-nums text-muted-foreground">{visibleAppeals.length} results</span>}
            </div>

            <div className="flex flex-col gap-2 border-b bg-muted/20 p-3 sm:flex-row">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  aria-label="Search appeals"
                  placeholder="Search claim, payer, or patient"
                  className="h-9 bg-background pl-9"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </div>
              <select
                aria-label="Filter appeals by status"
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                className="h-9 min-w-40 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">All statuses</option>
                {Object.entries(STATUS_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>

            <div className="hidden grid-cols-[minmax(170px,1.1fr)_minmax(180px,1.2fr)_115px_100px_120px_88px] bg-muted/30 px-4 py-2 text-xs font-medium text-muted-foreground md:grid">
              <span>Claim</span><span>Payer / patient</span><span>Status</span>
              <span className="text-right">Quality</span><span className="text-right">Claim value</span><span className="sr-only">Action</span>
            </div>

            {isLoading ? (
              <div className="space-y-2 p-3">
                {Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-16 w-full rounded" />)}
              </div>
            ) : isError ? (
              <div className="flex items-center justify-center gap-2 py-16 text-sm text-destructive">
                <AlertCircle className="h-4 w-4" /> Unable to load appeals.
              </div>
            ) : visibleAppeals.length === 0 ? (
              <div className="flex flex-col items-center py-16 text-center text-muted-foreground">
                {appeals.length === 0 ? <FileCheck2 className="mb-3 h-9 w-9 opacity-30" /> : <FileText className="mb-3 h-9 w-9 opacity-30" />}
                <p className="text-sm font-medium text-foreground">{appeals.length === 0 ? "No appeals created" : "No matching appeals"}</p>
                <p className="mt-1 max-w-sm text-xs">
                  {appeals.length === 0 ? "Open an eligible recovery case to generate the first appeal draft." : "Adjust the search or status filter."}
                </p>
                {appeals.length === 0 && (
                  <Link href="/recovery" className="mt-4"><Button size="sm" variant="outline">Open recovery queue</Button></Link>
                )}
              </div>
            ) : (
              <div>{visibleAppeals.map((appeal) => <AppealRow key={appeal.id} appeal={appeal} />)}</div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
