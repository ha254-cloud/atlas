import { api } from "@/lib/api-client";
import type {
  PaymentEvidenceRecord,
  PaymentAllocationBatch,
  PaymentAllocationItem,
  ClaimPaymentTracking,
  PaymentMatchCandidate,
  PaymentsResponse,
  RecoveryAttribution,
  RecoveryDispute,
  RecoveryDisputeResolutionResult,
  RecoveryIntervention,
} from "@/types/payment";

export const paymentsService = {
  list: () => api.get<PaymentsResponse>("/api/v1/payments"),
  records: () => api.get<PaymentEvidenceRecord[]>("/api/v1/payments/records"),
  trackingForClaim: (claimId: number) =>
    api.get<ClaimPaymentTracking>(`/api/v1/payments/claims/${claimId}/tracking`),
  candidates: (paymentId: number) =>
    api.get<PaymentMatchCandidate[]>(`/api/v1/payments/records/${paymentId}/candidates`),
  match: (paymentId: number, claimId: number, reason: string) =>
    api.post<PaymentEvidenceRecord>(`/api/v1/payments/records/${paymentId}/match`, {
      claim_id: claimId,
      reason,
    }),
  allocate: (
    paymentId: number,
    allocations: PaymentAllocationItem[],
    reason: string,
    idempotencyKey: string,
  ) =>
    api.post<PaymentAllocationBatch>(
      `/api/v1/payments/records/${paymentId}/allocations`,
      {
        allocations,
        reason,
        idempotency_key: idempotencyKey,
      },
    ),
  verifyRecovery: (recoveryId: number, reason: string) =>
    api.post(`/api/v1/recoveries/${recoveryId}/verify`, { reason }),
  interventions: (recoveryId: number) =>
    api.get<RecoveryIntervention[]>(
      `/api/v1/recoveries/${recoveryId}/interventions`,
    ),
  recordIntervention: (
    claimId: number,
    interventionType: string,
    occurredAt: string,
    reason: string,
  ) =>
    api.post<RecoveryIntervention>("/api/v1/recoveries/interventions", {
      claim_id: claimId,
      intervention_type: interventionType,
      occurred_at: occurredAt,
      reason,
    }),
  decideAttribution: (
    recoveryId: number,
    interventionId: number,
    reason: string,
  ) =>
    api.post<RecoveryAttribution>(
      `/api/v1/recoveries/${recoveryId}/attributions`,
      {
        status: "eligible",
        intervention_id: interventionId,
        reason,
      },
    ),
  disputes: (recoveryId: number) =>
    api.get<RecoveryDispute[]>(`/api/v1/recoveries/${recoveryId}/disputes`),
  openDispute: (recoveryId: number, reason: string) =>
    api.post<RecoveryDispute>(`/api/v1/recoveries/${recoveryId}/disputes`, {
      reason,
    }),
  resolveDispute: (
    recoveryId: number,
    disputeId: number,
    outcome: "upheld" | "partially_upheld" | "accepted",
    eligibleAmount: string | null,
    reason: string,
  ) =>
    api.post<RecoveryDisputeResolutionResult>(
      `/api/v1/recoveries/${recoveryId}/disputes/${disputeId}/resolve`,
      {
        outcome,
        eligible_amount: eligibleAmount,
        reason,
      },
    ),
};