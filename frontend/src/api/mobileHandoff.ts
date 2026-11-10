import axios from 'axios';
import { http, ApiRequestError } from './http';
import type { ApiResponse, LoginResult } from './auth';
export interface Handoff {
  id: string; order_id: number; user_id: number; username: string; expires_at: number;
  status: 'waiting' | 'claimed' | 'approved' | 'issuing' | 'consumed' | 'denied' | 'failed';
  pairing_code: string | null; qr_data_url?: string; mobile_url?: string; login?: LoginResult;
}
export const createHandoff = (order_id: number) => http.post<unknown, ApiResponse<Handoff>>('/auth/mobile-handoffs', { order_id });
export const getHandoff = (id: string) => http.get<unknown, ApiResponse<Handoff>>(`/auth/mobile-handoffs/${id}`);
export const decideHandoff = (id: string, decision: 'approve' | 'deny' | 'cancel', pairing_code?: string | null) =>
  http.post<unknown, ApiResponse<Handoff>>(`/auth/mobile-handoffs/${id}/decision`, { decision, pairing_code });
// A public exchange must never attach, refresh or erase another account's existing session.
const phone = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '/api', timeout: 10000 });
async function phoneRequest(id: string, action: string, body: object): Promise<Handoff> {
  try { return (await phone.post<ApiResponse<Handoff>>(`/auth/mobile-handoffs/${id}/${action}`, body)).data.data; }
  catch (error) {
    if (axios.isAxiosError(error)) throw new ApiRequestError(error.response?.data?.message || '网络暂时不可用，请重试', error.response?.status);
    throw error;
  }
}
export const claimHandoff = (id: string, ticket: string, device_secret: string) => phoneRequest(id, 'claim', { ticket, device_secret });
export const exchangeHandoff = (id: string, device_secret: string) => phoneRequest(id, 'exchange', { device_secret });
