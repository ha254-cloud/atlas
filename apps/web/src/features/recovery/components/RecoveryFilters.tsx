"use client";

import { useCallback } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";

const PRIORITIES = [
  { value: "",         label: "All" },
  { value: "critical", label: "Critical" },
  { value: "high",     label: "High" },
  { value: "medium",   label: "Medium" },
  { value: "low",      label: "Low" },
];

const STATUSES = [
  { value: "",             label: "All Statuses" },
  { value: "open",         label: "Open" },
  { value: "in_progress",  label: "In Progress" },
  { value: "appealed",     label: "Appealed" },
];

interface Filters {
  search: string;
  priority: string;
  status: string;
}

interface Props {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export function RecoveryFilters({ filters, onChange }: Props) {
  const set = useCallback((key: keyof Filters, value: string) => {
    onChange({ ...filters, [key]: value });
  }, [filters, onChange]);

  return (
    <div className="flex flex-col gap-3 border-b bg-muted/20 p-3 sm:flex-row sm:items-center">
      <div className="relative min-w-56 flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search claim or payer"
          aria-label="Search recovery cases"
          className="h-9 bg-background pl-9"
          value={filters.search}
          onChange={(e) => set("search", e.target.value)}
        />
      </div>

      <div className="grid grid-cols-2 gap-2 sm:flex">
        <select
          aria-label="Filter by priority"
          value={filters.priority}
          onChange={(e) => set("priority", e.target.value)}
          className="h-9 min-w-32 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {PRIORITIES.map((priority) => (
            <option key={priority.value} value={priority.value}>
              {priority.value ? `${priority.label} priority` : "All priorities"}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by status"
          value={filters.status}
          onChange={(e) => set("status", e.target.value)}
          className="h-9 min-w-32 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {STATUSES.map((status) => (
            <option key={status.value} value={status.value}>{status.label}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
