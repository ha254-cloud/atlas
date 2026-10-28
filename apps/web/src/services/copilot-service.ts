import { api } from "@/lib/api-client";
import type {
  CopilotChatResponse,
  CopilotConversation,
  CopilotConversationDetail,
} from "@/types/copilot";

export const copilotService = {
  chat: (message: string, conversationId?: number | null) =>
    api.post<CopilotChatResponse>("/api/v1/copilot/chat", {
      message,
      conversation_id: conversationId ?? null,
    }),

  confirm: (token: string) =>
    api.post<CopilotChatResponse>("/api/v1/copilot/confirm", { token }),

  listConversations: () =>
    api.get<CopilotConversation[]>("/api/v1/copilot/conversations"),

  getConversation: (id: number) =>
    api.get<CopilotConversationDetail>(`/api/v1/copilot/conversations/${id}`),
};