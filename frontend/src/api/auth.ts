import { http } from "./http";

export type UserRole = "user" | "admin" | "frontdesk" | "maintenance";

export interface MemberInfo {
  level: "normal" | "silver" | "gold" | "diamond";
  level_label: string;
  balance_cents: number;
  points: number;
  expires_at: string | null;
  discount_rate: number;
  effective_level: "normal" | "silver" | "gold" | "diamond";
  effective_discount_rate: number;
}

export interface UserInfo {
  id: number;
  username: string;
  nickname: string;
  role: UserRole;
  contact: string;
  status: number;
  member: MemberInfo;
  must_change_password?: boolean;
}

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface LoginResult {
  token: string;
  access_token: string;
  refresh_token: string;
  user: UserInfo;
}

export interface CaptchaResult {
  captcha_id: string;
  image_data: string;
  expires_in: number;
}

export interface PasswordResetRequestResult {
  reset_token: string;
  expires_in: number;
}

export function getCaptcha() {
  return http.get<unknown, ApiResponse<CaptchaResult>>("/auth/captcha");
}

export function register(payload: {
  username: string;
  password: string;
  nickname: string;
  contact: string;
  captcha_id: string;
  captcha_code: string;
}) {
  return http.post<unknown, ApiResponse<UserInfo>>("/auth/register", payload);
}

export function login(payload: { username: string; password: string; captcha_id: string; captcha_code: string }) {
  return http.post<unknown, ApiResponse<LoginResult>>("/auth/login", payload);
}

export function refreshLogin(payload: { refresh_token: string }) {
  return http.post<unknown, ApiResponse<LoginResult>>("/auth/refresh", payload);
}

export function logout(payload: { refresh_token: string }) {
  return http.post<unknown, ApiResponse<null>>("/auth/logout", payload);
}

export function requestPasswordReset(payload: {
  username: string;
  contact: string;
  captcha_id: string;
  captcha_code: string;
}) {
  return http.post<unknown, ApiResponse<PasswordResetRequestResult>>("/auth/password-reset/request", payload);
}

export function confirmPasswordReset(payload: { reset_token: string; new_password: string }) {
  return http.post<unknown, ApiResponse<null>>("/auth/password-reset/confirm", payload);
}

export function getProfile() {
  return http.get<unknown, ApiResponse<UserInfo>>("/auth/profile");
}

export function updateProfile(payload: { nickname: string; contact: string }) {
  return http.put<unknown, ApiResponse<UserInfo>>("/auth/profile", payload);
}

export function changePassword(payload: { old_password: string; new_password: string }) {
  return http.put<unknown, ApiResponse<null>>("/auth/password", payload);
}
