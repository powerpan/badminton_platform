import { http } from "./http";
import type { Announcement } from "./announcement";
import type { ApiResponse, UserInfo } from "./auth";
import type { Court, PageResult } from "./court";
import type { Reservation } from "./reservation";

export interface ConfigItem {
  id: number;
  config_key: string;
  config_value: string;
  description: string;
  updated_by: number | null;
  created_at: string;
  updated_at: string;
}

export function adminGetUsers(params: { role?: string; status?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<UserInfo>>>("/admin/users", { params });
}

export function adminCreateUser(payload: {
  username: string;
  password: string;
  nickname: string;
  contact: string;
  role: string;
  status: number;
}) {
  return http.post<unknown, ApiResponse<UserInfo>>("/admin/users", payload);
}

export function adminUpdateUserStatus(userId: number, status: number) {
  return http.put<unknown, ApiResponse<UserInfo>>(`/admin/users/${userId}/status`, { status });
}

export function adminUpdateUserRole(userId: number, role: string) {
  return http.put<unknown, ApiResponse<UserInfo>>(`/admin/users/${userId}/role`, { role });
}

export function adminGetCourts(params: { status?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<Court>>>("/admin/courts", { params });
}

export function adminCreateCourt(payload: {
  court_no: string;
  court_name: string;
  description: string;
  status: number;
}) {
  return http.post<unknown, ApiResponse<Court>>("/admin/courts", payload);
}

export function adminUpdateCourt(courtId: number, payload: {
  court_no: string;
  court_name: string;
  description: string;
  status: number;
}) {
  return http.put<unknown, ApiResponse<Court>>(`/admin/courts/${courtId}`, payload);
}

export function adminUpdateCourtStatus(courtId: number, status: number) {
  return http.put<unknown, ApiResponse<Court>>(`/admin/courts/${courtId}/status`, { status });
}

export function adminGetReservations(params: { status?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<Reservation>>>("/admin/reservations", { params });
}

export function adminCancelReservation(reservationId: number) {
  return http.put<unknown, ApiResponse<Reservation>>(`/admin/reservations/${reservationId}/cancel`);
}

export function adminGetAnnouncements(params: { status?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<Announcement>>>("/admin/announcements", { params });
}

export function adminCreateAnnouncement(payload: { title: string; content: string; status: number }) {
  return http.post<unknown, ApiResponse<Announcement>>("/admin/announcements", payload);
}

export function adminUpdateAnnouncement(announcementId: number, payload: {
  title: string;
  content: string;
  status: number;
}) {
  return http.put<unknown, ApiResponse<Announcement>>(`/admin/announcements/${announcementId}`, payload);
}

export function adminUpdateAnnouncementStatus(announcementId: number, status: number) {
  return http.put<unknown, ApiResponse<Announcement>>(`/admin/announcements/${announcementId}/status`, { status });
}

export function adminGetConfigs() {
  return http.get<unknown, ApiResponse<ConfigItem[]>>("/admin/configs");
}

export function adminUpdateConfig(configKey: string, configValue: string) {
  return http.put<unknown, ApiResponse<ConfigItem>>(`/admin/configs/${configKey}`, { config_value: configValue });
}
