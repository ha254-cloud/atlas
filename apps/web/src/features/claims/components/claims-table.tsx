"use client";

import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { claimsService } from "@/services/claims-service";
import { ClaimStatusBadge } from "./claim-status-badge";
import { PriorityBadge } from "@/features/recovery/components/PriorityBadge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { Claim } from "@/types";

interface Props {
  search?: string;
  status?: string;
  priority?: string;
}

export function ClaimsTable({ search, status, priority }: Props) {
  const queryClient = useQueryClient();

  const { data: claims, isLoading } = useQuery({
    queryKey: ["claims", { search, status, priority }],
    queryFn: () =>
      claimsService.list({
        search: search || undefined,
        status: status || undefined,
        priority: priority || undefined,
      }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => claimsService.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["claims"] }),
  });

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (!claims?.length) {
    return (
      <div className="py-16 text-center text-muted-foreground">
        {search || status || priority
          ? "No claims match your filters."
          : "No claims found. Upload or create a claim to get started."}
      </div>
    );
  }

  return (
    <div className="rounded-md border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 border-b">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Claim #</th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Patient</th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Payer</th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Service Date</th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground">Billed</th>
            <th className="px-4 py-3 text-right font-medium text-muted-foreground">Paid</th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Priority</th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
            <th className="px-4 py-3 text-left font-medium text-muted-foreground">Analysis</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y">
          {claims.map((claim: Claim) => (
            <tr key={claim.id} className="hover:bg-muted/30 transition-colors">
              <td className="px-4 py-3 font-mono font-medium">{claim.claim_number}</td>
              <td className="px-4 py-3 text-muted-foreground">{claim.patient_name ?? "—"}</td>
              <td className="px-4 py-3 text-muted-foreground">{claim.payer_name ?? "—"}</td>
              <td className="px-4 py-3 text-muted-foreground">
                {claim.service_date ? formatDate(claim.service_date) : "—"}
              </td>
              <td className="px-4 py-3 text-right font-medium">
                {formatCurrency(claim.billed_amount)}
              </td>
              <td className="px-4 py-3 text-right text-muted-foreground">
                {formatCurrency(claim.paid_amount)}
              </td>
              <td className="px-4 py-3">
                <PriorityBadge priority={claim.priority} />
              </td>
              <td className="px-4 py-3">
                <ClaimStatusBadge status={claim.status} />
              </td>
              <td className="px-4 py-3">
                <Badge variant={claim.analysis_status === "failed" ? "destructive" : "outline"}>
                  {claim.analysis_status}
                </Badge>
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center justify-end gap-3">
                  <Link
                    href={`/claims/detail?id=${claim.id}`}
                    className="text-primary hover:underline text-xs font-medium"
                  >
                    View
                  </Link>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                    disabled={deleteMutation.isPending}
                    onClick={() => {
                      if (confirm(`Delete claim ${claim.claim_number}? This cannot be undone.`)) {
                        deleteMutation.mutate(claim.id);
                      }
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
