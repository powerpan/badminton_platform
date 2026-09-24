import { http } from "./http";
import type { ApiResponse } from "./auth";
import type { PageResult } from "./court";
import type { PaymentMethod } from './payment';

export interface ShopProduct {
  id: number;
  product_no: string;
  product_name: string;
  description: string;
  image_url: string;
  price_cents: number;
  stock: number;
  available_stock: number;
  reserved_stock: number;
  sold_count: number;
  status: number;
  created_at: string;
  updated_at: string;
}

export interface ShopOrderItem {
  id: number;
  order_id: number;
  product_id: number;
  product_no_snapshot: string;
  product_name_snapshot: string;
  image_url_snapshot: string;
  price_cents: number;
  quantity: number;
  subtotal_cents: number;
  created_at: string;
}

export interface ShopOrder {
  id: number;
  order_no: string;
  user_id: number;
  username: string;
  nickname: string | null;
  status: 'pending' | 'expired' | "paid" | "refund_requested" | "completed" | "canceled";
  payment_id?: number | null;
  expires_at?: string | null;
  server_now?: string;
  pickup_status?: 'ready' | 'frozen' | 'redeemed' | 'invalid' | null;
  redeemed_at?: string | null;
  redeemed_by_name?: string | null;
  total_amount_cents: number;
  pay_method: string;
  paid_at: string | null;
  completed_at: string | null;
  canceled_at: string | null;
  cancel_reason: string | null;
  refund_requested_at: string | null;
  refund_request_reason: string | null;
  refund_reviewed_at: string | null;
  refund_reject_reason: string | null;
  remark: string | null;
  created_at: string;
  updated_at: string;
  items?: ShopOrderItem[];
}

export function getShopProducts(params: { keyword?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<ShopProduct>>>("/shop/products", { params });
}

export function getShopProduct(productId: number) {
  return http.get<unknown, ApiResponse<ShopProduct>>(`/shop/products/${productId}`);
}

export function createShopOrder(payload: {
  items: Array<{ product_id: number; quantity: number; expected_price_cents: number }>;
  remark?: string;
  pay_method?: PaymentMethod;
  request_key?: string;
}) {
  return http.post<unknown, ApiResponse<ShopOrder>>("/shop/orders", payload);
}

export function getMyShopOrders(params: { status?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<ShopOrder> & { server_now: string }>>("/shop/orders/my", { params });
}

export function getShopOrder(orderId: number) {
  return http.get<unknown, ApiResponse<ShopOrder>>(`/shop/orders/${orderId}`);
}

export function cancelShopOrder(orderId: number, request_key: string) {
  return http.put<unknown, ApiResponse<ShopOrder>>(`/shop/orders/${orderId}/cancel`, { request_key });
}

export function requestShopOrderRefund(orderId: number, payload: { reason: string; request_key?: string }) {
  return http.put<unknown, ApiResponse<ShopOrder>>(`/shop/orders/${orderId}/refund-request`, payload);
}

export interface ShopQuote {
  items: Array<{ product: ShopProduct; quantity: number; subtotal_cents: number }>;
  total_amount_cents: number;
  balance_cents: number;
  pending_amount_cents: number;
  available_balance_cents: number;
  issues: string[];
  can_checkout: boolean;
}
export function quoteShopOrder(items: Array<{ product_id: number; quantity: number }>, pay_method: PaymentMethod = 'balance') {
  return http.post<unknown, ApiResponse<ShopQuote>>('/shop/orders/quote', { items, pay_method });
}

export interface PickupCredential {
  order_id: number; order_no: string; status: 'ready' | 'frozen' | 'redeemed' | 'invalid';
  code: string | null; qr_content: string | null; qr_data_url: string | null;
  redeemed_at: string | null; redeemed_by: number | null;
}
export interface PickupLookup {
  id: number; order_no: string; status: ShopOrder['status']; total_amount_cents: number;
  pickup_status: PickupCredential['status']; redeemed_at: string | null; redeemed_by_name: string | null;
  items: Array<Pick<ShopOrderItem, 'product_name_snapshot' | 'quantity' | 'price_cents' | 'subtotal_cents'>>;
  can_redeem: boolean;
}
export const getPickupCode = (id: number) => http.get<unknown, ApiResponse<PickupCredential>>(`/shop/orders/${id}/pickup-code`);
export const lookupPickup = (code: string) => http.post<unknown, ApiResponse<PickupLookup>>('/frontdesk/pickups/lookup', { code });
export const redeemPickup = (code: string, request_key: string) => http.post<unknown, ApiResponse<Omit<PickupLookup, 'can_redeem'>>>('/frontdesk/pickups/redeem', { code, request_key });
