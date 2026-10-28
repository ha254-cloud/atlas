"use client";

import { useQuery } from "@tanstack/react-query";
import {
  FilePlus, Upload, Search, AlertTriangle, ClipboardCheck,
  FileText, Send, Banknote, RefreshCw, CheckCircle2, History,
} from "lucide-react";
import { claimsService } from "@/services/claims-service";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ClaimTimelineEvent } from "@/types";

const EVENT_CONFIG: Record<string, { label: string; icon: typeof FilePlus }> = {
  "claim.created":            { label: "Claim Created",       icon: FilePlus },
  "claim.imported":           { label: "Claim Imported",      icon: Upload },
  "claim.analyzed":           { label: "Analysis Complete",   icon: Search },
  "claim.denial_recorded":    { label: "Denial Recorded",     icon: AlertTriangle },
  "claim.recovery_created":   { label: "Recovery Case Opened", icon: ClipboardCheck },
  "claim.appeal_generated":   { label: "Appeal Generated",    icon: FileText },
  "claim.appeal_submitted":   { label: "Appeal Submitted",    icon: Send },
  "claim.payment_received":   { label: "Payment Received",    icon: Banknote },
  "claim.status_changed":     { label: "Status Changed",      icon: RefreshCw },
  "claim.recovery_closed":    { label: "Recovery Closed",     icon: CheckCircle2 },
};

function formatTimestamp(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function ClaimTimeline({ claimId }: { claimId: number }) {
  const { data: events, isLoading } = useQuery({
    queryKey: ["claim-timeline", claimId],
    queryFn: () => claimsService.timeline(claimId),
  });

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <History className="h-4 w-4 text-primary" /> Timeline
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        )}

        {!isLoading && !events?.length && (
          <p className="text-sm text-muted-foreground">No activity recorded yet.</p>
        )}

        {!isLoading && !!events?.length && (
          <ol className="relative border-l pl-5 space-y-5">
            {events.map((event: ClaimTimelineEvent) => {
              const config = EVENT_CONFIG[event.event_type] ?? { label: event.event_type, icon: History };
              const Icon = config.icon;
              return (
                <li key={event.id} className="relative">
                  <span className="absolute -left-[27px] flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 border">
                    <Icon className="h-3 w-3 text-primary" />
                  </span>
                  <p className="text-sm font-medium">{config.label}</p>
                  <p className="text-xs text-muted-foreground">{event.description}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {formatTimestamp(event.occurred_at)}
                  </p>
                </li>
              );
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
