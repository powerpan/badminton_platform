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
  status: "available" | "reserved" | "locked" | "disabled";
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
