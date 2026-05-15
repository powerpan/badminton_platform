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

export interface StatisticsOverview {
  date_from: string;
  date_to: string;
  total_users: number;
  enabled_users: number;
  admin_users: number;
  total_courts: number;
  enabled_courts: number;
  reservation_total: number;
  today_reservations: number;
  active_users: number;
  pending_reservations: number;
  confirmed_reservations: number;
  completed_reservations: number;
  canceled_reservations: number;
  expired_reservations: number;
  capacity_slots: number;
  occupied_slots: number;
  utilization_rate: number;
}

export interface CourtStatistic {
  court_id: number;
  court_no: string;
  court_name: string;
  status: number;
  reservation_count: number;
  active_count: number;
  booked_hours: number;
  capacity_slots: number;
  usage_rate: number;
}

export interface TimeSlotStatistic {
  time_slot: string;
  start_time: string;
  end_time: string;
  reservation_count: number;
}

export interface UserStatistic {
  user_id: number;
  username: string;
  nickname: string;
  reservation_count: number;
  confirmed_count: number;
  completed_count: number;
  canceled_count: number;
  last_reserve_date: string;
}

export interface StatisticsList<T> {
  date_from: string;
  date_to: string;
  items: T[];
}

export interface OperationLog {
  id: number;
  user_id: number | null;
  username: string | null;
  role: string | null;
  module: string;
  action: string;
  target_type: string | null;
  target_id: number | null;
  detail: string;
  ip: string | null;
  created_at: string;
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

export function adminUpdateUserMember(userId: number, payload: {
  member_level: string;
  expires_at: string | null;
  balance_change_cents: number;
  points_change: number;
  reason: string;
}) {
  return http.put<unknown, ApiResponse<UserInfo>>(`/admin/users/${userId}/member`, payload);
}

export function adminResetUserPassword(userId: number, password: string) {
  return http.put<unknown, ApiResponse<UserInfo>>(`/admin/users/${userId}/password`, { password });
}

export function adminGetCourts(params: { status?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<Court>>>("/admin/courts", { params });
}

export function adminCreateCourt(payload: {
  court_no: string;
  court_name: string;
  description: string;
  status: number;
  price_per_hour_cents: number;
  image_url: string;
  tags: string[];
  capacity: number;
}) {
  return http.post<unknown, ApiResponse<Court>>("/admin/courts", payload);
}

export function adminUpdateCourt(courtId: number, payload: {
  court_no: string;
  court_name: string;
  description: string;
  status: number;
  price_per_hour_cents: number;
  image_url: string;
  tags: string[];
  capacity: number;
}) {
  return http.put<unknown, ApiResponse<Court>>(`/admin/courts/${courtId}`, payload);
}

export function adminUpdateCourtStatus(courtId: number, status: number) {
  return http.put<unknown, ApiResponse<Court>>(`/admin/courts/${courtId}/status`, { status });
}

export function adminGetReservations(params: {
  status?: string;
  username?: string;
  court_id?: number;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
} = {}) {
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

export function adminGetStatisticsOverview(params: { date_from?: string; date_to?: string } = {}) {
  return http.get<unknown, ApiResponse<StatisticsOverview>>("/admin/statistics/overview", { params });
}

export function adminGetCourtStatistics(params: { date_from?: string; date_to?: string } = {}) {
  return http.get<unknown, ApiResponse<StatisticsList<CourtStatistic>>>("/admin/statistics/courts", { params });
}

export function adminGetTimeSlotStatistics(params: { date_from?: string; date_to?: string; limit?: number } = {}) {
  return http.get<unknown, ApiResponse<StatisticsList<TimeSlotStatistic>>>("/admin/statistics/time-slots", { params });
}

export function adminGetUserStatistics(params: { date_from?: string; date_to?: string; limit?: number } = {}) {
  return http.get<unknown, ApiResponse<StatisticsList<UserStatistic>>>("/admin/statistics/users", { params });
}

export function adminGetOperationLogs(params: {
  module?: string;
  action?: string;
  username?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
} = {}) {
  return http.get<unknown, ApiResponse<PageResult<OperationLog>>>("/admin/logs", { params });
}
