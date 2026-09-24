import { http } from './http';
import type { ApiResponse } from './auth';
import type { AdminBookingDetail } from './admin';

export interface FinanceRecord {
  record_type: 'payment' | 'refund' | 'account' | 'legacy_reservation' | 'legacy_shop';
  record_id: number; occurred_at: string; business_type: string; entry_type: string; status: string;
  pay_method: string; amount_cents: number; confirmed: number | null; evidence: 'payment' | 'account' | 'missing';
  customer_user_id: number | null; customer_username: string | null; customer_name: string | null; customer_contact: string | null;
  operator_id: number | null; operator_name: string | null; created_by: number | null; created_by_name: string | null;
  reservation_id: number | null; reservation_no: string | null; shop_order_id: number | null; recharge_order_id: number | null;
  order_no: string | null; payment_order_id: number | null; payment_no: string | null; payment_refund_id: number | null; refund_no: string | null;
  balance_change_cents: number | null; points_change: number | null; description: string | null;
}
export interface FinanceSummary {
  channel_receipts_cents: number; channel_refunds_cents: number; channel_net_cents: number; recharge_cents: number;
  balance_consumption_cents: number; balance_refunds_cents: number; consumption_receipts_cents: number;
  consumption_refunds_cents: number; consumption_net_cents: number; adjustment_increase_cents: number; adjustment_decrease_cents: number; unverified_count: number;
}
export interface FinanceResult {
  items: FinanceRecord[]; total: number; page: number; page_size: number; server_now: string; date_from: string; date_to: string; summary: FinanceSummary;
  reconciliation: { accounts: number; without_history: number; mismatches: number; issues: Array<{
    user_id: number; username: string; balance_cents: number; points: number; recorded_balance_cents: number | null; recorded_points: number | null; chain_mismatch: number;
  }> };
}
export interface FinanceDetail {
  record: FinanceRecord; server_now: string;
  business: { id?: number; source?: string; reservation_no?: string; order_no?: string; recharge_no?: string; court_name?: string;
    reserve_date?: string; start_time?: string; end_time?: string; status?: string; amount_cents?: number; total_amount_cents?: number;
    payable_amount_cents?: number; balance_cents?: number; points?: number } | null;
  items?: Array<{ product_id: number; product_name: string; price_cents: number; quantity: number; subtotal_cents: number }>;
  payments: Array<Pick<AdminBookingDetail['payments'][number], 'id' | 'payment_no' | 'amount_cents' | 'pay_method' | 'status' | 'purpose' | 'paid_at' | 'created_at' | 'operator_id' | 'operator_name_snapshot' | 'collected_by' | 'collector_username'>>;
  refunds: Array<Pick<AdminBookingDetail['refunds'][number], 'id' | 'refund_no' | 'payment_order_id' | 'refund_group_no' | 'amount_cents' | 'pay_method' | 'status' | 'purpose' | 'reason' | 'refunded_at' | 'operator_id' | 'operator_name_snapshot'>>;
  account_transactions: AdminBookingDetail['account_transactions'];
  changes: AdminBookingDetail['changes'];
}
export type FinanceFilters = { date_from?: string; date_to?: string; business_type?: string; entry_type?: string; pay_method?: string; status?: string; customer?: string; operator?: string; order_no?: string; page?: number; page_size?: number };
export const getTransactions = (params: FinanceFilters) => http.get<unknown, ApiResponse<FinanceResult>>('/admin/transactions', { params });
export const getTransaction = (type: FinanceRecord['record_type'], id: number) => http.get<unknown, ApiResponse<FinanceDetail>>(`/admin/transactions/${type}/${id}`);
