import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  icon: LucideIcon;
  loading?: boolean;
  className?: string;
}

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  loading = false,
  className,
}: MetricCardProps) {
  return (
    <Card className={cn("min-h-32", className)}>
      <CardContent className="h-full p-5">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />
          <p className="truncate text-xs font-semibold uppercase tracking-wide">{label}</p>
        </div>
        <div className="min-w-0 pl-6">
          {loading ? (
            <Skeleton className="mt-2 h-8 w-32" />
          ) : (
            <div className="mt-1.5 break-words text-2xl font-semibold tabular-nums">{value}</div>
          )}
          {detail && !loading && <div className="mt-1 text-xs text-muted-foreground">{detail}</div>}
        </div>
      </CardContent>
    </Card>
  );
}