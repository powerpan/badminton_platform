import { http } from "./http";
import type { ApiResponse } from "./auth";
import type { PageResult } from "./court";

export interface NotificationItem {
  id: number;
  title: string;
  content: string;
  category: "system" | "reservation" | "member" | "announcement";
  source_type: string | null;
  source_id: number | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface UnreadCountResult {
  unread_count: number;
}

export interface MarkAllReadResult {
  updated_count: number;
}

export function getNotifications(params: { is_read?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<NotificationItem>>>("/notifications", { params });
}

export function getUnreadCount() {
  return http.get<unknown, ApiResponse<UnreadCountResult>>("/notifications/unread-count");
}

export function markNotificationRead(notificationId: number) {
  return http.put<unknown, ApiResponse<NotificationItem>>(`/notifications/${notificationId}/read`);
}

export function markAllNotificationsRead() {
  return http.put<unknown, ApiResponse<MarkAllReadResult>>("/notifications/read-all");
}
