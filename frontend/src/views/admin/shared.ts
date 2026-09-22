import { ElMessage, ElMessageBox } from "element-plus";

export interface PageState {
  page: number;
  page_size: number;
  total: number;
}

export function formatDate(value: Date) {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

export function addDays(days: number) {
  const value = new Date();
  value.setDate(value.getDate() + days);
  return formatDate(value);
}

export function formatDateTime(value: Date) {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16).replace("T", " ");
}

export function addHours(hours: number) {
  const value = new Date();
  value.setHours(value.getHours() + hours);
  return formatDateTime(value);
}

export function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function centsToYuanInput(cents: number | null | undefined) {
  const value = (cents || 0) / 100;
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

export function yuanInputToCents(value: string) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) {
    throw new Error("场地价格必须大于0");
  }
  return Math.round(number * 100);
}

export function yuanDeltaToCents(value: string) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new Error("余额调整格式错误");
  }
  return Math.round(number * 100);
}

export function discountText(rate: number | null | undefined) {
  const value = rate || 100;
  return value >= 100 ? "无折扣" : `${value / 10} 折`;
}

export function memberValidity(value: string | null | undefined) {
  return value ? `至 ${value}` : "长期有效";
}

export function tagTextToArray(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function operationDetail(detail: string) {
  try {
    return Object.entries(JSON.parse(detail))
      .map(([key, value]) => `${key}: ${value}`)
      .join("，");
  } catch {
    return detail || "-";
  }
}

export function statusTagType(status: string) {
  const map: Record<string, "primary" | "success" | "info" | "warning" | "danger"> = {
    pending: "warning",
    confirmed: "success",
    completed: "primary",
    canceled: "info",
    expired: "danger",
  };
  return map[status] || "info";
}

export function reservationStatusText(status: string) {
  const map: Record<string, string> = {
    pending: "待支付",
    confirmed: "已确认",
    completed: "已结束",
    canceled: "已取消",
    expired: "已过期",
  };
  return map[status] || status;
}

export function payMethodText(value: string | null | undefined) {
  return value === "balance" ? "会员余额" : value || "-";
}

export async function confirmAction(message: string, title = "确认操作") {
  try {
    await ElMessageBox.confirm(message, title, {
      confirmButtonText: "确认",
      cancelButtonText: "取消",
      type: "warning",
    });
    return true;
  } catch {
    return false;
  }
}

export function setSuccess(message: string) {
  ElMessage.success(message);
}

export function setError(error: unknown, fallback: string) {
  ElMessage.error(error instanceof Error ? error.message : fallback);
}

export function resetPage(pageState: PageState) {
  pageState.page = 1;
}

export async function changePage(pageState: PageState, nextPage: number, loader: () => Promise<void>) {
  pageState.page = Math.max(1, nextPage);
  await loader();
}
