import { Badge } from "@/components/ui/badge";
import type { ClaimStatus } from "@/types";

const STATUS_CONFIG: Record<ClaimStatus, { label: string; variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" }> = {
  paid:     { label: "Paid",     variant: "success" },
  denied:   { label: "Denied",   variant: "destructive" },
  pending:  { label: "Pending",  variant: "warning" },
  imported: { label: "Imported", variant: "secondary" },
  appealed: { label: "Appealed", variant: "default" },
  closed:   { label: "Closed",   variant: "outline" },
};

export function ClaimStatusBadge({ status }: { status: ClaimStatus }) {
  const config = STATUS_CONFIG[status] ?? { label: status, variant: "secondary" as const };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
