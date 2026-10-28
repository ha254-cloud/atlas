import { api } from "@/lib/api-client";
import { setToken, clearToken } from "@/lib/auth";
import type {
  User,
  TokenResponse,
  LoginRequest,
  RegisterRequest,
  RegisterResponse,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  MessageResponse,
  InviteRequest,
  InviteResponse,
  AcceptInviteRequest,
} from "@/types";

export const authService = {
  async login(credentials: LoginRequest): Promise<TokenResponse> {
    const data = await api.post<TokenResponse>("/api/v1/auth/login", credentials);
    setToken(data.access_token);
    return data;
  },
  me(): Promise<User> {
    return api.get<User>("/api/v1/auth/me");
  },
  async logout(): Promise<void> {
    try {
      await api.post<MessageResponse>("/api/v1/auth/logout");
    } finally {
      clearToken();
    }
  },
  register(data: RegisterRequest): Promise<RegisterResponse> {
    return api.post<RegisterResponse>("/api/v1/auth/register", data);
  },
  verifyEmail(token: string): Promise<MessageResponse> {
    return api.post<MessageResponse>("/api/v1/auth/verify-email", { token });
  },
  forgotPassword(data: ForgotPasswordRequest): Promise<MessageResponse> {
    return api.post<MessageResponse>("/api/v1/auth/forgot-password", data);
  },
  resetPassword(data: ResetPasswordRequest): Promise<MessageResponse> {
    return api.post<MessageResponse>("/api/v1/auth/reset-password", data);
  },
  inviteUser(data: InviteRequest): Promise<InviteResponse> {
    return api.post<InviteResponse>("/api/v1/users/invite", data);
  },
  async acceptInvite(data: AcceptInviteRequest): Promise<TokenResponse> {
    const result = await api.post<TokenResponse>("/api/v1/users/accept-invite", data);
    setToken(result.access_token);
    return result;
  },
  listMembers(): Promise<User[]> {
    return api.get<User[]>("/api/v1/users");
  },
};
