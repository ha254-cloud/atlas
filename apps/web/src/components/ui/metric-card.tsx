import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const ACCENTS = {
  teal: "bg-emerald-50 text-emerald-700 ring-emerald-100",
  blue: "bg-sky-50 text-sky-700 ring-sky-100",
  amber: "bg-amber-50 text-amber-700 ring-amber-100",
  violet: "bg-violet-50 text-violet-700 ring-violet-100",
  neutral: "bg-muted text-muted-foreground ring-border",
} as const;

interface MetricCardProps {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  icon: LucideIcon;
  accent?: keyof typeof ACCENTS;
  loading?: boolean;
  className?: string;
}

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  accent = "neutral",
  loading = false,
  className,
}: MetricCardProps) {
  return (
    <Card className={cn("min-h-32", className)}>
      <CardContent className="flex h-full items-start justify-between gap-4 p-5">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase text-muted-foreground">{label}</p>
          {loading ? (
            <Skeleton className="mt-2 h-8 w-32" />
          ) : (
            <div className="mt-1.5 break-words text-2xl font-semibold tabular-nums">{value}</div>
          )}
          {detail && !loading && <div className="mt-1 text-xs text-muted-foreground">{detail}</div>}
        </div>
        <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-md ring-1 ring-inset", ACCENTS[accent])}>
          <Icon className="h-4 w-4" strokeWidth={1.8} />
        </div>
      </CardContent>
    </Card>
  );
}