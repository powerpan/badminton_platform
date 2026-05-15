import { http } from "./http";

export interface UserInfo {
  id: number;
  username: string;
  nickname: string;
  role: "user" | "admin";
  contact: string;
  status: number;
}

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface LoginResult {
  token: string;
  user: UserInfo;
}

export function register(payload: {
  username: string;
  password: string;
  nickname: string;
  contact: string;
}) {
  return http.post<unknown, ApiResponse<UserInfo>>("/auth/register", payload);
}

export function login(payload: { username: string; password: string }) {
  return http.post<unknown, ApiResponse<LoginResult>>("/auth/login", payload);
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
