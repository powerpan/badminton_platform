import { http } from './http';
import type { RechargeCustomer, RechargeCredit } from './recharge';
import type { ApiResponse } from './auth';

export type PaymentMethod = 'balance' | 'mock_alipay';
export type PaymentAction = 'balance-pay' | 'mock-confirm' | 'mock-fail' | 'cancel';
export interface Payment {
  id: number;
  payment_no: string;
  amount_cents: number;
  pay_method: PaymentMethod;
  status: 'pending' | 'succeeded' | 'canceled' | 'expired' | 'refunded';
  purpose: 'initial' | 'reschedule';
  expires_at: string;
  paid_at?: string | null;
  refunded_cents: number;
  server_now: string;
  reservation_id?: number;
  business_type: 'reservation' | 'shop' | 'recharge';
  recharge_order_id?: number;
  customer?: RechargeCustomer;
  credit?: RechargeCredit | null;
  shop_order_id?: number;
  target?: { court_name: string; reserve_date: string; start_time: string; end_time: string };
}
export const getPayment = (id: number) => http.get<unknown, ApiResponse<Payment>>(`/payments/${id}`);
export const paymentAction = (id: number, action: PaymentAction, key: string) =>
  http.post<unknown, ApiResponse<unknown>>(`/payments/${id}/${action}`, { request_key: key });
