export interface PaymentSummary {
  total_recovered: number;
  total_fees: number;
  net_recovered: number;
  payment_count: number;
  invoices_generated: number;
}

export interface PaymentRecord {
  payment_id: number;
  recovery_id: number | null;
  claim_id: number;
  claim_number: string;
  payer: string;
  recovered_amount: number;
  atlas_fee: number;
  net_amount: number;
  received_at: string;
  currency: string;
  payment_status: string;
  payment_source: string;
  recovery_verified: boolean;
  invoice_id: number | null;
  invoice_generated: boolean;
}

export interface PaymentTrackingStage {
  key: string;
  label: string;
  state: "pending" | "current" | "complete" | "failed";
  detail: string | null;
  occurred_at: string | null;
}

export interface ClaimPaymentTracking {
  claim_id: number;
  stages: PaymentTrackingStage[];
  appeal_id: number | null;
  appeal_status: string | null;
  submission_id: number | null;
  submission_status: string | null;
  submission_channel: string | null;
  payment_received: boolean;
  payment_amount: number | null;
  payment_currency: string | null;
  payment_received_at: string | null;
  recovery_verified: boolean;
  recovered_amount: number | null;
  atlas_fee_amount: number | null;
  recovery_verified_at: string | null;
  invoice_created: boolean;
  invoice_id: number | null;
  invoice_number: string | null;
  invoice_status: string | null;
  last_updated_at: string | null;
}

export interface PaymentsResponse {
  summary: PaymentSummary;
  payments: PaymentRecord[];
}

export interface PaymentEvidenceRecord {
  id: number;
  claim_id: number | null;
  submission_id: number | null;
  payer_name: string;
  payment_reference: string;
  payment_date: string;
  expected_amount: string;
  paid_amount: string;
  adjustment_amount: string;
  currency: string;
  payment_method: string | null;
  status: string;
  source: string;
  matched_at: string | null;
  matched_by_id: number | null;
  matching_method: string | null;
  matching_reason: string | null;
  correlation_id: string;
  created_at: string;
}

export interface PaymentMatchCandidate {
  claim_id: number;
  claim_number: string;
  payer_name: string;
  billed_amount: string;
  paid_amount: string;
  outstanding_amount: string;
  confidence: number;
  reasons: string[];
}