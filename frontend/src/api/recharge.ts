import { http } from './http';
import type { ApiResponse } from './auth';
import type { PageResult } from './court';
export interface RechargeCustomer { id: number; username: string; nickname: string | null; contact_masked: string; balance_cents?: number }
export interface RechargeCredit { id: number; balance_before_cents: number; balance_after_cents: number; operator_id: number; operator_username: string; created_at: string }
export interface RechargeOrder {
  id: number; recharge_no: string; user_id: number; amount_cents: number; status: 'pending' | 'paid' | 'canceled' | 'expired';
  expires_at: string; paid_at: string | null; canceled_at: string | null; created_at: string; server_now?: string;
  operator_id: number; operator_name_snapshot: string; customer: RechargeCustomer;
  payment_id: number; payment_no: string; pay_method: 'mock_alipay'; payment_status: string; credit?: RechargeCredit | null;
}
export interface RechargeDraft { user_id: number; amount_cents: number; request_key: string }
export interface RechargeFilters { date_from?: string; date_to?: string; status?: string; order_no?: string; page?: number; page_size?: number }
export const findRechargeCustomers = (query: string) => http.get<unknown, ApiResponse<{items: RechargeCustomer[]}>>('/frontdesk/recharge-customers',{params:{query}});
export const createRecharge = (body: RechargeDraft) => http.post<unknown,ApiResponse<RechargeOrder>>('/frontdesk/recharges',body);
export const getRecharges = (params: RechargeFilters, admin=false) => http.get<unknown,ApiResponse<PageResult<RechargeOrder> & {server_now: string}>>(admin?'/admin/recharges':'/frontdesk/recharges',{params});
export const getRecharge = (id:number,admin=false) => http.get<unknown,ApiResponse<RechargeOrder>>(`${admin?'/admin':'/frontdesk'}/recharges/${id}`);
export const cancelRecharge = (id:number,request_key:string) => http.post<unknown,ApiResponse<RechargeOrder>>(`/frontdesk/recharges/${id}/cancel`,{request_key});
