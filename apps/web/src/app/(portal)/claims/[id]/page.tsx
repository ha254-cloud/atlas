"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, TrendingUp, AlertTriangle,
  ClipboardCheck, ThumbsUp, ThumbsDown, Edit3, CheckCircle,
} from "lucide-react";
import { claimsService } from "@/services/claims-service";
import { workspaceService } from "@/services/workspace-service";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ClaimStatusBadge } from "@/features/claims/components/claim-status-badge";
import { PriorityBadge } from "@/features/claims/components/priority-badge";
import { PriorityBadge as ClaimPriorityBadge } from "@/features/recovery/components/PriorityBadge";
import { EvidencePanel } from "@/features/claims/components/EvidencePanel";
import { ClaimDocuments } from "@/features/claims/components/ClaimDocuments";
import { PaymentTracking } from "@/features/claims/components/PaymentTracking";
import { ClaimTimeline } from "@/features/claims/components/claim-timeline";
import { AppealBuilder } from "@/features/appeals/components/AppealBuilder";
import { formatCurrency, formatDate } from "@/lib/utils";

export default function ClaimDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [reviewSubmitted, setReviewSubmitted] = useState(false);

  const { data: claim, isLoading } = useQuery({
    queryKey: ["claim", id],
    queryFn: () => claimsService.get(Number(id)),
  });

  const { data: analysis } = useQuery({
    queryKey: ["claim-analysis", id],
    queryFn: () => claimsService.analysis(Number(id)),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "pending" || status === "running" ? 3000 : false;
    },
  });

  const reviewMutation = useMutation({
    mutationFn: ({ rc_id, decision }: { rc_id: number; decision: "accepted" | "edited" | "rejected" }) =>
      workspaceService.submitAIReview(rc_id, decision),
    onSuccess: () => {
      setReviewSubmitted(true);
      queryClient.invalidateQueries({ queryKey: ["recovery-workspace"] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex flex-col h-full">
        <Header title="Claim Details" />
        <div className="p-6 space-y-4 max-w-3xl">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-36 w-full" />
          <Skeleton className="h-36 w-full" />
        </div>
      </div>
    );
  }

  if (!claim) {
    return (
      <div className="flex flex-col h-full">
        <Header title="Claim Details" />
        <div className="p-6 text-center text-muted-foreground py-16">Claim not found.</div>
      </div>
    );
  }

  const topRecovery = claim.recovery_cases?.[0];
  const topDenial   = claim.denials?.[0];

  return (
    <div className="flex flex-col h-full">
      <Header title={`Claim ${claim.claim_number}`} />
      <div className="flex-1 overflow-y-auto p-6 space-y-5 max-w-3xl">
        <Button variant="ghost" size="sm" onClick={() => router.back()} className="-ml-1">
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>

        {/* 1. Claim Summary */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <CardTitle className="text-base">Claim Summary</CardTitle>
              <div className="flex items-center gap-2">
                <ClaimPriorityBadge priority={claim.priority} />
                <ClaimStatusBadge status={claim.status} />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div><dt className="text-muted-foreground text-xs">Claim #</dt><dd className="font-mono font-semibold mt-0.5">{claim.claim_number}</dd></div>
              <div><dt className="text-muted-foreground text-xs">Service Date</dt><dd className="font-medium mt-0.5">{claim.service_date ? formatDate(claim.service_date) : "—"}</dd></div>
              <div><dt className="text-muted-foreground text-xs">Billed</dt><dd className="font-semibold mt-0.5">{formatCurrency(claim.billed_amount)}</dd></div>
              <div><dt className="text-muted-foreground text-xs">Paid</dt><dd className="font-medium mt-0.5 text-muted-foreground">{formatCurrency(claim.paid_amount)}</dd></div>
              <div><dt className="text-muted-foreground text-xs">Provider</dt><dd className="font-medium mt-0.5">{claim.provider ?? "—"}</dd></div>
              <div><dt className="text-muted-foreground text-xs">Assigned To</dt><dd className="font-medium mt-0.5">{claim.assigned_user_name ?? "Unassigned"}</dd></div>
            </dl>
          </CardContent>
        </Card>

        {/* 2. Denial */}
        {topDenial && (
          <Card className="border-destructive/30">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm text-destructive">
                <AlertTriangle className="h-4 w-4" /> Denial Information
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="flex items-center gap-2">
                <Badge variant="destructive">{topDenial.denial_code}</Badge>
                <span className="text-sm font-medium">{topDenial.denial_type?.replace(/_/g, " ")}</span>
              </div>
              <p className="text-sm text-muted-foreground">{topDenial.description}</p>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="flex items-center gap-2 text-sm">
                <ClipboardCheck className="h-4 w-4 text-primary" /> Claim Analysis
              </CardTitle>
              <Badge variant={analysis?.status === "failed" ? "destructive" : "outline"}>
                {analysis?.status ?? claim.analysis_status}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {analysis?.status === "completed" ? (
              <div className="space-y-4">
                <dl className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
                  <div><dt className="text-xs text-muted-foreground">Risk Score</dt><dd className="mt-0.5 font-semibold">{analysis.risk_score ?? "—"}</dd></div>
                  <div><dt className="text-xs text-muted-foreground">Priority</dt><dd className="mt-0.5 font-semibold">{analysis.priority ?? "—"}</dd></div>
                  <div><dt className="text-xs text-muted-foreground">Confidence</dt><dd className="mt-0.5 font-semibold">{analysis.confidence != null ? `${Math.round(analysis.confidence * 100)}%` : "—"}</dd></div>
                  <div><dt className="text-xs text-muted-foreground">Recovery Probability</dt><dd className="mt-0.5 font-semibold">{analysis.recovery_probability != null ? `${Math.round(analysis.recovery_probability * 100)}%` : "—"}</dd></div>
                </dl>
                <div className="space-y-2 border-t pt-4 text-sm">
                  <div><p className="text-xs font-medium text-muted-foreground">Summary</p><p className="mt-1">{analysis.summary}</p></div>
                  <div><p className="text-xs font-medium text-muted-foreground">Recommended Action</p><p className="mt-1 font-medium">{analysis.recommended_action}</p></div>
                  {analysis.required_documents.length > 0 && (
                    <div><p className="text-xs font-medium text-muted-foreground">Required Documents</p><p className="mt-1">{analysis.required_documents.join(", ")}</p></div>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {analysis?.status === "failed"
                  ? "Analysis could not be completed. The claim remains available for review."
                  : "Analysis is in progress."}
              </p>
            )}
          </CardContent>
        </Card>

        {/* 3. Recovery Analysis */}
        {topRecovery && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-sm">
                <ClipboardCheck className="h-4 w-4 text-primary" /> Recovery Analysis
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <dl className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <dt className="text-muted-foreground text-xs">Recovery Score</dt>
                  <dd className="font-semibold mt-0.5 flex items-center gap-1.5">
                    {topRecovery.recovery_score} <PriorityBadge score={topRecovery.recovery_score} />
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground text-xs">Estimated Recovery</dt>
                  <dd className="font-semibold text-green-700 mt-0.5">{formatCurrency(topRecovery.estimated_value)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground text-xs">Confidence</dt>
                  <dd className="font-semibold mt-0.5">{Math.round(topRecovery.recovery_score)}%</dd>
                </div>
              </dl>

              {/* Recommendation */}
              <div className="rounded-lg bg-muted/40 border p-4 space-y-2.5">
                <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Recommendation</p>
                {topDenial && (
                  <div>
                    <p className="text-xs text-muted-foreground font-medium uppercase mb-0.5">Problem</p>
                    <p className="text-sm font-medium">{topDenial.denial_type?.replace(/_/g, " ")} — {topDenial.denial_code}</p>
                  </div>
                )}
                <div>
                  <p className="text-xs text-muted-foreground font-medium uppercase mb-0.5">Recommended Action</p>
                  <p className="text-sm">{topRecovery.recommendation}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium uppercase mb-0.5">Expected Success</p>
                  <p className="text-sm font-semibold">{Math.round(topRecovery.recovery_score)}%</p>
                </div>
              </div>

              {/* Human Review */}
              {!reviewSubmitted ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">Was this helpful?</span>
                  <Button size="sm" variant="outline" className="gap-1 text-green-700 border-green-200 hover:bg-green-50"
                    onClick={() => reviewMutation.mutate({ rc_id: topRecovery.id, decision: "accepted" })}>
                    <ThumbsUp className="h-3 w-3" /> Accept
                  </Button>
                  <Button size="sm" variant="outline" className="gap-1 text-yellow-700 border-yellow-200 hover:bg-yellow-50"
                    onClick={() => reviewMutation.mutate({ rc_id: topRecovery.id, decision: "edited" })}>
                    <Edit3 className="h-3 w-3" /> Edited
                  </Button>
                  <Button size="sm" variant="outline" className="gap-1 text-red-700 border-red-200 hover:bg-red-50"
                    onClick={() => reviewMutation.mutate({ rc_id: topRecovery.id, decision: "rejected" })}>
                    <ThumbsDown className="h-3 w-3" /> Reject
                  </Button>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground flex items-center gap-1">
                  <CheckCircle className="h-3 w-3 text-green-600" /> Feedback recorded.
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {/* 4. Evidence */}
        <EvidencePanel denial_code={topDenial?.denial_code} />

        <ClaimDocuments claimId={Number(id)} />

        {/* 5. Appeal Builder */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary" /> Appeal Builder
            </CardTitle>
          </CardHeader>
          <CardContent>
            <AppealBuilder claimId={Number(id)} recoveryId={topRecovery?.id} />
          </CardContent>
        </Card>

        {/* 6. Payment Tracking */}
        <PaymentTracking claimId={Number(id)} />

        {/* 7. Timeline */}
        <ClaimTimeline claimId={Number(id)} />
      </div>
    </div>
  );
}
