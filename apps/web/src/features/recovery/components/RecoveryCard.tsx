import Link from "next/link";
import { ArrowRight, AlertCircle } from "lucide-react";
import { cn, formatCurrency, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { WorkspaceCase } from "@/services/workspace-service";

const PRIORITY_STYLE: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-amber-500",
  low: "bg-emerald-500",
};

interface Props {
  item: WorkspaceCase;
}

export function RecoveryCard({ item }: Props) {
  return (
    <div className="grid gap-3 border-t px-4 py-3 transition-colors first:border-t-0 hover:bg-muted/20 md:grid-cols-[minmax(170px,1.2fr)_minmax(190px,1.35fr)_110px_120px_96px] md:items-center">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn("h-2 w-2 shrink-0 rounded-full", PRIORITY_STYLE[item.priority] ?? "bg-slate-400")} />
          <p className="truncate font-mono text-sm font-semibold">{item.claim_number}</p>
        </div>
        {item.service_date && (
          <p className="mt-1 pl-4 text-xs text-muted-foreground">{formatDate(item.service_date)}</p>
        )}
      </div>

      <div className="flex-1 min-w-0">
        <p className="truncate text-sm font-medium">{item.payer_name}</p>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">{item.patient_name}</p>
        {item.denial && (
          <div className="mt-1 flex items-center gap-1 text-xs text-destructive">
            <AlertCircle className="h-3 w-3" />
            <span className="font-medium">{item.denial.denial_code}</span>
          </div>
        )}
      </div>

      <div className="md:text-right">
        <p className="text-sm font-medium tabular-nums">{item.confidence}%</p>
        <p className="text-xs capitalize text-muted-foreground">{item.priority}</p>
      </div>

      <div className="md:text-right">
        <p className="text-sm font-semibold tabular-nums">{formatCurrency(item.estimated_recovery)}</p>
        <p className="text-xs tabular-nums text-muted-foreground">of {formatCurrency(item.balance)}</p>
      </div>

      <Link href={`/claims/detail?id=${item.claim_id}`} className="justify-self-start md:justify-self-end">
        <Button size="sm" variant="ghost" className="gap-1.5 text-xs">
          Review <ArrowRight className="h-3.5 w-3.5" />
        </Button>
      </Link>
    </div>
  );
}
