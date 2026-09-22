import { http } from './http';
import type { ApiResponse } from './auth';
import type { Reservation } from './reservation';

export interface BookingTarget { court_id: number; reserve_date: string; start_time: string; end_time: string }
export interface Recommendation extends BookingTarget { court_no: string; court_name: string; payable_amount_cents: number; reasons: string[] }
export interface RescheduleQuote { target: BookingTarget; revision: number; court_name: string; payable_amount_cents: number; old_amount_cents: number; difference_cents: number; discount_rate: number }
export interface CourtBlock extends BookingTarget { id: number; court_no: string; court_name: string; reason: string; status: 'active' | 'released' }
export interface BookingSnapshot extends BookingTarget { court_no?: string; court_name?: string }
export interface ReservationChange { id: number; before_snapshot: BookingSnapshot; after_snapshot: BookingSnapshot; balance_change_cents: number; created_at: string }
export interface OperationsReport {
  date_from: string; date_to: string; generated_at: string;
  total: number; canceled: number; cancellation_rate: number | null;
  ended: number; checked_in: number; no_show: number; unrecorded: number; attendance_rate: number | null; attendance_coverage: number | null;
  charges_cents: number; refunds_cents: number; net_cents: number; ledger_count: number;
  reconciliation: { orders: number; mismatches: number };
  daily: { date: string; total: number; active: number; canceled: number; booked_minutes: number }[];
  hourly: { hour: number; label: string; booked_minutes: number }[];
}
export const getRecommendations = (payload: { reserve_date: string; earliest_time: string; duration_minutes: number; preferred_court_id?: number }) =>
  http.post<unknown, ApiResponse<{ items: Recommendation[] }>>('/reservations/recommendations', payload);
export const getRescheduleQuote = (id: number, payload: BookingTarget) => http.post<unknown, ApiResponse<RescheduleQuote>>(`/reservations/${id}/reschedule/quote`, payload);
export const rescheduleReservation = (id: number, payload: BookingTarget & { expected_revision: number; expected_amount_cents: number; request_key: string }) =>
  http.put<unknown, ApiResponse<Reservation>>(`/reservations/${id}/reschedule`, payload);
export const getReservationChanges = (id: number) => http.get<unknown, ApiResponse<{ items: ReservationChange[] }>>(`/reservations/${id}/changes`);
export const getCourtBlocks = (params: { date_from: string; date_to: string }) => http.get<unknown, ApiResponse<{ items: CourtBlock[] }>>('/admin/court-blocks', { params });
export const createCourtBlock = (payload: BookingTarget & { reason: string }) => http.post<unknown, ApiResponse<{ id: number }>>('/admin/court-blocks', payload);
export const releaseCourtBlock = (id: number) => http.put(`/admin/court-blocks/${id}/release`);
export const recordAttendance = (id: number, outcome: 'checked_in' | 'no_show') => http.put<unknown, ApiResponse<Reservation>>(`/admin/reservations/${id}/attendance`, { outcome });
export const getOperationsReport = (params: { date_from: string; date_to: string }) => http.get<unknown, ApiResponse<OperationsReport>>('/admin/statistics/operations', { params });
