import { cn } from "@/lib/utils";

const CONFIG = {
  critical: { label: "CRITICAL", classes: "bg-red-100 text-red-800 border-red-200" },
  high:     { label: "HIGH",     classes: "bg-orange-100 text-orange-800 border-orange-200" },
  medium:   { label: "MEDIUM",   classes: "bg-yellow-100 text-yellow-800 border-yellow-200" },
  low:      { label: "LOW",      classes: "bg-green-100 text-green-800 border-green-200" },
} as const;

type Priority = keyof typeof CONFIG;

export function PriorityBadge({ priority }: { priority: Priority | string }) {
  const cfg = CONFIG[priority as Priority] ?? CONFIG.low;
  return (
    <span className={cn("inline-flex items-center rounded border px-2 py-0.5 text-xs font-bold", cfg.classes)}>
      {cfg.label}
    </span>
  );
}
