import { api } from "@/lib/api-client";
import type {
  PaymentEvidenceRecord,
  ClaimPaymentTracking,
  PaymentMatchCandidate,
  PaymentsResponse,
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
};