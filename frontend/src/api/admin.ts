import { http } from "./http";
import type { Announcement } from "./announcement";
import type { ApiResponse, UserInfo } from "./auth";
import type { CommunityPost } from "./community";
import type { Court, PageResult } from "./court";
import type { ClubEvent } from "./event";
import type { Reservation } from "./reservation";
import type { ShopOrder, ShopProduct } from "./shop";

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

export interface BroadcastNotificationResult {
  sent_count: number;
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
  source?: string;
  pay_method?: string;
  operator?: string;
  order_no?: string;
  court_id?: number;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
} = {}) {
  return http.get<unknown, ApiResponse<PageResult<Reservation> & { server_now: string }>>("/admin/reservations", { params });
}

export interface AdminBookingDetail extends Reservation {
  customer_contact?: string | null;
  server_now: string;
  chain: Array<Pick<Reservation, 'id' | 'reservation_no' | 'source' | 'parent_reservation_id' | 'reserve_date' | 'start_time' | 'end_time' | 'court_no' | 'court_name' | 'status' | 'payable_amount_cents'>>;
  payments: Array<{
    id: number; payment_no: string; purpose: string; amount_cents: number; pay_method: string; status: string;
    created_at: string; expires_at: string; paid_at: string | null; closed_at: string | null;
    operator_id: number; operator_name_snapshot: string; collected_by: number | null;
    collector_username: string | null; collection_recorded_at: string | null; refunded_cents: number;
  }>;
  refunds: Array<{
    id: number; refund_no: string; payment_order_id: number; payment_no: string; pay_method: string;
    refund_group_no: string; amount_cents: number; reason: string; purpose: string; status: string;
    operator_id: number; operator_name_snapshot: string; refunded_at: string;
  }>;
  account_transactions: Array<{
    id: number; transaction_type: string; balance_change_cents: number; balance_before_cents: number;
    balance_after_cents: number; points_change: number; reason: string; operator_id: number | null;
    operator_username: string | null; payment_order_id: number | null; payment_refund_id: number | null; created_at: string;
  }>;
  changes: import('./operations').ReservationChange[];
}

export function adminGetReservation(reservationId: number) {
  return http.get<unknown, ApiResponse<AdminBookingDetail>>(`/admin/reservations/${reservationId}`);
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

export function adminBroadcastNotification(payload: { title: string; content: string }) {
  return http.post<unknown, ApiResponse<BroadcastNotificationResult>>("/admin/notifications/broadcast", payload);
}

export function adminGetEvents(params: { status?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<ClubEvent>>>("/admin/events", { params });
}

export function adminCreateEvent(payload: {
  title: string;
  content: string;
  location: string;
  start_at: string;
  end_at: string;
  registration_deadline: string;
  capacity: number;
  status: number;
}) {
  return http.post<unknown, ApiResponse<ClubEvent>>("/admin/events", payload);
}

export function adminUpdateEvent(eventId: number, payload: {
  title: string;
  content: string;
  location: string;
  start_at: string;
  end_at: string;
  registration_deadline: string;
  capacity: number;
  status: number;
}) {
  return http.put<unknown, ApiResponse<ClubEvent>>(`/admin/events/${eventId}`, payload);
}

export function adminUpdateEventStatus(eventId: number, status: number) {
  return http.put<unknown, ApiResponse<ClubEvent>>(`/admin/events/${eventId}/status`, { status });
}

export function adminGetCommunityPosts(params: { status?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<CommunityPost>>>("/admin/community/posts", { params });
}

export function adminHideCommunityPost(postId: number) {
  return http.put<unknown, ApiResponse<CommunityPost>>(`/admin/community/posts/${postId}/hide`);
}

export function adminGetShopProducts(params: {
  status?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
} = {}) {
  return http.get<unknown, ApiResponse<PageResult<ShopProduct>>>("/admin/shop/products", { params });
}

export function adminCreateShopProduct(payload: {
  product_no: string;
  product_name: string;
  description: string;
  image_url: string;
  price_cents: number;
  stock: number;
  status: number;
}) {
  return http.post<unknown, ApiResponse<ShopProduct>>("/admin/shop/products", payload);
}

export function adminUpdateShopProduct(productId: number, payload: {
  product_no: string;
  product_name: string;
  description: string;
  image_url: string;
  price_cents: number;
  stock: number;
  status: number;
}) {
  return http.put<unknown, ApiResponse<ShopProduct>>(`/admin/shop/products/${productId}`, payload);
}

export function adminUpdateShopProductStatus(productId: number, status: number) {
  return http.put<unknown, ApiResponse<ShopProduct>>(`/admin/shop/products/${productId}/status`, { status });
}

export function adminGetShopOrders(params: {
  status?: string;
  username?: string;
  page?: number;
  page_size?: number;
} = {}) {
  return http.get<unknown, ApiResponse<PageResult<ShopOrder>>>("/admin/shop/orders", { params });
}

export function adminGetShopOrder(orderId: number) {
  return http.get<unknown, ApiResponse<ShopOrder>>(`/admin/shop/orders/${orderId}`);
}

export function adminCompleteShopOrder(orderId: number, payload?: { request_key: string }) {
  return http.put<unknown, ApiResponse<ShopOrder>>(`/admin/shop/orders/${orderId}/complete`, payload);
}

export function adminCancelShopOrder(orderId: number, payload?: { request_key: string; reason?: string }) {
  return http.put<unknown, ApiResponse<ShopOrder>>(`/admin/shop/orders/${orderId}/cancel`, payload);
}

export function adminRejectShopOrderRefund(orderId: number, payload: { reason: string; request_key?: string }) {
  return http.put<unknown, ApiResponse<ShopOrder>>(`/admin/shop/orders/${orderId}/refund-reject`, payload);
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
