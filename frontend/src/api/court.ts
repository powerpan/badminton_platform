import { http } from "./http";
import type { ApiResponse } from "./auth";

export interface PageResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Court {
  id: number;
  court_no: string;
  court_name: string;
  description: string;
  status: number;
  price_per_hour_cents: number;
  image_url: string;
  tags: string[];
  capacity: number;
  created_at: string;
  updated_at: string;
}

export interface SlotItem {
  start_time: string;
  end_time: string;
  status: "available" | "reserved" | "locked" | "disabled" | "maintenance";
  unavailable_reason?: string | null;
  price_cents: number;
}

export interface ReservationRules {
  business_start_time: string;
  business_end_time: string;
  slot_interval_minutes: number;
  max_reservation_minutes: number;
  daily_reservation_limit: number;
  payment_timeout_minutes: number;
  min_date: string;
  max_date: string;
  server_now: string;
}

export interface BookingBalance {
  balance_cents: number;
  pending_amount_cents: number;
  available_balance_cents: number;
}

export function getReservationRules() {
  return http.get<unknown, ApiResponse<ReservationRules>>("/courts/rules");
}

export function getVenueInfo() {
  return http.get<unknown, ApiResponse<Pick<ReservationRules, "business_start_time" | "business_end_time">>>("/venue");
}

export function getBookingBalance() {
  return http.get<unknown, ApiResponse<BookingBalance>>("/member/booking-balance");
}

export interface CourtSlots {
  court_id: number;
  court: Court;
  date: string;
  slots: SlotItem[];
}

export function getCourts(params: { status?: number; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<Court>>>("/courts", { params });
}

export function getCourtSlots(courtId: number, date: string) {
  return http.get<unknown, ApiResponse<CourtSlots>>(`/courts/${courtId}/slots`, { params: { date } });
}

// Administrative drawers must offer the same complete list as the booking page.
export async function getAllCourts(status?: number): Promise<Court[]> {
  const first = await getCourts({ status, page_size: 100 });
  const items = [...first.data.items];
  for (let page = 2; items.length < first.data.total; page++) {
    const response = await getCourts({ status, page, page_size: 100 });
    if (!response.data.items.length) break;
    items.push(...response.data.items);
  }
  return items;
}
