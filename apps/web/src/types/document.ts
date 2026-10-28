export type DocumentType =
  | "operative_report"
  | "imaging"
  | "referral"
  | "lab_results"
  | "authorization"
  | "physician_notes"
  | "other";

export interface ClaimDocument {
  id: number;
  claim_id: number;
  document_type: DocumentType;
  filename: string;
  content_type: string;
  file_size: number;
  checksum: string;
  tags: string[];
  extracted_text?: string | null;
  ai_summary?: string | null;
  uploaded_by_id?: number | null;
  created_at: string;
}