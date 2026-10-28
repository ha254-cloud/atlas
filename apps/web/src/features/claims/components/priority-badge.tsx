import { Badge } from "@/components/ui/badge";

const PRIORITY_CONFIG: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" }> = {
  critical: { label: "Critical", variant: "destructive" },
  high:     { label: "High",     variant: "warning" },
  medium:   { label: "Medium",   variant: "default" },
  low:      { label: "Low",      variant: "secondary" },
};

function getPriority(score: number): string {
  if (score >= 90) return "critical";
  if (score >= 70) return "high";
  if (score >= 40) return "medium";
  return "low";
}

export function PriorityBadge({ score }: { score: number }) {
  const priority = getPriority(score);
  const config = PRIORITY_CONFIG[priority];
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
