/**
 * Authentication API hooks and functions.
 */
import { apiClient } from '../api-client';

export interface SignupData {
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginData {
  email: string;
  password: string;
  mfa_code?: string;
}

export interface User {
  id: string;
  email: string;
  full_name?: string;
  email_verified: boolean;
  mfa_enabled: boolean;
  role: string;
  paper_trading_approved: boolean;
  live_trading_approved: boolean;
  preferences: Record<string, any>;
  created_at: string;
  last_login_at?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  requires_mfa: boolean;
}

export interface SignupResponse {
  user: User;
  message: string;
}

export interface MessageResponse {
  message: string;
  success: boolean;
}

export interface MFAEnableResponse {
  secret: string;
  qr_code_uri: string;
  backup_codes: string[];
  message: string;
}

export interface MFAStatusResponse {
  mfa_enabled: boolean;
  backup_codes_remaining: number;
}

export interface SessionInfo {
  id: string;
  device_info: {
    ip_address?: string;
    user_agent?: string;
    device_name?: string;
  };
  last_used_at: string;
  created_at: string;
  is_current: boolean;
}

export interface SessionListResponse {
  sessions: SessionInfo[];
}

// ============================================================================
// Auth API Functions
// ============================================================================

export async function signup(data: SignupData): Promise<SignupResponse> {
  const response = await apiClient.post('/auth/register', data);
  return response.data;
}

export async function login(data: LoginData): Promise<LoginResponse> {
  const response = await apiClient.post('/auth/login', data);

  // Store access token in localStorage
  if (response.data.access_token) {
    localStorage.setItem('access_token', response.data.access_token);
  }

  return response.data;
}

export async function verifyMFA(email: string, mfa_code: string): Promise<LoginResponse> {
  const response = await apiClient.post('/auth/mfa/verify', null, {
    params: { email, mfa_code },
  });

  if (response.data.access_token) {
    localStorage.setItem('access_token', response.data.access_token);
  }

  return response.data;
}

export async function logout(): Promise<MessageResponse> {
  const response = await apiClient.post('/auth/logout');
  localStorage.removeItem('access_token');
  return response.data;
}

export async function refreshToken(): Promise<{ access_token: string; expires_in: number }> {
  const response = await apiClient.post('/auth/refresh');
  if (response.data.access_token) {
    localStorage.setItem('access_token', response.data.access_token);
  }
  return response.data;
}

export async function getCurrentUser(): Promise<User> {
  const response = await apiClient.get('/auth/me');
  return response.data;
}

export async function verifyEmail(token: string): Promise<MessageResponse> {
  const response = await apiClient.post('/auth/verify-email', { token });
  return response.data;
}

export async function forgotPassword(email: string): Promise<MessageResponse> {
  const response = await apiClient.post('/auth/forgot-password', { email });
  return response.data;
}

export async function resetPassword(token: string, new_password: string): Promise<MessageResponse> {
  const response = await apiClient.post('/auth/reset-password', {
    token,
    new_password,
  });
  return response.data;
}

export async function changePassword(
  current_password: string,
  new_password: string
): Promise<MessageResponse> {
  const response = await apiClient.post('/auth/change-password', {
    current_password,
    new_password,
  });
  return response.data;
}

// ============================================================================
// MFA Functions
// ============================================================================

export async function enableMFA(password: string): Promise<MFAEnableResponse> {
  const response = await apiClient.post('/auth/mfa/enable', { password });
  return response.data;
}

export async function confirmMFA(code: string): Promise<MessageResponse> {
  const response = await apiClient.post('/auth/mfa/confirm', { code });
  return response.data;
}

export async function disableMFA(password: string, code: string): Promise<MessageResponse> {
  const response = await apiClient.post('/auth/mfa/disable', { password, code });
  return response.data;
}

export async function getMFAStatus(): Promise<MFAStatusResponse> {
  const response = await apiClient.get('/auth/mfa/status');
  return response.data;
}

// ============================================================================
// Session Management
// ============================================================================

export async function getSessions(): Promise<SessionListResponse> {
  const response = await apiClient.get('/auth/sessions');
  return response.data;
}

export async function revokeSession(sessionId: string): Promise<MessageResponse> {
  const response = await apiClient.post(`/auth/sessions/${sessionId}/revoke`);
  return response.data;
}
