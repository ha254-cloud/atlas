"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { claimsService } from "@/services/claims-service";
import { PriorityBadge } from "@/features/claims/components/priority-badge";
import { ClaimStatusBadge } from "@/features/claims/components/claim-status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency } from "@/lib/utils";

export function RecoveryOpportunitiesTable() {
  const { data: claims, isLoading } = useQuery({
    queryKey: ["claims"],
    queryFn: () => claimsService.list(),
  });

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  const opportunities = (claims ?? [])
    .filter((c) => c.status === "denied" || c.status === "pending")
    .sort((a, b) => (b.billed_amount - b.paid_amount) - (a.billed_amount - a.paid_amount));

  if (!opportunities.length) {
    return (
      <div className="py-16 text-center text-muted-foreground">
        No recovery opportunities found.
      </div>
    );
  }

  return (
    <div className="rounded-md border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 border-b">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Priority</th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Claim #</th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground">Billed</th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground">Balance</th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Recommended Action</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y">
          {opportunities.map((claim) => {
            const balance = claim.billed_amount - claim.paid_amount;
            const score = Math.round(
              claim.ai_score ?? (claim.recovery_probability ?? 0) * 100,
            );
            return (
              <tr key={claim.id} className="hover:bg-muted/30 transition-colors">
                <td className="px-4 py-3">
                  <PriorityBadge score={score} />
                </td>
                <td className="px-4 py-3 font-mono font-medium">{claim.claim_number}</td>
                <td className="px-4 py-3">
                  <ClaimStatusBadge status={claim.status} />
                </td>
                <td className="px-4 py-3 text-right">{formatCurrency(claim.billed_amount)}</td>
                <td className="px-4 py-3 text-right font-semibold text-destructive">
                  {formatCurrency(balance)}
                </td>
                <td className="px-4 py-3 text-muted-foreground text-xs max-w-xs truncate">
                  Review denial category and evaluate appeal readiness.
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/claims/detail?id=${claim.id}`}
                    className="text-primary hover:underline text-xs font-medium"
                  >
                    View
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
