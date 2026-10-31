"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ClipboardCheck, TrendingUp, AlertTriangle, ThumbsUp, ThumbsDown,
  Edit3, CheckCircle, FileText, Loader2, ChevronRight, Search,
  Building2, User as UserIcon,
} from "lucide-react";
import { workspaceService, type WorkspaceCase } from "@/services/workspace-service";
import { appealsService, type Appeal } from "@/services/appeals-service";
import { PriorityBadge } from "@/features/recovery/components/PriorityBadge";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { EmptyState } from "@/components/common/EmptyState";
import { formatCurrency, formatDate, cn } from "@/lib/utils";

// ─── Left panel: work queue list ────────────────────────────────────────────

function CaseRow({
  item,
  selected,
  onClick,
}: {
  item: WorkspaceCase;
  selected: boolean;
  onClick: () => void;
}) {
  const dotColor: Record<string, string> = {
    critical: "bg-red-500",
    high: "bg-orange-500",
    medium: "bg-yellow-500",
    low: "bg-green-500",
  };

  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left px-4 py-3 border-b transition-colors",
        selected ? "bg-primary/5 border-l-2 border-l-primary" : "hover:bg-muted/50 border-l-2 border-l-transparent",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className={cn("mt-1.5 h-2 w-2 rounded-full shrink-0", dotColor[item.priority] ?? "bg-muted")} />
          <div className="min-w-0">
            <p className="font-mono font-semibold text-xs truncate">{item.claim_number}</p>
            <p className="text-xs text-muted-foreground truncate">{item.payer_name}</p>
          </div>
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs font-bold">{formatCurrency(item.estimated_recovery)}</p>
          <p className="text-xs text-muted-foreground">{item.confidence}%</p>
        </div>
      </div>
    </button>
  );
}

// ─── Right panel: case detail ───────────────────────────────────────────────

function CaseDetail({ item }: { item: WorkspaceCase }) {
  const queryClient = useQueryClient();
  const [appeal, setAppeal] = useState<Appeal | null>(null);
  const [reviewDone, setReviewDone] = useState(false);

  const reviewMutation = useMutation({
    mutationFn: ({ decision }: { decision: "accepted" | "edited" | "rejected" }) =>
      workspaceService.submitAIReview(item.id, decision),
    onSuccess: () => {
      setReviewDone(true);
      queryClient.invalidateQueries({ queryKey: ["recovery-workspace"] });
    },
  });

  const appealMutation = useMutation({
    mutationFn: () => appealsService.generate(item.claim_id, item.id),
    onSuccess: (data) => setAppeal(data),
  });

  return (
    <div className="flex-1 overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-background border-b px-6 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5 mb-0.5">
              <PriorityBadge priority={item.priority} />
              <h2 className="font-mono font-bold">{item.claim_number}</h2>
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
              <span className="flex items-center gap-1"><Building2 className="h-3 w-3" />{item.payer_name}</span>
              <span className="flex items-center gap-1"><UserIcon className="h-3 w-3" />{item.patient_name}</span>
              {item.service_date && <span>{formatDate(item.service_date)}</span>}
            </div>
          </div>
          <div className="text-right">
            <p className="text-xl font-bold">{formatCurrency(item.estimated_recovery)}</p>
            <p className="text-xs text-muted-foreground">estimated recovery</p>
          </div>
        </div>
      </div>

      <div className="px-6 py-5 space-y-6">
        {/* Financial summary */}
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Billed</p>
            <p className="font-bold mt-0.5">{formatCurrency(item.billed_amount)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Paid</p>
            <p className="font-bold mt-0.5 text-muted-foreground">{formatCurrency(item.paid_amount)}</p>
          </div>
          <div className="rounded-lg border p-3 border-red-200 bg-red-50">
            <p className="text-xs text-red-600">Balance</p>
            <p className="font-bold mt-0.5 text-red-700">{formatCurrency(item.balance)}</p>
          </div>
        </div>

        {/* Denial */}
        {item.denial && (
          <>
            <Separator />
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5 text-destructive" /> Denial
              </h3>
              <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 space-y-1">
                <div className="flex items-center gap-2">
                  <Badge variant="destructive" className="text-xs">{item.denial.denial_code}</Badge>
                  <span className="text-sm font-medium">{item.denial.denial_type?.replace(/_/g, " ")}</span>
                </div>
                {item.denial.description && (
                  <p className="text-xs text-muted-foreground">{item.denial.description}</p>
                )}
              </div>
            </div>
          </>
        )}

        {/* Recovery Analysis */}
        <Separator />
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1.5">
            <ClipboardCheck className="h-3.5 w-3.5 text-primary" /> Recovery Analysis
          </h3>
          <div className="rounded-lg bg-muted/40 border p-4 space-y-3">
            {item.denial && (
              <div>
                <p className="text-xs text-muted-foreground font-semibold uppercase mb-0.5">Problem</p>
                <p className="text-sm font-medium">{item.denial.denial_code} — {item.denial.denial_type?.replace(/_/g, " ")}</p>
              </div>
            )}
            <div>
              <p className="text-xs text-muted-foreground font-semibold uppercase mb-0.5">Recommended Action</p>
              <p className="text-sm">{item.recommendation}</p>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <div>
                <p className="text-xs text-muted-foreground font-semibold uppercase mb-0.5">Expected Success</p>
                <p className="font-bold">{item.confidence}%</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground font-semibold uppercase mb-0.5">Status</p>
                <p className="capitalize font-medium">{item.status.replace(/_/g, " ")}</p>
              </div>
            </div>
          </div>

          {/* Human review */}
          {!reviewDone && !item.ai_review ? (
            <div className="mt-3 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Was this helpful?</span>
              {(["accepted", "edited", "rejected"] as const).map((d) => (
                <Button
                  key={d}
                  size="sm" variant="outline"
                  className={cn("gap-1 capitalize text-xs",
                    d === "accepted" ? "text-green-700 border-green-200 hover:bg-green-50" :
                    d === "edited"   ? "text-yellow-700 border-yellow-200 hover:bg-yellow-50" :
                    "text-red-700 border-red-200 hover:bg-red-50"
                  )}
                  disabled={reviewMutation.isPending}
                  onClick={() => reviewMutation.mutate({ decision: d })}
                >
                  {d === "accepted" ? <ThumbsUp className="h-3 w-3" /> :
                   d === "edited"   ? <Edit3 className="h-3 w-3" /> :
                   <ThumbsDown className="h-3 w-3" />}
                  {d.charAt(0).toUpperCase() + d.slice(1)}
                </Button>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-xs text-muted-foreground flex items-center gap-1">
              <CheckCircle className="h-3 w-3 text-green-600" />
              {item.ai_review ? `Marked as ${item.ai_review}` : "Feedback recorded"}
            </p>
          )}
        </div>

        {/* Appeal */}
        <Separator />
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wide text-muted-foreground mb-3 flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5 text-primary" /> Appeal
          </h3>

          {!appeal ? (
            <Button
              onClick={() => appealMutation.mutate()}
              disabled={appealMutation.isPending}
              className="gap-2"
            >
              {appealMutation.isPending
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
                : <><FileText className="h-4 w-4" /> Generate Appeal</>
              }
            </Button>
          ) : (
            <div className="space-y-3">
              {appeal.summary && (
                <p className="text-sm bg-blue-50 rounded-md p-3 border border-blue-100 text-blue-800">
                  <strong>Summary: </strong>{appeal.summary}
                </p>
              )}
              <div className="rounded-md border bg-muted/20 p-4 max-h-64 overflow-y-auto">
                <pre className="text-xs whitespace-pre-wrap font-sans leading-relaxed">{appeal.appeal_text}</pre>
              </div>
              <div className="flex flex-wrap gap-2">
                {appeal.status !== "submitted" && (
                  <Button size="sm" className="gap-1" asChild>
                    <Link href={`/claims/detail?id=${item.claim_id}`}>
                      Review and submit <ChevronRight className="h-3 w-3" />
                    </Link>
                  </Button>
                )}
                {appeal.status === "submitted" && appeal.confirmation_number && (
                  <Badge variant="success">Submitted · {appeal.confirmation_number}</Badge>
                )}
                {appeal.status === "submitted" && !appeal.confirmation_number && (
                  <Badge variant="destructive">Unverified submission record</Badge>
                )}
                <Button size="sm" variant="ghost" onClick={() => { setAppeal(null); appealMutation.reset(); }}>
                  Regenerate
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main two-panel workspace ────────────────────────────────────────────────

export function RecoveryWorkspace() {
  const [search, setSearch] = useState("");
  const [priority, setPriority] = useState("");
  const [selected, setSelected] = useState<WorkspaceCase | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["recovery-workspace", { search, priority }],
    queryFn: () => workspaceService.getWorkspace({ search: search || undefined, priority: priority || undefined, limit: 200 }),
    staleTime: 30_000,
  });

  const cases = data?.cases ?? [];
  const summary = data?.summary;

  return (
    <div className="flex h-full overflow-hidden">
      {/* ── LEFT PANEL ── */}
      <div className="flex flex-col w-80 shrink-0 border-r bg-background">
        {/* Summary bar */}
        <div className="px-4 py-3 border-b bg-muted/30">
          <div className="flex justify-between text-xs text-muted-foreground mb-1">
            <span>{summary?.total ?? 0} cases</span>
            <span className="font-semibold text-foreground">{formatCurrency(summary?.estimated_recovery ?? 0)}</span>
          </div>
          <div className="flex gap-3 text-xs">
            {[
              { key: "critical", color: "text-red-600" },
              { key: "high", color: "text-orange-600" },
              { key: "medium", color: "text-yellow-600" },
              { key: "low", color: "text-green-600" },
            ].map(({ key, color }) => (
              <span key={key} className={color}>
                {summary?.[key as keyof typeof summary] ?? 0} {key}
              </span>
            ))}
          </div>
        </div>

        {/* Search + filter */}
        <div className="px-3 py-2 border-b space-y-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              className="pl-8 h-8 text-xs"
              placeholder="Search claim number…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex gap-1 flex-wrap">
            {["", "critical", "high", "medium", "low"].map((p) => (
              <button
                key={p}
                onClick={() => setPriority(p)}
                className={cn(
                  "px-2 py-0.5 rounded text-xs font-medium transition-colors",
                  priority === p ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80",
                )}
              >
                {p || "All"}
              </button>
            ))}
          </div>
        </div>

        {/* Case list */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-3 space-y-2">
              {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
            </div>
          ) : cases.length === 0 ? (
            <EmptyState
              icon={TrendingUp}
              title="No cases found"
              description={search || priority ? "Try adjusting your filters." : "Import claims to populate the workspace."}
            />
          ) : (
            cases.map((item) => (
              <CaseRow
                key={item.id}
                item={item}
                selected={selected?.id === item.id}
                onClick={() => setSelected(item)}
              />
            ))
          )}
        </div>
      </div>

      {/* ── RIGHT PANEL ── */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {selected ? (
          <CaseDetail key={selected.id} item={selected} />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-3">
            <TrendingUp className="h-12 w-12 opacity-20" />
            <p className="font-medium">Select a recovery case</p>
            <p className="text-sm">Click any case on the left to view the full analysis and generate an appeal.</p>
          </div>
        )}
      </div>
    </div>
  );
}
