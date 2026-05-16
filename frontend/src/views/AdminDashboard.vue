<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import type { Announcement } from "../api/announcement";
import {
  adminBroadcastNotification,
  adminCancelShopOrder,
  adminCompleteShopOrder,
  adminCancelReservation,
  adminCreateAnnouncement,
  adminCreateCourt,
  adminCreateEvent,
  adminCreateShopProduct,
  adminCreateUser,
  adminGetCommunityPosts,
  adminGetAnnouncements,
  adminGetConfigs,
  adminGetCourtStatistics,
  adminGetCourts,
  adminGetEvents,
  adminGetOperationLogs,
  adminGetReservations,
  adminGetShopOrders,
  adminGetShopProducts,
  adminGetStatisticsOverview,
  adminGetTimeSlotStatistics,
  adminGetUserStatistics,
  adminGetUsers,
  adminHideCommunityPost,
  adminResetUserPassword,
  adminUpdateAnnouncement,
  adminUpdateAnnouncementStatus,
  adminUpdateConfig,
  adminUpdateCourt,
  adminUpdateCourtStatus,
  adminUpdateEvent,
  adminUpdateEventStatus,
  adminUpdateShopProduct,
  adminUpdateShopProductStatus,
  adminUpdateUserMember,
  adminUpdateUserRole,
  adminUpdateUserStatus,
  type ConfigItem,
  type CourtStatistic,
  type OperationLog,
  type StatisticsOverview,
  type TimeSlotStatistic,
  type UserStatistic,
} from "../api/admin";
import type { UserInfo } from "../api/auth";
import type { CommunityPost } from "../api/community";
import type { Court } from "../api/court";
import type { ClubEvent } from "../api/event";
import type { Reservation } from "../api/reservation";
import type { ShopOrder, ShopProduct } from "../api/shop";
import { useAuthStore } from "../stores/auth";

type AdminTab =
  | "statistics"
  | "users"
  | "courts"
  | "reservations"
  | "announcements"
  | "notifications"
  | "events"
  | "community"
  | "shop"
  | "configs"
  | "logs";

interface PageState {
  page: number;
  page_size: number;
  total: number;
}

const authStore = useAuthStore();
const activeTab = ref<AdminTab>("statistics");
const loading = ref(false);

const tabs: Array<{ key: AdminTab; label: string }> = [
  { key: "statistics", label: "统计" },
  { key: "users", label: "用户" },
  { key: "courts", label: "场地" },
  { key: "reservations", label: "预约" },
  { key: "announcements", label: "公告" },
  { key: "notifications", label: "通知" },
  { key: "events", label: "活动" },
  { key: "community", label: "球友圈" },
  { key: "shop", label: "商城" },
  { key: "configs", label: "规则" },
  { key: "logs", label: "日志" },
];

function formatDate(value: Date) {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function addDays(days: number) {
  const value = new Date();
  value.setDate(value.getDate() + days);
  return formatDate(value);
}

function formatDateTime(value: Date) {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16).replace("T", " ");
}

function addHours(hours: number) {
  const value = new Date();
  value.setHours(value.getHours() + hours);
  return formatDateTime(value);
}

function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function centsToYuanInput(cents: number | null | undefined) {
  const value = (cents || 0) / 100;
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function yuanInputToCents(value: string) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) {
    throw new Error("场地价格必须大于0");
  }
  return Math.round(number * 100);
}

function yuanDeltaToCents(value: string) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new Error("余额调整格式错误");
  }
  return Math.round(number * 100);
}

function discountText(rate: number | null | undefined) {
  const value = rate || 100;
  return value >= 100 ? "无折扣" : `${value / 10} 折`;
}

function memberValidity(value: string | null | undefined) {
  return value ? `至 ${value}` : "长期有效";
}

function tagTextToArray(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function operationDetail(detail: string) {
  try {
    return Object.entries(JSON.parse(detail))
      .map(([key, value]) => `${key}: ${value}`)
      .join("，");
  } catch {
    return detail || "-";
  }
}

function statusTagType(status: string) {
  const map: Record<string, "primary" | "success" | "info" | "warning" | "danger"> = {
    pending: "warning",
    confirmed: "success",
    completed: "primary",
    canceled: "info",
    expired: "danger",
  };
  return map[status] || "info";
}

function reservationStatusText(status: string) {
  const map: Record<string, string> = {
    pending: "待支付",
    confirmed: "已确认",
    completed: "已完成",
    canceled: "已取消",
    expired: "已过期",
  };
  return map[status] || status;
}

async function confirmAction(message: string, title = "确认操作") {
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

function setSuccess(message: string) {
  ElMessage.success(message);
}

function setError(error: unknown, fallback: string) {
  ElMessage.error(error instanceof Error ? error.message : fallback);
}

function resetPage(pageState: PageState) {
  pageState.page = 1;
}

async function changePage(pageState: PageState, nextPage: number, loader: () => Promise<void>) {
  pageState.page = Math.max(1, nextPage);
  await loader();
}

async function changeUserPage(page: number) {
  await changePage(userPage.value, page, () => refreshUsers());
}

async function changeCourtPage(page: number) {
  await changePage(courtPage.value, page, () => refreshCourts());
}

async function changeReservationPage(page: number) {
  await changePage(reservationPage.value, page, () => refreshReservations());
}

async function changeAnnouncementPage(page: number) {
  await changePage(announcementPage.value, page, () => refreshAnnouncements());
}

async function changeEventPage(page: number) {
  await changePage(eventPage.value, page, () => refreshEvents());
}

async function changeCommunityPage(page: number) {
  await changePage(communityPage.value, page, () => refreshCommunityPosts());
}

async function changeShopProductPage(page: number) {
  await changePage(shopProductPage.value, page, () => refreshShopProducts());
}

async function changeShopOrderPage(page: number) {
  await changePage(shopOrderPage.value, page, () => refreshShopOrders());
}

async function changeLogPage(page: number) {
  await changePage(logPage.value, page, () => refreshOperationLogs());
}

const statsRange = ref({
  date_from: addDays(0),
  date_to: addDays(6),
});
const statisticsOverview = ref<StatisticsOverview | null>(null);
const courtStatistics = ref<CourtStatistic[]>([]);
const timeSlotStatistics = ref<TimeSlotStatistic[]>([]);
const userStatistics = ref<UserStatistic[]>([]);

const users = ref<UserInfo[]>([]);
const userPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });
const userFilters = ref({ role: "", status: "" });
const memberLevelOptions = [
  { value: "normal", label: "普通会员" },
  { value: "silver", label: "银卡会员" },
  { value: "gold", label: "金卡会员" },
  { value: "diamond", label: "钻石会员" },
];
const userForm = ref({
  username: "",
  password: "",
  nickname: "",
  contact: "",
  role: "user",
  status: 1,
});
const editingMemberUser = ref<UserInfo | null>(null);
const memberForm = ref({
  member_level: "normal",
  expires_at: "",
  balance_change_yuan: "0",
  points_change: 0,
  reason: "",
});
const resettingPasswordUser = ref<UserInfo | null>(null);
const resetPasswordForm = ref({ password: "" });

const courts = ref<Court[]>([]);
const courtOptions = ref<Court[]>([]);
const courtPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });
const courtStatus = ref("");
const emptyCourtForm = () => ({
  court_no: "",
  court_name: "",
  description: "",
  price_per_hour_yuan: "120",
  image_url: "/courts/default-court.png",
  tags_text: "空调开放,标准场地",
  capacity: 6,
  status: 1,
});
const courtForm = ref(emptyCourtForm());
const editingCourtId = ref<number | null>(null);
const editingCourt = ref<Court | null>(null);
const courtEditForm = ref(emptyCourtForm());

const reservations = ref<Reservation[]>([]);
const reservationPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });
const reservationFilters = ref({
  status: "",
  username: "",
  court_id: "",
  date_from: "",
  date_to: "",
});

const announcements = ref<Announcement[]>([]);
const announcementPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });
const announcementStatus = ref("");
const announcementForm = ref({ title: "", content: "", status: 1 });
const editingAnnouncementId = ref<number | null>(null);
const editingAnnouncement = ref<Announcement | null>(null);
const announcementEditForm = ref({ title: "", content: "", status: 1 });

const broadcastForm = ref({
  title: "",
  content: "",
});

const events = ref<ClubEvent[]>([]);
const eventPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });
const eventStatus = ref("");
const emptyEventForm = () => ({
  title: "",
  content: "",
  location: "一号场",
  start_at: addHours(48),
  end_at: addHours(50),
  registration_deadline: addHours(24),
  capacity: 20,
  status: 1,
});
const eventForm = ref(emptyEventForm());
const editingEventId = ref<number | null>(null);
const editingEvent = ref<ClubEvent | null>(null);
const eventEditForm = ref(emptyEventForm());

const communityPosts = ref<CommunityPost[]>([]);
const communityPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });
const communityStatus = ref("");

const shopProducts = ref<ShopProduct[]>([]);
const shopProductPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });
const shopProductFilters = ref({ status: "", keyword: "" });
const emptyShopProductForm = () => ({
  product_no: "",
  product_name: "",
  description: "",
  image_url: "/courts/default-court.png",
  price_yuan: "10",
  stock: 10,
  status: 1,
});
const shopProductForm = ref(emptyShopProductForm());
const editingShopProductId = ref<number | null>(null);
const editingShopProduct = ref<ShopProduct | null>(null);
const shopProductEditForm = ref(emptyShopProductForm());
const shopOrders = ref<ShopOrder[]>([]);
const shopOrderPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });
const shopOrderFilters = ref({ status: "", username: "" });

const configs = ref<ConfigItem[]>([]);
const editingConfig = ref<ConfigItem | null>(null);
const configForm = ref({ config_value: "" });

const operationLogs = ref<OperationLog[]>([]);
const logPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });
const logFilters = ref({
  module: "",
  action: "",
  username: "",
  date_from: "",
  date_to: "",
});

const usageTable = computed(() =>
  courtStatistics.value.map((item) => ({
    ...item,
    progress: Math.min(100, Math.max(0, Number(item.usage_rate || 0))),
  })),
);

async function loadStatistics() {
  const params = { date_from: statsRange.value.date_from, date_to: statsRange.value.date_to };
  const [overview, courtsResult, slotsResult, usersResult] = await Promise.all([
    adminGetStatisticsOverview(params),
    adminGetCourtStatistics(params),
    adminGetTimeSlotStatistics({ ...params, limit: 12 }),
    adminGetUserStatistics({ ...params, limit: 10 }),
  ]);
  statisticsOverview.value = overview.data;
  courtStatistics.value = courtsResult.data.items;
  timeSlotStatistics.value = slotsResult.data.items;
  userStatistics.value = usersResult.data.items;
}

async function refreshStatistics() {
  loading.value = true;
  try {
    await loadStatistics();
    setSuccess("统计已刷新");
  } catch (error) {
    setError(error, "统计数据加载失败");
  } finally {
    loading.value = false;
  }
}

async function loadUsers() {
  const response = await adminGetUsers({
    role: userFilters.value.role || undefined,
    status: userFilters.value.status || undefined,
    page: userPage.value.page,
    page_size: userPage.value.page_size,
  });
  users.value = response.data.items;
  userPage.value.total = response.data.total;
}

async function refreshUsers(reset = false) {
  if (reset) resetPage(userPage.value);
  loading.value = true;
  try {
    await loadUsers();
  } catch (error) {
    setError(error, "用户列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function submitUser() {
  loading.value = true;
  try {
    await adminCreateUser(userForm.value);
    userForm.value = { username: "", password: "", nickname: "", contact: "", role: "user", status: 1 };
    resetPage(userPage.value);
    await loadUsers();
    setSuccess("用户已创建");
  } catch (error) {
    setError(error, "创建用户失败");
  } finally {
    loading.value = false;
  }
}

async function toggleUserStatus(user: UserInfo) {
  const nextStatusLabel = user.status === 1 ? "禁用" : "启用";
  if (!(await confirmAction(`确认${nextStatusLabel}用户 ${user.username}？`))) return;
  loading.value = true;
  try {
    await adminUpdateUserStatus(user.id, user.status === 1 ? 0 : 1);
    await loadUsers();
    setSuccess("用户状态已更新");
  } catch (error) {
    setError(error, "更新用户状态失败");
  } finally {
    loading.value = false;
  }
}

async function changeUserRoleValue(user: UserInfo, roleValue: string | number | boolean) {
  const role = String(roleValue);
  if (role !== user.role && !(await confirmAction(`确认将用户 ${user.username} 的角色修改为 ${role}？`))) return;
  loading.value = true;
  try {
    await adminUpdateUserRole(user.id, role);
    await loadUsers();
    setSuccess("用户角色已更新");
  } catch (error) {
    setError(error, "更新用户角色失败");
    await loadUsers();
  } finally {
    loading.value = false;
  }
}

function editUserMember(user: UserInfo) {
  editingMemberUser.value = user;
  memberForm.value = {
    member_level: user.member.level,
    expires_at: user.member.expires_at || "",
    balance_change_yuan: "0",
    points_change: 0,
    reason: "",
  };
}

function resetMemberForm() {
  editingMemberUser.value = null;
  memberForm.value = { member_level: "normal", expires_at: "", balance_change_yuan: "0", points_change: 0, reason: "" };
}

async function submitMember() {
  if (!editingMemberUser.value) return;
  try {
    const targetUserId = editingMemberUser.value.id;
    const balanceChangeCents = yuanDeltaToCents(memberForm.value.balance_change_yuan);
    const pointsChange = Number(memberForm.value.points_change || 0);
    if (!Number.isFinite(pointsChange)) throw new Error("积分调整格式错误");
    const levelLabel = memberLevelOptions.find((item) => item.value === memberForm.value.member_level)?.label || memberForm.value.member_level;
    const expiresText = memberForm.value.expires_at || "长期有效";
    const balanceText = `${balanceChangeCents >= 0 ? "+" : ""}${(balanceChangeCents / 100).toFixed(2)} 元`;
    const pointsText = `${pointsChange >= 0 ? "+" : ""}${pointsChange} 分`;
    if (!(await confirmAction(`确认调整 ${editingMemberUser.value.username} 的会员账户？\n等级：${levelLabel}\n有效期：${expiresText}\n余额变动：${balanceText}\n积分变动：${pointsText}`))) return;
    loading.value = true;
    await adminUpdateUserMember(targetUserId, {
      member_level: memberForm.value.member_level,
      expires_at: memberForm.value.expires_at || null,
      balance_change_cents: balanceChangeCents,
      points_change: pointsChange,
      reason: memberForm.value.reason.trim() || "后台调整会员账户",
    });
    resetMemberForm();
    await loadUsers();
    if (targetUserId === authStore.user?.id) await authStore.fetchProfile();
    setSuccess("会员账户已更新");
  } catch (error) {
    setError(error, "更新会员账户失败");
  } finally {
    loading.value = false;
  }
}

function resetUserPassword(user: UserInfo) {
  resettingPasswordUser.value = user;
  resetPasswordForm.value = { password: "" };
}

function resetPasswordDialog() {
  resettingPasswordUser.value = null;
  resetPasswordForm.value = { password: "" };
}

async function submitResetPassword() {
  if (!resettingPasswordUser.value || !resetPasswordForm.value.password) return;
  const user = resettingPasswordUser.value;
  if (!(await confirmAction(`确认重置用户 ${user.username} 的密码？该用户旧登录态会失效。`))) return;
  loading.value = true;
  try {
    await adminResetUserPassword(user.id, resetPasswordForm.value.password);
    resetPasswordDialog();
    setSuccess("用户密码已重置");
  } catch (error) {
    setError(error, "重置密码失败");
  } finally {
    loading.value = false;
  }
}

function courtPayload(form: ReturnType<typeof emptyCourtForm>) {
  return {
    court_no: form.court_no,
    court_name: form.court_name,
    description: form.description,
    status: form.status,
    price_per_hour_cents: yuanInputToCents(form.price_per_hour_yuan),
    image_url: form.image_url,
    tags: tagTextToArray(form.tags_text),
    capacity: form.capacity,
  };
}

async function loadCourts() {
  const response = await adminGetCourts({
    status: courtStatus.value || undefined,
    page: courtPage.value.page,
    page_size: courtPage.value.page_size,
  });
  courts.value = response.data.items;
  courtPage.value.total = response.data.total;
}

async function loadCourtOptions() {
  if (courtOptions.value.length > 0) return;
  const response = await adminGetCourts({ page_size: 100 });
  courtOptions.value = response.data.items;
}

async function refreshCourts(reset = false) {
  if (reset) resetPage(courtPage.value);
  loading.value = true;
  try {
    await loadCourts();
  } catch (error) {
    setError(error, "场地列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function submitCourt() {
  const isEdit = Boolean(editingCourtId.value);
  const form = isEdit ? courtEditForm.value : courtForm.value;
  if (isEdit && form.status === 0 && !(await confirmAction("确认停用该场地？如存在未来预约，后端会拒绝停用。"))) return;
  loading.value = true;
  try {
    const payload = courtPayload(form);
    if (editingCourtId.value) {
      await adminUpdateCourt(editingCourtId.value, payload);
      setSuccess("场地已更新");
    } else {
      await adminCreateCourt(payload);
      setSuccess("场地已创建");
    }
    resetCourtForm();
    resetPage(courtPage.value);
    courtOptions.value = [];
    await loadCourts();
  } catch (error) {
    setError(error, "保存场地失败");
  } finally {
    loading.value = false;
  }
}

function editCourt(court: Court) {
  editingCourtId.value = court.id;
  editingCourt.value = court;
  courtEditForm.value = {
    court_no: court.court_no,
    court_name: court.court_name,
    description: court.description || "",
    price_per_hour_yuan: centsToYuanInput(court.price_per_hour_cents),
    image_url: court.image_url || "/courts/default-court.png",
    tags_text: court.tags?.join(",") || "",
    capacity: court.capacity || 6,
    status: court.status,
  };
}

function resetCourtForm() {
  editingCourtId.value = null;
  editingCourt.value = null;
  courtForm.value = emptyCourtForm();
  courtEditForm.value = emptyCourtForm();
}

async function toggleCourtStatus(court: Court) {
  const nextStatusLabel = court.status === 1 ? "停用" : "启用";
  if (!(await confirmAction(`确认${nextStatusLabel}场地 ${court.court_no} ${court.court_name}？`))) return;
  loading.value = true;
  try {
    await adminUpdateCourtStatus(court.id, court.status === 1 ? 0 : 1);
    courtOptions.value = [];
    await loadCourts();
    setSuccess("场地状态已更新");
  } catch (error) {
    setError(error, "更新场地状态失败");
  } finally {
    loading.value = false;
  }
}

async function loadReservations() {
  const response = await adminGetReservations({
    status: reservationFilters.value.status || undefined,
    username: reservationFilters.value.username || undefined,
    court_id: reservationFilters.value.court_id ? Number(reservationFilters.value.court_id) : undefined,
    date_from: reservationFilters.value.date_from || undefined,
    date_to: reservationFilters.value.date_to || undefined,
    page: reservationPage.value.page,
    page_size: reservationPage.value.page_size,
  });
  reservations.value = response.data.items;
  reservationPage.value.total = response.data.total;
}

async function refreshReservations(reset = false) {
  if (reset) resetPage(reservationPage.value);
  loading.value = true;
  try {
    await loadReservations();
  } catch (error) {
    setError(error, "预约列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function cancelAdminReservation(reservation: Reservation) {
  const tip = reservation.status === "pending"
    ? `确认取消待支付预约 ${reservation.reservation_no}？取消后会释放场地占用。`
    : `确认取消预约 ${reservation.reservation_no}？`;
  if (!(await confirmAction(tip))) return;
  loading.value = true;
  try {
    await adminCancelReservation(reservation.id);
    await loadReservations();
    setSuccess("预约已取消");
  } catch (error) {
    setError(error, "取消预约失败");
  } finally {
    loading.value = false;
  }
}

async function loadAnnouncements() {
  const response = await adminGetAnnouncements({
    status: announcementStatus.value || undefined,
    page: announcementPage.value.page,
    page_size: announcementPage.value.page_size,
  });
  announcements.value = response.data.items;
  announcementPage.value.total = response.data.total;
}

async function refreshAnnouncements(reset = false) {
  if (reset) resetPage(announcementPage.value);
  loading.value = true;
  try {
    await loadAnnouncements();
  } catch (error) {
    setError(error, "公告列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function submitAnnouncement() {
  const payload = editingAnnouncementId.value ? announcementEditForm.value : announcementForm.value;
  loading.value = true;
  try {
    if (editingAnnouncementId.value) {
      await adminUpdateAnnouncement(editingAnnouncementId.value, payload);
      setSuccess("公告已更新");
    } else {
      await adminCreateAnnouncement(payload);
      setSuccess("公告已创建");
    }
    resetAnnouncementForm();
    resetPage(announcementPage.value);
    await loadAnnouncements();
  } catch (error) {
    setError(error, "保存公告失败");
  } finally {
    loading.value = false;
  }
}

function editAnnouncement(announcement: Announcement) {
  editingAnnouncementId.value = announcement.id;
  editingAnnouncement.value = announcement;
  announcementEditForm.value = {
    title: announcement.title,
    content: announcement.content,
    status: announcement.status,
  };
}

function resetAnnouncementForm() {
  editingAnnouncementId.value = null;
  editingAnnouncement.value = null;
  announcementForm.value = { title: "", content: "", status: 1 };
  announcementEditForm.value = { title: "", content: "", status: 1 };
}

async function toggleAnnouncementStatus(announcement: Announcement) {
  const nextStatusLabel = announcement.status === 1 ? "隐藏" : "显示";
  if (!(await confirmAction(`确认${nextStatusLabel}公告《${announcement.title}》？`))) return;
  loading.value = true;
  try {
    await adminUpdateAnnouncementStatus(announcement.id, announcement.status === 1 ? 0 : 1);
    await loadAnnouncements();
    setSuccess("公告状态已更新");
  } catch (error) {
    setError(error, "更新公告状态失败");
  } finally {
    loading.value = false;
  }
}

async function submitBroadcastNotification() {
  const title = broadcastForm.value.title.trim();
  const content = broadcastForm.value.content.trim();
  if (!title || !content) {
    setError(new Error("通知标题和内容不能为空"), "发送通知失败");
    return;
  }
  if (!(await confirmAction("确认向全部启用账号发送这条站内通知？"))) return;
  loading.value = true;
  try {
    const response = await adminBroadcastNotification({ title, content });
    broadcastForm.value = { title: "", content: "" };
    setSuccess(`通知已发送给 ${response.data.sent_count} 个账号`);
  } catch (error) {
    setError(error, "发送通知失败");
  } finally {
    loading.value = false;
  }
}

function eventPayload(form: ReturnType<typeof emptyEventForm>) {
  return {
    title: form.title,
    content: form.content,
    location: form.location,
    start_at: form.start_at,
    end_at: form.end_at,
    registration_deadline: form.registration_deadline,
    capacity: form.capacity,
    status: form.status,
  };
}

async function loadEvents() {
  const response = await adminGetEvents({
    status: eventStatus.value || undefined,
    page: eventPage.value.page,
    page_size: eventPage.value.page_size,
  });
  events.value = response.data.items;
  eventPage.value.total = response.data.total;
}

async function refreshEvents(reset = false) {
  if (reset) resetPage(eventPage.value);
  loading.value = true;
  try {
    await loadEvents();
  } catch (error) {
    setError(error, "活动列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function submitEvent() {
  const payload = editingEventId.value ? eventPayload(eventEditForm.value) : eventPayload(eventForm.value);
  loading.value = true;
  try {
    if (editingEventId.value) {
      await adminUpdateEvent(editingEventId.value, payload);
      setSuccess("活动已更新");
    } else {
      await adminCreateEvent(payload);
      setSuccess("活动已创建");
    }
    resetEventForm();
    resetPage(eventPage.value);
    await loadEvents();
  } catch (error) {
    setError(error, "保存活动失败");
  } finally {
    loading.value = false;
  }
}

function editEvent(event: ClubEvent) {
  editingEventId.value = event.id;
  editingEvent.value = event;
  eventEditForm.value = {
    title: event.title,
    content: event.content,
    location: event.location,
    start_at: String(event.start_at).slice(0, 16).replace("T", " "),
    end_at: String(event.end_at).slice(0, 16).replace("T", " "),
    registration_deadline: String(event.registration_deadline).slice(0, 16).replace("T", " "),
    capacity: event.capacity,
    status: event.status,
  };
}

function resetEventForm() {
  editingEventId.value = null;
  editingEvent.value = null;
  eventForm.value = emptyEventForm();
  eventEditForm.value = emptyEventForm();
}

async function toggleEventStatus(event: ClubEvent) {
  const nextStatusLabel = event.status === 1 ? "隐藏" : "显示";
  if (!(await confirmAction(`确认${nextStatusLabel}活动《${event.title}》？`))) return;
  loading.value = true;
  try {
    await adminUpdateEventStatus(event.id, event.status === 1 ? 0 : 1);
    await loadEvents();
    setSuccess("活动状态已更新");
  } catch (error) {
    setError(error, "更新活动状态失败");
  } finally {
    loading.value = false;
  }
}

async function loadCommunityPosts() {
  const response = await adminGetCommunityPosts({
    status: communityStatus.value || undefined,
    page: communityPage.value.page,
    page_size: communityPage.value.page_size,
  });
  communityPosts.value = response.data.items;
  communityPage.value.total = response.data.total;
}

async function refreshCommunityPosts(reset = false) {
  if (reset) resetPage(communityPage.value);
  loading.value = true;
  try {
    await loadCommunityPosts();
  } catch (error) {
    setError(error, "球友圈动态加载失败");
  } finally {
    loading.value = false;
  }
}

async function hideAdminCommunityPost(post: CommunityPost) {
  if (!(await confirmAction(`确认隐藏 ${post.nickname || post.username} 的动态？`))) return;
  loading.value = true;
  try {
    await adminHideCommunityPost(post.id);
    await loadCommunityPosts();
    setSuccess("动态已隐藏");
  } catch (error) {
    setError(error, "隐藏动态失败");
  } finally {
    loading.value = false;
  }
}

function shopProductPayload(form: ReturnType<typeof emptyShopProductForm>) {
  return {
    product_no: form.product_no,
    product_name: form.product_name,
    description: form.description,
    image_url: form.image_url,
    price_cents: yuanInputToCents(form.price_yuan),
    stock: form.stock,
    status: form.status,
  };
}

async function loadShopProducts() {
  const response = await adminGetShopProducts({
    status: shopProductFilters.value.status || undefined,
    keyword: shopProductFilters.value.keyword || undefined,
    page: shopProductPage.value.page,
    page_size: shopProductPage.value.page_size,
  });
  shopProducts.value = response.data.items;
  shopProductPage.value.total = response.data.total;
}

async function refreshShopProducts(reset = false) {
  if (reset) resetPage(shopProductPage.value);
  loading.value = true;
  try {
    await loadShopProducts();
  } catch (error) {
    setError(error, "商品列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function submitShopProduct() {
  const payload = editingShopProductId.value
    ? shopProductPayload(shopProductEditForm.value)
    : shopProductPayload(shopProductForm.value);
  loading.value = true;
  try {
    if (editingShopProductId.value) {
      await adminUpdateShopProduct(editingShopProductId.value, payload);
      setSuccess("商品已更新");
    } else {
      await adminCreateShopProduct(payload);
      setSuccess("商品已创建");
    }
    resetShopProductForm();
    resetPage(shopProductPage.value);
    await loadShopProducts();
  } catch (error) {
    setError(error, "保存商品失败");
  } finally {
    loading.value = false;
  }
}

function editShopProduct(product: ShopProduct) {
  editingShopProductId.value = product.id;
  editingShopProduct.value = product;
  shopProductEditForm.value = {
    product_no: product.product_no,
    product_name: product.product_name,
    description: product.description || "",
    image_url: product.image_url || "/courts/default-court.png",
    price_yuan: centsToYuanInput(product.price_cents),
    stock: product.stock,
    status: product.status,
  };
}

function resetShopProductForm() {
  editingShopProductId.value = null;
  editingShopProduct.value = null;
  shopProductForm.value = emptyShopProductForm();
  shopProductEditForm.value = emptyShopProductForm();
}

async function toggleShopProductStatus(product: ShopProduct) {
  const nextStatusLabel = product.status === 1 ? "下架" : "上架";
  if (!(await confirmAction(`确认${nextStatusLabel}商品 ${product.product_name}？`))) return;
  loading.value = true;
  try {
    await adminUpdateShopProductStatus(product.id, product.status === 1 ? 0 : 1);
    await loadShopProducts();
    setSuccess("商品状态已更新");
  } catch (error) {
    setError(error, "更新商品状态失败");
  } finally {
    loading.value = false;
  }
}

function shopOrderStatusType(status: string) {
  const map: Record<string, "success" | "primary" | "info"> = {
    paid: "success",
    completed: "primary",
    canceled: "info",
  };
  return map[status] || "info";
}

function shopOrderStatusText(status: string) {
  const map: Record<string, string> = {
    paid: "已支付",
    completed: "已完成",
    canceled: "已取消",
  };
  return map[status] || status;
}

async function loadShopOrders() {
  const response = await adminGetShopOrders({
    status: shopOrderFilters.value.status || undefined,
    username: shopOrderFilters.value.username || undefined,
    page: shopOrderPage.value.page,
    page_size: shopOrderPage.value.page_size,
  });
  shopOrders.value = response.data.items;
  shopOrderPage.value.total = response.data.total;
}

async function refreshShopOrders(reset = false) {
  if (reset) resetPage(shopOrderPage.value);
  loading.value = true;
  try {
    await loadShopOrders();
  } catch (error) {
    setError(error, "商城订单加载失败");
  } finally {
    loading.value = false;
  }
}

async function completeShopOrder(order: ShopOrder) {
  if (!(await confirmAction(`确认完成订单 ${order.order_no}？完成后不能取消退款。`))) return;
  loading.value = true;
  try {
    await adminCompleteShopOrder(order.id);
    await loadShopOrders();
    setSuccess("订单已完成");
  } catch (error) {
    setError(error, "完成订单失败");
  } finally {
    loading.value = false;
  }
}

async function cancelAdminShopOrder(order: ShopOrder) {
  if (!(await confirmAction(`确认取消订单 ${order.order_no} 并退回会员余额？`))) return;
  loading.value = true;
  try {
    await adminCancelShopOrder(order.id);
    await loadShopOrders();
    setSuccess("订单已取消并退款");
  } catch (error) {
    setError(error, "取消商城订单失败");
  } finally {
    loading.value = false;
  }
}

async function loadConfigs() {
  const response = await adminGetConfigs();
  configs.value = response.data;
}

function editConfig(config: ConfigItem) {
  editingConfig.value = config;
  configForm.value = { config_value: config.config_value };
}

function resetConfigForm() {
  editingConfig.value = null;
  configForm.value = { config_value: "" };
}

async function submitConfig() {
  if (!editingConfig.value) return;
  const nextValue = configForm.value.config_value.trim();
  if (!nextValue) {
    setError(new Error("配置值不能为空"), "更新规则配置失败");
    return;
  }
  if (!(await confirmAction(`确认保存规则 ${editingConfig.value.config_key} = ${nextValue}？`))) return;
  loading.value = true;
  try {
    await adminUpdateConfig(editingConfig.value.config_key, nextValue);
    resetConfigForm();
    await loadConfigs();
    setSuccess("规则配置已更新");
  } catch (error) {
    setError(error, "更新规则配置失败");
  } finally {
    loading.value = false;
  }
}

async function loadOperationLogs() {
  const response = await adminGetOperationLogs({
    module: logFilters.value.module || undefined,
    action: logFilters.value.action || undefined,
    username: logFilters.value.username || undefined,
    date_from: logFilters.value.date_from || undefined,
    date_to: logFilters.value.date_to || undefined,
    page: logPage.value.page,
    page_size: logPage.value.page_size,
  });
  operationLogs.value = response.data.items;
  logPage.value.total = response.data.total;
}

async function refreshOperationLogs(reset = false) {
  if (reset) resetPage(logPage.value);
  loading.value = true;
  try {
    await loadOperationLogs();
  } catch (error) {
    setError(error, "日志加载失败");
  } finally {
    loading.value = false;
  }
}

async function loadActiveTab() {
  loading.value = true;
  try {
    if (activeTab.value === "statistics") await loadStatistics();
    if (activeTab.value === "users") await loadUsers();
    if (activeTab.value === "courts") await loadCourts();
    if (activeTab.value === "reservations") {
      await loadCourtOptions();
      await loadReservations();
    }
    if (activeTab.value === "announcements") await loadAnnouncements();
    if (activeTab.value === "notifications") return;
    if (activeTab.value === "events") await loadEvents();
    if (activeTab.value === "community") await loadCommunityPosts();
    if (activeTab.value === "shop") {
      await Promise.all([loadShopProducts(), loadShopOrders()]);
    }
    if (activeTab.value === "configs") await loadConfigs();
    if (activeTab.value === "logs") await loadOperationLogs();
  } catch (error) {
    setError(error, "后台数据加载失败");
  } finally {
    loading.value = false;
  }
}

async function switchTab(tab: AdminTab) {
  activeTab.value = tab;
  await loadActiveTab();
}

async function switchTabByName(name: string | number) {
  await switchTab(String(name) as AdminTab);
}

onMounted(loadActiveTab);
</script>

<template>
  <section class="page-header">
    <p class="eyebrow">管理端</p>
    <h1>后台管理</h1>
    <p>集中管理统计、用户、场地、预约、公告、通知、活动、球友圈、商城、规则配置和操作日志。</p>
  </section>

  <el-card shadow="never" class="admin-shell element-admin">
    <el-tabs :model-value="activeTab" @tab-change="switchTabByName">
      <el-tab-pane v-for="tab in tabs" :key="tab.key" :label="tab.label" :name="tab.key" />
    </el-tabs>

    <section v-if="activeTab === 'statistics'" v-loading="loading" class="admin-section">
      <el-form inline class="element-filter">
        <el-form-item label="开始日期">
          <el-date-picker v-model="statsRange.date_from" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="statsRange.date_to" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="refreshStatistics">刷新统计</el-button>
        </el-form-item>
      </el-form>

      <el-row v-if="statisticsOverview" :gutter="14" class="element-grid">
        <el-col :xs="24" :sm="12" :lg="4">
          <el-statistic title="预约总量" :value="statisticsOverview.reservation_total" />
        </el-col>
        <el-col :xs="24" :sm="12" :lg="4">
          <el-statistic title="今日预约" :value="statisticsOverview.today_reservations" />
        </el-col>
        <el-col :xs="24" :sm="12" :lg="4">
          <el-statistic title="活跃用户" :value="statisticsOverview.active_users" />
        </el-col>
        <el-col :xs="24" :sm="12" :lg="4">
          <el-statistic title="场地使用率" :value="statisticsOverview.utilization_rate" suffix="%" />
        </el-col>
        <el-col :xs="24" :sm="12" :lg="4">
          <el-statistic title="启用场地" :value="statisticsOverview.enabled_courts" />
        </el-col>
        <el-col :xs="24" :sm="12" :lg="4">
          <el-statistic title="已完成预约" :value="statisticsOverview.completed_reservations" />
        </el-col>
      </el-row>

      <el-row :gutter="16" class="element-grid">
        <el-col :xs="24" :lg="12">
          <el-card shadow="never" class="panel-card">
            <template #header><strong>场地使用率</strong></template>
            <el-table :data="usageTable" empty-text="暂无场地统计数据">
              <el-table-column label="场地" min-width="150">
                <template #default="{ row }">{{ row.court_no }} {{ row.court_name }}</template>
              </el-table-column>
              <el-table-column prop="active_count" label="有效预约" width="100" />
              <el-table-column label="使用率" min-width="180">
                <template #default="{ row }">
                  <el-progress :percentage="row.progress" />
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="12">
          <el-card shadow="never" class="panel-card">
            <template #header><strong>热门时间段</strong></template>
            <el-table :data="timeSlotStatistics" empty-text="暂无时间段统计数据">
              <el-table-column prop="time_slot" label="时间段" />
              <el-table-column prop="reservation_count" label="预约次数" width="120" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" class="panel-card">
        <template #header><strong>用户活跃度</strong></template>
        <el-table :data="userStatistics" empty-text="暂无用户统计数据" stripe>
          <el-table-column label="用户" min-width="130">
            <template #default="{ row }">{{ row.nickname || row.username }}</template>
          </el-table-column>
          <el-table-column prop="reservation_count" label="预约总数" />
          <el-table-column prop="confirmed_count" label="已确认" />
          <el-table-column prop="completed_count" label="已完成" />
          <el-table-column prop="canceled_count" label="已取消" />
          <el-table-column prop="last_reserve_date" label="最近预约日期" min-width="130" />
        </el-table>
      </el-card>
    </section>

    <section v-if="activeTab === 'users'" v-loading="loading" class="admin-section">
      <el-card shadow="never" class="panel-card">
        <template #header><strong>新增用户</strong></template>
        <el-form inline class="element-filter" @submit.prevent="submitUser">
          <el-form-item label="用户名"><el-input v-model="userForm.username" /></el-form-item>
          <el-form-item label="密码"><el-input v-model="userForm.password" type="password" show-password /></el-form-item>
          <el-form-item label="昵称"><el-input v-model="userForm.nickname" /></el-form-item>
          <el-form-item label="联系方式"><el-input v-model="userForm.contact" /></el-form-item>
          <el-form-item label="角色">
            <el-select v-model="userForm.role" class="short-select">
              <el-option label="user" value="user" />
              <el-option label="admin" value="admin" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="userForm.status" class="short-select">
              <el-option label="启用" :value="1" />
              <el-option label="禁用" :value="0" />
            </el-select>
          </el-form-item>
          <el-form-item><el-button type="primary" native-type="submit">新增用户</el-button></el-form-item>
        </el-form>
      </el-card>

      <el-form inline class="element-filter">
        <el-form-item label="角色">
          <el-select v-model="userFilters.role" clearable class="short-select" @change="refreshUsers(true)">
            <el-option label="user" value="user" />
            <el-option label="admin" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="userFilters.status" clearable class="short-select" @change="refreshUsers(true)">
            <el-option label="启用" value="1" />
            <el-option label="禁用" value="0" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table :data="users" empty-text="暂无用户数据" stripe>
        <el-table-column prop="username" label="用户名" min-width="110" />
        <el-table-column prop="nickname" label="昵称" min-width="110" />
        <el-table-column prop="contact" label="联系方式" min-width="130" />
        <el-table-column label="角色" min-width="120">
          <template #default="{ row }">
            <el-select :model-value="row.role" size="small" @change="changeUserRoleValue(row, $event)">
              <el-option label="user" value="user" />
              <el-option label="admin" value="admin" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="会员" min-width="170">
          <template #default="{ row }">
            <el-tag effect="plain">{{ row.member.level_label }}</el-tag>
            <div class="table-subtext">{{ memberValidity(row.member.expires_at) }} / {{ discountText(row.member.effective_discount_rate) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="余额" min-width="110">
          <template #default="{ row }">{{ formatMoney(row.member.balance_cents) }}</template>
        </el-table-column>
        <el-table-column label="积分" min-width="90">
          <template #default="{ row }">{{ row.member.points }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" effect="plain">{{ row.status === 1 ? "启用" : "禁用" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="230">
          <template #default="{ row }">
            <el-button link type="warning" @click="toggleUserStatus(row)">{{ row.status === 1 ? "禁用" : "启用" }}</el-button>
            <el-button link type="primary" @click="editUserMember(row)">会员</el-button>
            <el-button link type="danger" @click="resetUserPassword(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="userPage.page" :page-size="userPage.page_size" :total="userPage.total" layout="prev, pager, next, total" @current-change="changeUserPage" />
    </section>

    <section v-if="activeTab === 'courts'" v-loading="loading" class="admin-section">
      <el-card shadow="never" class="panel-card">
        <template #header><strong>新增场地</strong></template>
        <el-form inline class="element-filter" @submit.prevent="submitCourt">
          <el-form-item label="编号"><el-input v-model="courtForm.court_no" /></el-form-item>
          <el-form-item label="名称"><el-input v-model="courtForm.court_name" /></el-form-item>
          <el-form-item label="说明"><el-input v-model="courtForm.description" /></el-form-item>
          <el-form-item label="价格"><el-input v-model="courtForm.price_per_hour_yuan" /></el-form-item>
          <el-form-item label="图片"><el-input v-model="courtForm.image_url" /></el-form-item>
          <el-form-item label="标签"><el-input v-model="courtForm.tags_text" /></el-form-item>
          <el-form-item label="人数"><el-input-number v-model="courtForm.capacity" :min="1" :max="50" /></el-form-item>
          <el-form-item label="状态">
            <el-select v-model="courtForm.status" class="short-select">
              <el-option label="启用" :value="1" />
              <el-option label="停用" :value="0" />
            </el-select>
          </el-form-item>
          <el-form-item><el-button type="primary" native-type="submit">新增场地</el-button></el-form-item>
        </el-form>
      </el-card>

      <el-form inline class="element-filter">
        <el-form-item label="状态">
          <el-select v-model="courtStatus" clearable class="short-select" @change="refreshCourts(true)">
            <el-option label="启用" value="1" />
            <el-option label="停用" value="0" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table :data="courts" empty-text="暂无场地数据" stripe>
        <el-table-column prop="court_no" label="编号" width="90" />
        <el-table-column prop="court_name" label="名称" min-width="120" />
        <el-table-column prop="description" label="说明" min-width="180" />
        <el-table-column label="价格" width="120"><template #default="{ row }">{{ formatMoney(row.price_per_hour_cents) }}/小时</template></el-table-column>
        <el-table-column label="标签" min-width="170"><template #default="{ row }">{{ row.tags?.join("，") || "-" }}</template></el-table-column>
        <el-table-column prop="capacity" label="人数" width="80" />
        <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'" effect="plain">{{ row.status === 1 ? "启用" : "停用" }}</el-tag></template></el-table-column>
        <el-table-column label="操作" fixed="right" width="140">
          <template #default="{ row }">
            <el-button link type="primary" @click="editCourt(row)">编辑</el-button>
            <el-button link type="warning" @click="toggleCourtStatus(row)">{{ row.status === 1 ? "停用" : "启用" }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="courtPage.page" :page-size="courtPage.page_size" :total="courtPage.total" layout="prev, pager, next, total" @current-change="changeCourtPage" />
    </section>

    <section v-if="activeTab === 'reservations'" v-loading="loading" class="admin-section">
      <el-form inline class="element-filter">
        <el-form-item label="状态">
          <el-select v-model="reservationFilters.status" clearable class="short-select" @change="refreshReservations(true)">
            <el-option label="已确认" value="confirmed" />
            <el-option label="已取消" value="canceled" />
            <el-option label="待支付" value="pending" />
            <el-option label="已完成" value="completed" />
            <el-option label="已过期" value="expired" />
          </el-select>
        </el-form-item>
        <el-form-item label="用户"><el-input v-model="reservationFilters.username" placeholder="用户名或昵称" @keyup.enter="refreshReservations(true)" /></el-form-item>
        <el-form-item label="场地">
          <el-select v-model="reservationFilters.court_id" clearable filterable class="medium-select" @change="refreshReservations(true)">
            <el-option v-for="court in courtOptions" :key="court.id" :label="`${court.court_no} ${court.court_name}`" :value="String(court.id)" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="reservationFilters.date_from" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="reservationFilters.date_to" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item><el-button type="primary" @click="refreshReservations(true)">查询预约</el-button></el-form-item>
      </el-form>

      <el-table :data="reservations" empty-text="暂无预约数据" stripe>
        <el-table-column prop="reservation_no" label="预约号" min-width="160" />
        <el-table-column label="用户" min-width="130"><template #default="{ row }">{{ row.nickname || row.username }}</template></el-table-column>
        <el-table-column prop="court_name" label="场地" min-width="110" />
        <el-table-column prop="reserve_date" label="日期" min-width="115" />
        <el-table-column label="时间" min-width="130"><template #default="{ row }">{{ row.start_time }}-{{ row.end_time }}</template></el-table-column>
        <el-table-column label="会员" min-width="130"><template #default="{ row }">{{ row.member_level_snapshot }} / {{ discountText(row.discount_rate) }}</template></el-table-column>
        <el-table-column label="应付金额" min-width="120"><template #default="{ row }">{{ formatMoney(row.payable_amount_cents) }}</template></el-table-column>
        <el-table-column label="状态" min-width="100"><template #default="{ row }"><el-tag :type="statusTagType(row.status)" effect="plain">{{ reservationStatusText(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="支付截止" min-width="160"><template #default="{ row }">{{ row.status === "pending" ? row.order_expires_at || "-" : "-" }}</template></el-table-column>
        <el-table-column label="操作" fixed="right" width="100"><template #default="{ row }"><el-button link type="danger" :disabled="!['pending', 'confirmed'].includes(row.status)" @click="cancelAdminReservation(row)">取消</el-button></template></el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="reservationPage.page" :page-size="reservationPage.page_size" :total="reservationPage.total" layout="prev, pager, next, total" @current-change="changeReservationPage" />
    </section>

    <section v-if="activeTab === 'announcements'" v-loading="loading" class="admin-section">
      <el-card shadow="never" class="panel-card">
        <template #header><strong>新增公告</strong></template>
        <el-form label-position="top" class="element-form" @submit.prevent="submitAnnouncement">
          <el-form-item label="公告标题"><el-input v-model="announcementForm.title" /></el-form-item>
          <el-form-item label="公告内容"><el-input v-model="announcementForm.content" type="textarea" :rows="4" /></el-form-item>
          <el-form-item label="状态">
            <el-select v-model="announcementForm.status" class="short-select">
              <el-option label="显示" :value="1" />
              <el-option label="隐藏" :value="0" />
            </el-select>
          </el-form-item>
          <el-button type="primary" native-type="submit">新增公告</el-button>
        </el-form>
      </el-card>

      <el-form inline class="element-filter">
        <el-form-item label="状态">
          <el-select v-model="announcementStatus" clearable class="short-select" @change="refreshAnnouncements(true)">
            <el-option label="显示" value="1" />
            <el-option label="隐藏" value="0" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table :data="announcements" empty-text="暂无公告数据" stripe>
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'" effect="plain">{{ row.status === 1 ? "显示" : "隐藏" }}</el-tag></template></el-table-column>
        <el-table-column prop="updated_at" label="更新时间" min-width="170" />
        <el-table-column label="操作" fixed="right" width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click="editAnnouncement(row)">编辑</el-button>
            <el-button link type="warning" @click="toggleAnnouncementStatus(row)">{{ row.status === 1 ? "隐藏" : "显示" }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="announcementPage.page" :page-size="announcementPage.page_size" :total="announcementPage.total" layout="prev, pager, next, total" @current-change="changeAnnouncementPage" />
    </section>

    <section v-if="activeTab === 'notifications'" v-loading="loading" class="admin-section">
      <el-card shadow="never" class="panel-card">
        <template #header><strong>全员通知</strong></template>
        <el-alert title="此处发送给全部启用账号。预约、取消、会员调整和公告发布会由系统自动发送通知。" type="info" show-icon :closable="false" />
        <el-form label-position="top" class="element-form dialog-form" @submit.prevent="submitBroadcastNotification">
          <el-form-item label="通知标题">
            <el-input v-model="broadcastForm.title" maxlength="100" show-word-limit />
          </el-form-item>
          <el-form-item label="通知内容">
            <el-input v-model="broadcastForm.content" type="textarea" :rows="6" maxlength="2000" show-word-limit />
          </el-form-item>
          <el-button type="primary" :loading="loading" native-type="submit">发送通知</el-button>
        </el-form>
      </el-card>
    </section>

    <section v-if="activeTab === 'events'" v-loading="loading" class="admin-section">
      <el-card shadow="never" class="panel-card">
        <template #header><strong>新增活动</strong></template>
        <el-form label-position="top" class="element-form admin-grid-form" @submit.prevent="submitEvent">
          <el-form-item label="活动标题"><el-input v-model="eventForm.title" /></el-form-item>
          <el-form-item label="活动地点"><el-input v-model="eventForm.location" /></el-form-item>
          <el-form-item label="开始时间"><el-date-picker v-model="eventForm.start_at" type="datetime" value-format="YYYY-MM-DD HH:mm" /></el-form-item>
          <el-form-item label="结束时间"><el-date-picker v-model="eventForm.end_at" type="datetime" value-format="YYYY-MM-DD HH:mm" /></el-form-item>
          <el-form-item label="报名截止"><el-date-picker v-model="eventForm.registration_deadline" type="datetime" value-format="YYYY-MM-DD HH:mm" /></el-form-item>
          <el-form-item label="容量"><el-input-number v-model="eventForm.capacity" :min="1" :max="9999" /></el-form-item>
          <el-form-item label="状态">
            <el-select v-model="eventForm.status" class="short-select">
              <el-option label="显示" :value="1" />
              <el-option label="隐藏" :value="0" />
            </el-select>
          </el-form-item>
          <el-form-item label="活动内容" class="form-span-2"><el-input v-model="eventForm.content" type="textarea" :rows="4" /></el-form-item>
          <el-form-item><el-button type="primary" native-type="submit">新增活动</el-button></el-form-item>
        </el-form>
      </el-card>

      <el-form inline class="element-filter">
        <el-form-item label="状态">
          <el-select v-model="eventStatus" clearable class="short-select" @change="refreshEvents(true)">
            <el-option label="显示" value="1" />
            <el-option label="隐藏" value="0" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table :data="events" empty-text="暂无活动数据" stripe>
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column prop="location" label="地点" min-width="120" />
        <el-table-column prop="start_at" label="开始时间" min-width="160" />
        <el-table-column label="报名" width="100"><template #default="{ row }">{{ row.registered_count }}/{{ row.capacity }}</template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'" effect="plain">{{ row.status === 1 ? "显示" : "隐藏" }}</el-tag></template></el-table-column>
        <el-table-column label="操作" fixed="right" width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click="editEvent(row)">编辑</el-button>
            <el-button link type="warning" @click="toggleEventStatus(row)">{{ row.status === 1 ? "隐藏" : "显示" }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="eventPage.page" :page-size="eventPage.page_size" :total="eventPage.total" layout="prev, pager, next, total" @current-change="changeEventPage" />
    </section>

    <section v-if="activeTab === 'community'" v-loading="loading" class="admin-section">
      <el-form inline class="element-filter">
        <el-form-item label="状态">
          <el-select v-model="communityStatus" clearable class="short-select" @change="refreshCommunityPosts(true)">
            <el-option label="显示" value="1" />
            <el-option label="隐藏" value="0" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table :data="communityPosts" empty-text="暂无动态数据" stripe>
        <el-table-column label="用户" min-width="120"><template #default="{ row }">{{ row.nickname || row.username }}</template></el-table-column>
        <el-table-column prop="content" label="内容" min-width="280" />
        <el-table-column prop="created_at" label="发布时间" min-width="170" />
        <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'" effect="plain">{{ row.status === 1 ? "显示" : "隐藏" }}</el-tag></template></el-table-column>
        <el-table-column label="操作" fixed="right" width="100"><template #default="{ row }"><el-button link type="warning" :disabled="row.status !== 1" @click="hideAdminCommunityPost(row)">隐藏</el-button></template></el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="communityPage.page" :page-size="communityPage.page_size" :total="communityPage.total" layout="prev, pager, next, total" @current-change="changeCommunityPage" />
    </section>

    <section v-if="activeTab === 'shop'" v-loading="loading" class="admin-section">
      <el-card shadow="never" class="panel-card">
        <template #header><strong>新增商品</strong></template>
        <el-form inline class="element-filter" @submit.prevent="submitShopProduct">
          <el-form-item label="编号"><el-input v-model="shopProductForm.product_no" /></el-form-item>
          <el-form-item label="名称"><el-input v-model="shopProductForm.product_name" /></el-form-item>
          <el-form-item label="价格"><el-input v-model="shopProductForm.price_yuan" /></el-form-item>
          <el-form-item label="库存"><el-input-number v-model="shopProductForm.stock" :min="0" :max="999999" /></el-form-item>
          <el-form-item label="状态">
            <el-select v-model="shopProductForm.status" class="short-select">
              <el-option label="上架" :value="1" />
              <el-option label="下架" :value="0" />
            </el-select>
          </el-form-item>
          <el-form-item label="图片"><el-input v-model="shopProductForm.image_url" /></el-form-item>
          <el-form-item label="说明"><el-input v-model="shopProductForm.description" /></el-form-item>
          <el-form-item><el-button type="primary" native-type="submit">新增商品</el-button></el-form-item>
        </el-form>
      </el-card>

      <el-card shadow="never" class="panel-card">
        <template #header><strong>商品管理</strong></template>
        <el-form inline class="element-filter">
          <el-form-item label="状态">
            <el-select v-model="shopProductFilters.status" clearable class="short-select" @change="refreshShopProducts(true)">
              <el-option label="上架" value="1" />
              <el-option label="下架" value="0" />
            </el-select>
          </el-form-item>
          <el-form-item label="商品"><el-input v-model="shopProductFilters.keyword" placeholder="编号或名称" @keyup.enter="refreshShopProducts(true)" /></el-form-item>
          <el-form-item><el-button type="primary" @click="refreshShopProducts(true)">查询商品</el-button></el-form-item>
        </el-form>
        <el-table :data="shopProducts" empty-text="暂无商品数据" stripe>
          <el-table-column prop="product_no" label="编号" min-width="100" />
          <el-table-column prop="product_name" label="名称" min-width="150" />
          <el-table-column label="价格" width="110"><template #default="{ row }">{{ formatMoney(row.price_cents) }}</template></el-table-column>
          <el-table-column prop="stock" label="库存" width="90" />
          <el-table-column prop="sold_count" label="销量" width="90" />
          <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'" effect="plain">{{ row.status === 1 ? "上架" : "下架" }}</el-tag></template></el-table-column>
          <el-table-column label="操作" fixed="right" width="140">
            <template #default="{ row }">
              <el-button link type="primary" @click="editShopProduct(row)">编辑</el-button>
              <el-button link type="warning" @click="toggleShopProductStatus(row)">{{ row.status === 1 ? "下架" : "上架" }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination class="element-pagination" :current-page="shopProductPage.page" :page-size="shopProductPage.page_size" :total="shopProductPage.total" layout="prev, pager, next, total" @current-change="changeShopProductPage" />
      </el-card>

      <el-card shadow="never" class="panel-card">
        <template #header><strong>订单管理</strong></template>
        <el-form inline class="element-filter">
          <el-form-item label="状态">
            <el-select v-model="shopOrderFilters.status" clearable class="short-select" @change="refreshShopOrders(true)">
              <el-option label="已支付" value="paid" />
              <el-option label="已完成" value="completed" />
              <el-option label="已取消" value="canceled" />
            </el-select>
          </el-form-item>
          <el-form-item label="用户"><el-input v-model="shopOrderFilters.username" placeholder="用户名或昵称" @keyup.enter="refreshShopOrders(true)" /></el-form-item>
          <el-form-item><el-button type="primary" @click="refreshShopOrders(true)">查询订单</el-button></el-form-item>
        </el-form>
        <el-table :data="shopOrders" empty-text="暂无商城订单" stripe>
          <el-table-column prop="order_no" label="订单号" min-width="160" />
          <el-table-column label="用户" min-width="120"><template #default="{ row }">{{ row.nickname || row.username }}</template></el-table-column>
          <el-table-column label="金额" width="120"><template #default="{ row }">{{ formatMoney(row.total_amount_cents) }}</template></el-table-column>
          <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="shopOrderStatusType(row.status)" effect="plain">{{ shopOrderStatusText(row.status) }}</el-tag></template></el-table-column>
          <el-table-column prop="created_at" label="创建时间" min-width="170" />
          <el-table-column label="操作" fixed="right" width="170">
            <template #default="{ row }">
              <el-button link type="primary" :disabled="row.status !== 'paid'" @click="completeShopOrder(row)">完成</el-button>
              <el-button link type="warning" :disabled="row.status !== 'paid'" @click="cancelAdminShopOrder(row)">取消退款</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination class="element-pagination" :current-page="shopOrderPage.page" :page-size="shopOrderPage.page_size" :total="shopOrderPage.total" layout="prev, pager, next, total" @current-change="changeShopOrderPage" />
      </el-card>
    </section>

    <section v-if="activeTab === 'configs'" v-loading="loading" class="admin-section">
      <el-table :data="configs" empty-text="暂无规则配置" stripe>
        <el-table-column prop="config_key" label="配置键" min-width="220" />
        <el-table-column prop="config_value" label="配置值" min-width="160" />
        <el-table-column prop="description" label="说明" min-width="260" />
        <el-table-column label="操作" fixed="right" width="100"><template #default="{ row }"><el-button link type="primary" @click="editConfig(row)">编辑</el-button></template></el-table-column>
      </el-table>
    </section>

    <section v-if="activeTab === 'logs'" v-loading="loading" class="admin-section">
      <el-form inline class="element-filter">
        <el-form-item label="模块">
          <el-select v-model="logFilters.module" clearable class="short-select" @change="refreshOperationLogs(true)">
            <el-option label="用户" value="user" />
            <el-option label="场地" value="court" />
            <el-option label="预约" value="reservation" />
            <el-option label="公告" value="announcement" />
            <el-option label="通知" value="notification" />
            <el-option label="活动" value="event" />
            <el-option label="球友圈" value="community" />
            <el-option label="商城" value="shop" />
            <el-option label="规则" value="config" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作">
          <el-select v-model="logFilters.action" clearable class="short-select" @change="refreshOperationLogs(true)">
            <el-option label="create" value="create" />
            <el-option label="update" value="update" />
            <el-option label="status" value="status" />
            <el-option label="role" value="role" />
            <el-option label="member" value="member" />
            <el-option label="cancel" value="cancel" />
            <el-option label="hide" value="hide" />
            <el-option label="broadcast" value="broadcast" />
            <el-option label="complete" value="complete" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作人"><el-input v-model="logFilters.username" placeholder="用户名" @keyup.enter="refreshOperationLogs(true)" /></el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="logFilters.date_from" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="logFilters.date_to" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item><el-button type="primary" @click="refreshOperationLogs(true)">查询日志</el-button></el-form-item>
      </el-form>

      <el-table :data="operationLogs" empty-text="暂无操作日志" stripe>
        <el-table-column prop="created_at" label="时间" min-width="170" />
        <el-table-column label="操作人" min-width="120"><template #default="{ row }">{{ row.username || "-" }}</template></el-table-column>
        <el-table-column prop="module" label="模块" width="110" />
        <el-table-column prop="action" label="操作" width="110" />
        <el-table-column label="目标" min-width="130"><template #default="{ row }">{{ row.target_type || "-" }} #{{ row.target_id || "-" }}</template></el-table-column>
        <el-table-column label="详情" min-width="260"><template #default="{ row }">{{ operationDetail(row.detail) }}</template></el-table-column>
        <el-table-column label="IP" min-width="130"><template #default="{ row }">{{ row.ip || "-" }}</template></el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="logPage.page" :page-size="logPage.page_size" :total="logPage.total" layout="prev, pager, next, total" @current-change="changeLogPage" />
    </section>
  </el-card>

  <el-dialog :model-value="Boolean(editingMemberUser)" title="调整会员" width="560px" @close="resetMemberForm">
    <el-alert title="余额和积分填写本次增减值，正数为增加，负数为扣减，不是账户最终值。" type="info" show-icon :closable="false" />
    <el-form label-position="top" class="element-form dialog-form" @submit.prevent="submitMember">
      <el-form-item label="会员等级">
        <el-select v-model="memberForm.member_level">
          <el-option v-for="level in memberLevelOptions" :key="level.value" :label="level.label" :value="level.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="有效期">
        <el-date-picker v-model="memberForm.expires_at" type="date" value-format="YYYY-MM-DD" placeholder="不填表示长期有效" />
      </el-form-item>
      <el-form-item label="余额增减（元）"><el-input v-model="memberForm.balance_change_yuan" placeholder="如 50 或 -20" /></el-form-item>
      <el-form-item label="积分增减"><el-input-number v-model="memberForm.points_change" /></el-form-item>
      <el-form-item label="调整原因"><el-input v-model="memberForm.reason" placeholder="默认：后台调整会员账户" /></el-form-item>
      <div class="dialog-actions">
        <el-button @click="resetMemberForm">取消</el-button>
        <el-button type="primary" :loading="loading" native-type="submit">保存会员</el-button>
      </div>
    </el-form>
  </el-dialog>

  <el-dialog :model-value="Boolean(resettingPasswordUser)" title="重置密码" width="460px" @close="resetPasswordDialog">
    <el-form label-position="top" class="element-form" @submit.prevent="submitResetPassword">
      <el-alert title="新密码至少 6 位。保存后该用户旧登录态会失效。" type="warning" show-icon :closable="false" />
      <el-form-item label="新密码"><el-input v-model="resetPasswordForm.password" type="password" show-password /></el-form-item>
      <div class="dialog-actions">
        <el-button @click="resetPasswordDialog">取消</el-button>
        <el-button type="primary" :loading="loading" native-type="submit">重置密码</el-button>
      </div>
    </el-form>
  </el-dialog>

  <el-dialog :model-value="Boolean(editingCourtId)" :title="`编辑场地：${editingCourt?.court_name || ''}`" width="680px" @close="resetCourtForm">
    <el-alert title="修改场地资料会影响后续展示和新预约价格；历史预约保留创建时的金额快照。" type="info" show-icon :closable="false" />
    <el-form label-position="top" class="element-form dialog-form" @submit.prevent="submitCourt">
      <el-form-item label="场地编号"><el-input v-model="courtEditForm.court_no" /></el-form-item>
      <el-form-item label="场地名称"><el-input v-model="courtEditForm.court_name" /></el-form-item>
      <el-form-item label="说明"><el-input v-model="courtEditForm.description" /></el-form-item>
      <el-form-item label="每小时价格（元）"><el-input v-model="courtEditForm.price_per_hour_yuan" /></el-form-item>
      <el-form-item label="图片路径"><el-input v-model="courtEditForm.image_url" /></el-form-item>
      <el-form-item label="标签"><el-input v-model="courtEditForm.tags_text" /></el-form-item>
      <el-form-item label="容纳人数"><el-input-number v-model="courtEditForm.capacity" :min="1" :max="50" /></el-form-item>
      <el-form-item label="状态">
        <el-select v-model="courtEditForm.status">
          <el-option label="启用" :value="1" />
          <el-option label="停用" :value="0" />
        </el-select>
      </el-form-item>
      <div class="dialog-actions">
        <el-button @click="resetCourtForm">取消</el-button>
        <el-button type="primary" :loading="loading" native-type="submit">保存场地</el-button>
      </div>
    </el-form>
  </el-dialog>

  <el-dialog :model-value="Boolean(editingAnnouncementId)" :title="`编辑公告：${editingAnnouncement?.title || ''}`" width="640px" @close="resetAnnouncementForm">
    <el-form label-position="top" class="element-form" @submit.prevent="submitAnnouncement">
      <el-form-item label="公告标题"><el-input v-model="announcementEditForm.title" /></el-form-item>
      <el-form-item label="公告内容"><el-input v-model="announcementEditForm.content" type="textarea" :rows="5" /></el-form-item>
      <el-form-item label="状态">
        <el-select v-model="announcementEditForm.status">
          <el-option label="显示" :value="1" />
          <el-option label="隐藏" :value="0" />
        </el-select>
      </el-form-item>
      <div class="dialog-actions">
        <el-button @click="resetAnnouncementForm">取消</el-button>
        <el-button type="primary" :loading="loading" native-type="submit">保存公告</el-button>
      </div>
    </el-form>
  </el-dialog>

  <el-dialog :model-value="Boolean(editingEventId)" :title="`编辑活动：${editingEvent?.title || ''}`" width="680px" @close="resetEventForm">
    <el-alert title="隐藏活动会通知已报名用户；容量不能小于当前已报名人数。" type="info" show-icon :closable="false" />
    <el-form label-position="top" class="element-form dialog-form" @submit.prevent="submitEvent">
      <el-form-item label="活动标题"><el-input v-model="eventEditForm.title" /></el-form-item>
      <el-form-item label="活动地点"><el-input v-model="eventEditForm.location" /></el-form-item>
      <el-form-item label="开始时间"><el-date-picker v-model="eventEditForm.start_at" type="datetime" value-format="YYYY-MM-DD HH:mm" /></el-form-item>
      <el-form-item label="结束时间"><el-date-picker v-model="eventEditForm.end_at" type="datetime" value-format="YYYY-MM-DD HH:mm" /></el-form-item>
      <el-form-item label="报名截止"><el-date-picker v-model="eventEditForm.registration_deadline" type="datetime" value-format="YYYY-MM-DD HH:mm" /></el-form-item>
      <el-form-item label="容量"><el-input-number v-model="eventEditForm.capacity" :min="1" :max="9999" /></el-form-item>
      <el-form-item label="状态">
        <el-select v-model="eventEditForm.status">
          <el-option label="显示" :value="1" />
          <el-option label="隐藏" :value="0" />
        </el-select>
      </el-form-item>
      <el-form-item label="活动内容"><el-input v-model="eventEditForm.content" type="textarea" :rows="5" /></el-form-item>
      <div class="dialog-actions">
        <el-button @click="resetEventForm">取消</el-button>
        <el-button type="primary" :loading="loading" native-type="submit">保存活动</el-button>
      </div>
    </el-form>
  </el-dialog>

  <el-dialog :model-value="Boolean(editingShopProductId)" :title="`编辑商品：${editingShopProduct?.product_name || ''}`" width="640px" @close="resetShopProductForm">
    <el-alert title="库存为当前可售库存；已支付订单取消时会自动退回库存。" type="info" show-icon :closable="false" />
    <el-form label-position="top" class="element-form dialog-form" @submit.prevent="submitShopProduct">
      <el-form-item label="商品编号"><el-input v-model="shopProductEditForm.product_no" /></el-form-item>
      <el-form-item label="商品名称"><el-input v-model="shopProductEditForm.product_name" /></el-form-item>
      <el-form-item label="价格（元）"><el-input v-model="shopProductEditForm.price_yuan" /></el-form-item>
      <el-form-item label="库存"><el-input-number v-model="shopProductEditForm.stock" :min="0" :max="999999" /></el-form-item>
      <el-form-item label="图片路径"><el-input v-model="shopProductEditForm.image_url" /></el-form-item>
      <el-form-item label="状态">
        <el-select v-model="shopProductEditForm.status">
          <el-option label="上架" :value="1" />
          <el-option label="下架" :value="0" />
        </el-select>
      </el-form-item>
      <el-form-item label="商品说明"><el-input v-model="shopProductEditForm.description" type="textarea" :rows="4" /></el-form-item>
      <div class="dialog-actions">
        <el-button @click="resetShopProductForm">取消</el-button>
        <el-button type="primary" :loading="loading" native-type="submit">保存商品</el-button>
      </div>
    </el-form>
  </el-dialog>

  <el-dialog :model-value="Boolean(editingConfig)" :title="`编辑规则：${editingConfig?.config_key || ''}`" width="520px" @close="resetConfigForm">
    <el-alert :title="editingConfig?.description || '修改后会影响后续业务判断。'" type="info" show-icon :closable="false" />
    <el-form label-position="top" class="element-form" @submit.prevent="submitConfig">
      <el-form-item label="配置值"><el-input v-model="configForm.config_value" /></el-form-item>
      <div class="dialog-actions">
        <el-button @click="resetConfigForm">取消</el-button>
        <el-button type="primary" :loading="loading" native-type="submit">保存规则</el-button>
      </div>
    </el-form>
  </el-dialog>
</template>
