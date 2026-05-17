import { http } from "./http";
import type { ApiResponse } from "./auth";
import type { PageResult } from "./court";

export interface ShopProduct {
  id: number;
  product_no: string;
  product_name: string;
  description: string;
  image_url: string;
  price_cents: number;
  stock: number;
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
  status: "paid" | "refund_requested" | "completed" | "canceled";
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
  items: Array<{ product_id: number; quantity: number }>;
  remark?: string;
}) {
  return http.post<unknown, ApiResponse<ShopOrder>>("/shop/orders", payload);
}

export function getMyShopOrders(params: { status?: string; page?: number; page_size?: number } = {}) {
  return http.get<unknown, ApiResponse<PageResult<ShopOrder>>>("/shop/orders/my", { params });
}

export function getShopOrder(orderId: number) {
  return http.get<unknown, ApiResponse<ShopOrder>>(`/shop/orders/${orderId}`);
}

export function cancelShopOrder(orderId: number) {
  return http.put<unknown, ApiResponse<ShopOrder>>(`/shop/orders/${orderId}/cancel`);
}

export function requestShopOrderRefund(orderId: number, payload: { reason: string }) {
  return http.put<unknown, ApiResponse<ShopOrder>>(`/shop/orders/${orderId}/refund-request`, payload);
}
