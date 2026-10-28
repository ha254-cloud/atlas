import { formatCurrency } from "@/lib/utils";
import type { WorkspaceSummary } from "@/services/workspace-service";
import { Skeleton } from "@/components/ui/skeleton";

const BUCKETS = [
  { key: "critical" as const, label: "Critical", accent: "bg-red-500" },
  { key: "high"     as const, label: "High",     accent: "bg-orange-500" },
  { key: "medium"   as const, label: "Medium",   accent: "bg-amber-500" },
  { key: "low"      as const, label: "Low",      accent: "bg-emerald-500" },
];

interface Props {
  summary?: WorkspaceSummary;
  loading?: boolean;
}

export function RecoverySummary({ summary, loading }: Props) {
  if (loading) return <Skeleton className="h-28 w-full rounded-lg" />;
  if (!summary) return null;

  return (
    <section className="overflow-hidden rounded-lg border bg-card" aria-label="Recovery queue summary">
      <div className="grid divide-y sm:grid-cols-[minmax(220px,1.35fr)_repeat(4,minmax(88px,0.65fr))] sm:divide-x sm:divide-y-0">
        <div className="px-5 py-4">
          <p className="text-xs font-medium text-muted-foreground">Recoverable balance</p>
          <div className="mt-1 flex items-baseline gap-3">
            <p className="text-2xl font-semibold tabular-nums text-foreground">
              {formatCurrency(summary.estimated_recovery)}
            </p>
            <span className="text-xs text-muted-foreground">
              {summary.total} open {summary.total === 1 ? "case" : "cases"}
            </span>
          </div>
        </div>

        {BUCKETS.map(({ key, label, accent }) => (
          <div key={key} className="flex items-center justify-between px-4 py-3 sm:block sm:py-4">
            <div className="flex items-center gap-2">
              <span className={`h-1.5 w-1.5 rounded-full ${accent}`} />
              <span className="text-xs font-medium text-muted-foreground">{label}</span>
            </div>
            <p className="mt-0.5 text-lg font-semibold tabular-nums text-foreground sm:pl-3.5">
              {summary[key]}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
