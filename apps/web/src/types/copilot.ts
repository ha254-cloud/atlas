export interface CopilotEvidence {
  label: string;
  path: string;
  value?: string | number;
}

export interface CopilotClaimResult {
  id?: number;
  claim_id?: number;
  claim_number: string;
  payer: string;
  status?: string;
  priority: string;
  billed_amount?: number;
  outstanding_amount?: number;
  estimated_recovery?: number;
  recovery_score?: number;
}

export interface CopilotMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  tool_name: string | null;
  tool_input: Record<string, unknown> | null;
  tool_output: unknown;
  evidence: CopilotEvidence[] | null;
  navigation_path: string | null;
  created_at: string;
}

export interface CopilotConfirmation {
  token: string;
  summary: string;
  expires_at: string;
}

export interface CopilotChatResponse {
  conversation_id: number;
  message: CopilotMessage;
  confirmation: CopilotConfirmation | null;
  suggested_questions: string[];
}

export interface CopilotConversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface CopilotConversationDetail extends CopilotConversation {
  messages: CopilotMessage[];
}