import { http } from "./http";
import type { ApiResponse } from "./auth";
import type { PageResult } from "./court";
import type { Payment, PaymentMethod } from './payment';

export type ReservationStatus = "pending" | "confirmed" | "canceled" | "expired" | "completed";

export interface Reservation {
  id: number;
  revision?: number;
  attendance_outcome?: 'checked_in' | 'no_show' | null;
  attendance_recorded_at?: string | null;
  attendance_recorded_by?: number | null;
  reservation_no: string;
  user_id?: number | null;
  source?: 'online' | 'walk_in' | 'walk_in_extension';
  guest_name?: string | null;
  guest_contact?: string | null;
  operator_name_snapshot?: string | null;
  opened_at?: string | null;
  parent_reservation_id?: number | null;
  root_reservation_id?: number | null;
  username?: string;
  nickname?: string;
  court_id: number;
  court_no: string;
  court_name: string;
  reserve_date: string;
  start_time: string;
  end_time: string;
  time_slot: string;
  status: ReservationStatus;
  remark: string;
  price_per_hour_cents: number;
  duration_minutes: number;
  original_amount_cents: number;
  discount_amount_cents: number;
  payable_amount_cents: number;
  member_level_snapshot: string;
  discount_rate: number;
  points_awarded: number;
  order_id?: number | null;
  payment_id?: number | null;
  reschedule_payment_id?: number | null;
  payment?: Pick<Payment, 'id' | 'payment_no' | 'amount_cents' | 'pay_method' | 'status' | 'expires_at' | 'paid_at'>;
  requires_payment?: boolean;
  order_no?: string | null;
  order_status?: "pending" | "paid" | "canceled" | "expired" | null;
  order_amount_cents?: number | null;
  order_pay_method?: string | null;
  order_expires_at?: string | null;
  order_paid_at?: string | null;
  order_canceled_at?: string | null;
  created_at: string;
  updated_at?: string;
  canceled_at?: string | null;
}

export function createReservation(payload: {
  court_id: number;
  reserve_date: string;
  start_time: string;
  end_time: string;
  remark?: string;
  expected_amount_cents: number;
  pay_method?: PaymentMethod;
  request_key?: string;
}) {
  return http.post<unknown, ApiResponse<Reservation>>("/reservations", payload);
}

export function getMyReservations(params: { status?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<Reservation>>>("/reservations/my", { params });
}

export interface ReservationSummary {
  upcoming: Reservation | null;
  pending: Reservation | null;
  pending_count: number;
}

export function getReservationSummary() {
  return http.get<unknown, ApiResponse<ReservationSummary>>("/reservations/summary");
}

export function cancelReservation(reservationId: number) {
  return http.put<unknown, ApiResponse<Reservation>>(`/reservations/${reservationId}/cancel`);
}

export function payReservationOrder(orderId: number) {
  return http.put<unknown, ApiResponse<Reservation>>(`/reservation-orders/${orderId}/pay`);
}

export function getReservation(reservationId: number) {
  return http.get<unknown, ApiResponse<Reservation>>(`/reservations/${reservationId}`);
}
