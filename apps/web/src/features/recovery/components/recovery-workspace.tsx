"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp } from "lucide-react";
import { workspaceService } from "@/services/workspace-service";
import { RecoverySummary } from "./RecoverySummary";
import { RecoveryCard } from "./RecoveryCard";
import { RecoveryFilters } from "./RecoveryFilters";
import { Skeleton } from "@/components/ui/skeleton";

const PRIORITY_ORDER = ["critical", "high", "medium", "low"] as const;

export function RecoveryWorkspace() {
  const [filters, setFilters] = useState({ search: "", priority: "", status: "" });

  const { data, isLoading } = useQuery({
    queryKey: ["recovery-workspace", filters],
    queryFn: () =>
      workspaceService.getWorkspace({
        priority: filters.priority || undefined,
        status: filters.status || undefined,
        search: filters.search || undefined,
        limit: 200,
      }),
    staleTime: 30_000,
  });

  const cases = data?.cases ?? [];

  const grouped = PRIORITY_ORDER.reduce((acc, p) => {
    acc[p] = cases.filter((c) => c.priority === p);
    return acc;
  }, {} as Record<string, typeof cases>);

  return (
    <div className="space-y-4">
      <RecoverySummary summary={data?.summary} loading={isLoading} />

      <section className="overflow-hidden rounded-lg border bg-card" aria-label="Recovery work queue">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold">Open work queue</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">Prioritized claims requiring recovery action</p>
          </div>
          {!isLoading && <span className="text-xs tabular-nums text-muted-foreground">{cases.length} results</span>}
        </div>

        <RecoveryFilters filters={filters} onChange={setFilters} />

        <div className="hidden grid-cols-[minmax(170px,1.2fr)_minmax(190px,1.35fr)_110px_120px_96px] bg-muted/30 px-4 py-2 text-xs font-medium text-muted-foreground md:grid">
          <span>Claim</span>
          <span>Payer / patient</span>
          <span className="text-right">Confidence</span>
          <span className="text-right">Recovery</span>
          <span className="sr-only">Action</span>
        </div>

        {isLoading ? (
        <div className="space-y-2 p-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded" />
          ))}
        </div>
      ) : cases.length === 0 ? (
        <div className="py-16 text-center text-muted-foreground">
          <TrendingUp className="mx-auto h-10 w-10 opacity-30 mb-3" />
          <p className="font-medium">No open recovery opportunities.</p>
          <p className="text-sm mt-1">
            {filters.search || filters.priority || filters.status
              ? "Try adjusting your filters."
              : "Import claims to populate the work queue."}
          </p>
        </div>
      ) : (
        <div>
          {PRIORITY_ORDER.map((priority) => {
            const items = grouped[priority];
            if (!items.length) return null;
            return (
              <section key={priority} className="border-t first:border-t-0">
                <h3 className="bg-muted/10 px-4 py-2 text-xs font-medium capitalize text-muted-foreground">
                  {priority} priority <span className="ml-1 tabular-nums">({items.length})</span>
                </h3>
                <div>
                  {items.map((item) => (
                    <RecoveryCard key={item.id} item={item} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
      </section>
    </div>
  );
}
