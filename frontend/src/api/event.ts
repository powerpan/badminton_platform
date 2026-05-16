import { http } from "./http";
import type { ApiResponse } from "./auth";
import type { PageResult } from "./court";

export interface ClubEvent {
  id: number;
  title: string;
  content: string;
  location: string;
  start_at: string;
  end_at: string;
  registration_deadline: string;
  capacity: number;
  registered_count: number;
  status: number;
  is_registered: boolean;
  can_register: boolean;
  created_at: string;
  updated_at: string;
}

export function getEvents(params: { page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<ClubEvent>>>("/events", { params });
}

export function getEvent(eventId: number) {
  return http.get<unknown, ApiResponse<ClubEvent>>(`/events/${eventId}`);
}

export function registerEvent(eventId: number) {
  return http.post<unknown, ApiResponse<ClubEvent>>(`/events/${eventId}/register`);
}

export function cancelEventRegistration(eventId: number) {
  return http.put<unknown, ApiResponse<ClubEvent>>(`/events/${eventId}/cancel-registration`);
}
