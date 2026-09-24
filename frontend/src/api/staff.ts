import { http } from './http';
import type { ApiResponse } from './auth';
import type { CourtSlots, PageResult, ReservationRules } from './court';
import type { BookingTarget } from './operations';
import type { Reservation } from './reservation';

export interface StaffPayment {
  id: number; payment_no: string; amount_cents: number;
  status: 'pending' | 'succeeded' | 'canceled' | 'expired' | 'refunded';
  pay_method: 'mock_alipay'; is_simulated: true; expires_at: string; paid_at: string | null;
}
export interface WalkIn extends Reservation {
  payment: StaffPayment; server_now: string;
  chain?: Pick<WalkIn, 'id' | 'parent_reservation_id' | 'start_time' | 'end_time' | 'status'>[];
}
export interface WalkInQuote extends BookingTarget {
  court_name: string; payable_amount_cents: number; expires_at: string; server_now: string;
}
export type WalkInDraft = Partial<BookingTarget> & { end_time: string; guest_name?: string; guest_contact?: string; expected_amount_cents: number; request_key: string };
export const getStaffSchedule = (date: string) => http.get<unknown, ApiResponse<{ items: CourtSlots[]; rules: ReservationRules; server_now: string }>>('/frontdesk/court-slots', { params: { date } });
export const getWalkIns = (params: { date: string; status?: string; court_id?: number; order_no?: string; page: number; page_size: number }) => http.get<unknown, ApiResponse<PageResult<WalkIn>>>('/frontdesk/walk-ins', { params });
export const getWalkIn = (id: number) => http.get<unknown, ApiResponse<WalkIn>>(`/frontdesk/walk-ins/${id}`);
export const quoteWalkIn = (body: Partial<BookingTarget>, parent?: number) => http.post<unknown, ApiResponse<WalkInQuote>>(parent ? `/frontdesk/walk-ins/${parent}/extensions/quote` : '/frontdesk/walk-ins/quote', body);
export const createWalkIn = (body: WalkInDraft, parent?: number) => http.post<unknown, ApiResponse<WalkIn>>(parent ? `/frontdesk/walk-ins/${parent}/extensions` : '/frontdesk/walk-ins', body);
export const cancelWalkIn = (id: number, request_key: string) => http.post<unknown, ApiResponse<WalkIn>>(`/frontdesk/walk-ins/${id}/cancel`, { request_key, reason: '前台撤销未付款订场' });
export const mockCollect = (id: number, action: 'confirm' | 'fail', request_key: string) => http.post<unknown, ApiResponse<WalkIn>>(`/payments/${id}/mock-${action}`, { request_key });
