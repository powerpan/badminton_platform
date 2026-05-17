import { http } from "./http";
import type { ApiResponse } from "./auth";
import type { PageResult } from "./court";

export type MemberTransactionType =
  | "admin_adjust"
  | "reservation_charge"
  | "reservation_refund"
  | "shop_purchase"
  | "shop_refund";

export interface MemberTransaction {
  id: number;
  transaction_type: MemberTransactionType;
  transaction_type_label: string;
  balance_change_cents: number;
  points_change: number;
  balance_before_cents: number;
  balance_after_cents: number;
  points_before: number;
  points_after: number;
  reason: string | null;
  reservation_id: number | null;
  shop_order_id: number | null;
  operator_username: string | null;
  created_at: string;
}

export function getMemberTransactions(params: { transaction_type?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<MemberTransaction>>>("/member/transactions", { params });
}
