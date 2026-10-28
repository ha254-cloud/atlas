export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: "owner" | "admin" | "biller" | "auditor" | "viewer" | "manager" | "revenue_analyst" | "appeals_specialist";
  organization_id: number;
  is_active: boolean;
  is_superuser: boolean;
  email_verified?: boolean;
}

export interface TokenResponse {
  access_token: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  organization_name: string;
  organization_type?: string;
  country?: string;
  first_name: string;
  last_name: string;
  email: string;
  password: string;
}

export interface RegisterResponse {
  organization_id: number;
  user_id: number;
  message: string;
}

export interface VerifyEmailRequest {
  token: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  password: string;
}

export interface MessageResponse {
  message: string;
}

export interface InviteRequest {
  email: string;
  role: User["role"];
}

export interface InviteResponse {
  invitation_id: number;
  email: string;
  role: User["role"];
  message: string;
}

export interface AcceptInviteRequest {
  token: string;
  first_name: string;
  last_name: string;
  password: string;
}
