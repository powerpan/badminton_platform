import { http } from "./http";
import type { ApiResponse } from "./auth";
import type { PageResult } from "./court";

export interface CommunityPost {
  id: number;
  user_id: number;
  username: string;
  nickname: string | null;
  content: string;
  status: number;
  created_at: string;
  updated_at: string;
}

export function getCommunityPosts(params: { page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<CommunityPost>>>("/community/posts", { params });
}

export function createCommunityPost(payload: { content: string }) {
  return http.post<unknown, ApiResponse<CommunityPost>>("/community/posts", payload);
}

export function hideCommunityPost(postId: number) {
  return http.put<unknown, ApiResponse<CommunityPost>>(`/community/posts/${postId}/hide`);
}
