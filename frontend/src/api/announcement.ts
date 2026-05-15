import { http } from "./http";
import type { ApiResponse } from "./auth";
import type { PageResult } from "./court";

export interface Announcement {
  id: number;
  title: string;
  content: string;
  status: number;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export function getAnnouncements(params: { page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<Announcement>>>("/announcements", { params });
}
