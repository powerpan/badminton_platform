<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import type { Announcement } from "../api/announcement";
import {
  adminCancelReservation,
  adminCreateAnnouncement,
  adminCreateCourt,
  adminCreateUser,
  adminGetAnnouncements,
  adminGetConfigs,
  adminGetCourtStatistics,
  adminGetCourts,
  adminGetOperationLogs,
  adminGetReservations,
  adminGetStatisticsOverview,
  adminGetTimeSlotStatistics,
  adminGetUserStatistics,
  adminGetUsers,
  adminResetUserPassword,
  adminUpdateAnnouncement,
  adminUpdateAnnouncementStatus,
  adminUpdateConfig,
  adminUpdateCourt,
  adminUpdateCourtStatus,
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
import type { Court } from "../api/court";
import type { Reservation } from "../api/reservation";
import { useAuthStore } from "../stores/auth";

type AdminTab = "statistics" | "users" | "courts" | "reservations" | "announcements" | "configs" | "logs";

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
  if (!(await confirmAction(`确认取消预约 ${reservation.reservation_no}？`))) return;
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
    <p>集中管理统计、用户、场地、预约、公告、规则配置和操作日志。</p>
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
            <el-option label="confirmed" value="confirmed" />
            <el-option label="canceled" value="canceled" />
            <el-option label="pending" value="pending" />
            <el-option label="completed" value="completed" />
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
        <el-table-column label="状态" min-width="100"><template #default="{ row }"><el-tag :type="statusTagType(row.status)" effect="plain">{{ row.status }}</el-tag></template></el-table-column>
        <el-table-column label="操作" fixed="right" width="100"><template #default="{ row }"><el-button link type="danger" :disabled="row.status !== 'confirmed'" @click="cancelAdminReservation(row)">取消</el-button></template></el-table-column>
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
