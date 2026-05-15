<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

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
  adminUpdateUserRole,
  adminUpdateUserStatus,
  type CourtStatistic,
  type ConfigItem,
  type OperationLog,
  type StatisticsOverview,
  type TimeSlotStatistic,
  type UserStatistic,
} from "../api/admin";
import type { UserInfo } from "../api/auth";
import type { Court } from "../api/court";
import type { Reservation } from "../api/reservation";

type AdminTab = "statistics" | "users" | "courts" | "reservations" | "announcements" | "configs" | "logs";
interface PageState {
  page: number;
  page_size: number;
  total: number;
}

const tabs: Array<{ key: AdminTab; label: string }> = [
  { key: "statistics", label: "统计" },
  { key: "users", label: "用户" },
  { key: "courts", label: "场地" },
  { key: "reservations", label: "预约" },
  { key: "announcements", label: "公告" },
  { key: "configs", label: "规则" },
  { key: "logs", label: "日志" },
];

const activeTab = ref<AdminTab>("statistics");
const loading = ref(false);
const message = ref("");
const errorMessage = ref("");

function formatDate(value: Date) {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

function addDays(days: number) {
  const value = new Date();
  value.setDate(value.getDate() + days);
  return formatDate(value);
}

const statsRange = ref({
  date_from: addDays(0),
  date_to: addDays(6),
});
const statisticsOverview = ref<StatisticsOverview | null>(null);
const courtStatistics = ref<CourtStatistic[]>([]);
const timeSlotStatistics = ref<TimeSlotStatistic[]>([]);
const userStatistics = ref<UserStatistic[]>([]);
const maxCourtActiveCount = computed(() => Math.max(0, ...courtStatistics.value.map((item) => item.active_count)));
const maxTimeSlotCount = computed(() => Math.max(0, ...timeSlotStatistics.value.map((item) => item.reservation_count)));

const users = ref<UserInfo[]>([]);
const userPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });
const userFilters = ref({ role: "", status: "" });
const userForm = ref({
  username: "",
  password: "",
  nickname: "",
  contact: "",
  role: "user",
  status: 1,
});

const courts = ref<Court[]>([]);
const courtOptions = ref<Court[]>([]);
const courtPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });
const courtStatus = ref("");
const editingCourtId = ref<number | null>(null);
const courtForm = ref({
  court_no: "",
  court_name: "",
  description: "",
  price_per_hour_yuan: "120",
  image_url: "/courts/default-court.png",
  tags_text: "空调开放,标准场地",
  capacity: 6,
  status: 1,
});

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
const editingAnnouncementId = ref<number | null>(null);
const announcementForm = ref({
  title: "",
  content: "",
  status: 1,
});

const configs = ref<ConfigItem[]>([]);

const operationLogs = ref<OperationLog[]>([]);
const logPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });
const logFilters = ref({
  module: "",
  action: "",
  username: "",
  date_from: "",
  date_to: "",
});

function setMessage(text: string) {
  message.value = text;
  errorMessage.value = "";
}

function setError(error: unknown, fallback: string) {
  errorMessage.value = error instanceof Error ? error.message : fallback;
  message.value = "";
}

function confirmAction(messageText: string) {
  return window.confirm(messageText);
}

function barWidth(value: number, max: number) {
  if (!max) return "0%";
  return `${Math.max(6, Math.round((value / max) * 100))}%`;
}

function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toFixed(0)}`;
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

function tagTextToArray(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function courtPayload() {
  return {
    court_no: courtForm.value.court_no,
    court_name: courtForm.value.court_name,
    description: courtForm.value.description,
    status: courtForm.value.status,
    price_per_hour_cents: yuanInputToCents(courtForm.value.price_per_hour_yuan),
    image_url: courtForm.value.image_url,
    tags: tagTextToArray(courtForm.value.tags_text),
    capacity: courtForm.value.capacity,
  };
}

function operationDetail(detail: string) {
  try {
    const parsed = JSON.parse(detail);
    return Object.entries(parsed)
      .map(([key, value]) => `${key}: ${value}`)
      .join("，");
  } catch {
    return detail || "-";
  }
}

function pageCount(pageState: PageState) {
  return Math.max(1, Math.ceil(pageState.total / pageState.page_size));
}

async function changePage(pageState: PageState, nextPage: number, loader: () => Promise<void>) {
  pageState.page = Math.min(Math.max(1, nextPage), pageCount(pageState));
  await loader();
}

function resetPage(pageState: PageState) {
  pageState.page = 1;
}

async function loadStatistics() {
  const params = {
    date_from: statsRange.value.date_from,
    date_to: statsRange.value.date_to,
  };
  const [overview, courts, timeSlots, users] = await Promise.all([
    adminGetStatisticsOverview(params),
    adminGetCourtStatistics(params),
    adminGetTimeSlotStatistics({ ...params, limit: 12 }),
    adminGetUserStatistics({ ...params, limit: 10 }),
  ]);
  statisticsOverview.value = overview.data;
  courtStatistics.value = courts.data.items;
  timeSlotStatistics.value = timeSlots.data.items;
  userStatistics.value = users.data.items;
}

async function refreshStatistics() {
  loading.value = true;
  try {
    await loadStatistics();
    setMessage("统计已刷新");
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
    setMessage("用户已创建");
  } catch (error) {
    setError(error, "创建用户失败");
  } finally {
    loading.value = false;
  }
}

async function toggleUserStatus(user: UserInfo) {
  const nextStatusLabel = user.status === 1 ? "禁用" : "启用";
  if (!confirmAction(`确认${nextStatusLabel}用户 ${user.username}？`)) return;
  loading.value = true;
  try {
    await adminUpdateUserStatus(user.id, user.status === 1 ? 0 : 1);
    await loadUsers();
    setMessage("用户状态已更新");
  } catch (error) {
    setError(error, "更新用户状态失败");
  } finally {
    loading.value = false;
  }
}

async function changeUserRole(user: UserInfo, event: Event) {
  const role = (event.target as HTMLSelectElement).value;
  if (role !== user.role && !confirmAction(`确认将用户 ${user.username} 的角色修改为 ${role}？`)) {
    (event.target as HTMLSelectElement).value = user.role;
    return;
  }
  loading.value = true;
  try {
    await adminUpdateUserRole(user.id, role);
    await loadUsers();
    setMessage("用户角色已更新");
  } catch (error) {
    setError(error, "更新用户角色失败");
    await loadUsers();
  } finally {
    loading.value = false;
  }
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

function editCourt(court: Court) {
  editingCourtId.value = court.id;
  courtForm.value = {
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
  courtForm.value = {
    court_no: "",
    court_name: "",
    description: "",
    price_per_hour_yuan: "120",
    image_url: "/courts/default-court.png",
    tags_text: "空调开放,标准场地",
    capacity: 6,
    status: 1,
  };
}

async function submitCourt() {
  if (editingCourtId.value && courtForm.value.status === 0 && !confirmAction("确认停用该场地？如存在未来预约，后端会拒绝停用。")) {
    return;
  }
  loading.value = true;
  try {
    const payload = courtPayload();
    if (editingCourtId.value) {
      await adminUpdateCourt(editingCourtId.value, payload);
      setMessage("场地已更新");
    } else {
      await adminCreateCourt(payload);
      setMessage("场地已创建");
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

async function toggleCourtStatus(court: Court) {
  const nextStatusLabel = court.status === 1 ? "停用" : "启用";
  if (!confirmAction(`确认${nextStatusLabel}场地 ${court.court_no} ${court.court_name}？`)) return;
  loading.value = true;
  try {
    await adminUpdateCourtStatus(court.id, court.status === 1 ? 0 : 1);
    courtOptions.value = [];
    await loadCourts();
    setMessage("场地状态已更新");
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
  if (!confirmAction(`确认取消预约 ${reservation.reservation_no}？`)) return;
  loading.value = true;
  try {
    await adminCancelReservation(reservation.id);
    await loadReservations();
    setMessage("预约已取消");
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

function editAnnouncement(announcement: Announcement) {
  editingAnnouncementId.value = announcement.id;
  announcementForm.value = {
    title: announcement.title,
    content: announcement.content,
    status: announcement.status,
  };
}

function resetAnnouncementForm() {
  editingAnnouncementId.value = null;
  announcementForm.value = { title: "", content: "", status: 1 };
}

async function submitAnnouncement() {
  loading.value = true;
  try {
    if (editingAnnouncementId.value) {
      await adminUpdateAnnouncement(editingAnnouncementId.value, announcementForm.value);
      setMessage("公告已更新");
    } else {
      await adminCreateAnnouncement(announcementForm.value);
      setMessage("公告已创建");
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

async function toggleAnnouncementStatus(announcement: Announcement) {
  const nextStatusLabel = announcement.status === 1 ? "隐藏" : "显示";
  if (!confirmAction(`确认${nextStatusLabel}公告《${announcement.title}》？`)) return;
  loading.value = true;
  try {
    await adminUpdateAnnouncementStatus(announcement.id, announcement.status === 1 ? 0 : 1);
    await loadAnnouncements();
    setMessage("公告状态已更新");
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

async function resetUserPassword(user: UserInfo) {
  const password = window.prompt(`重置 ${user.username} 的密码，至少6位`);
  if (!password) return;
  if (!confirmAction(`确认重置用户 ${user.username} 的密码？该用户旧登录态会失效。`)) return;
  loading.value = true;
  try {
    await adminResetUserPassword(user.id, password);
    setMessage("用户密码已重置");
  } catch (error) {
    setError(error, "重置密码失败");
  } finally {
    loading.value = false;
  }
}

async function refreshOperationLogs() {
  loading.value = true;
  try {
    await loadOperationLogs();
    setMessage("日志已刷新");
  } catch (error) {
    setError(error, "日志加载失败");
  } finally {
    loading.value = false;
  }
}

async function searchOperationLogs() {
  resetPage(logPage.value);
  await refreshOperationLogs();
}

async function saveConfig(config: ConfigItem) {
  if (!confirmAction(`确认保存规则 ${config.config_key} = ${config.config_value}？`)) return;
  loading.value = true;
  try {
    await adminUpdateConfig(config.config_key, config.config_value);
    await loadConfigs();
    setMessage("规则配置已更新");
  } catch (error) {
    setError(error, "更新规则配置失败");
  } finally {
    loading.value = false;
  }
}

async function loadActiveTab() {
  loading.value = true;
  message.value = "";
  errorMessage.value = "";
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

onMounted(loadActiveTab);
</script>

<template>
  <section class="page-header">
    <p class="eyebrow">管理端</p>
    <h1>后台管理</h1>
    <p>集中管理统计、用户、场地、预约、公告、规则配置和操作日志。</p>
  </section>

  <section class="panel admin-shell">
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <p v-if="message" class="success-text">{{ message }}</p>
    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <div v-if="activeTab === 'statistics'" class="admin-section">
      <div class="toolbar-row">
        <label>
          开始日期
          <input v-model="statsRange.date_from" type="date" />
        </label>
        <label>
          结束日期
          <input v-model="statsRange.date_to" type="date" />
        </label>
        <button class="primary-button" type="button" :disabled="loading" @click="refreshStatistics">刷新统计</button>
      </div>

      <div v-if="statisticsOverview" class="metric-grid">
        <article class="metric-card">
          <span>预约总量</span>
          <strong>{{ statisticsOverview.reservation_total }}</strong>
          <small>{{ statisticsOverview.date_from }} 至 {{ statisticsOverview.date_to }}</small>
        </article>
        <article class="metric-card">
          <span>今日预约</span>
          <strong>{{ statisticsOverview.today_reservations }}</strong>
          <small>当天预约记录</small>
        </article>
        <article class="metric-card">
          <span>活跃用户</span>
          <strong>{{ statisticsOverview.active_users }}</strong>
          <small>区间内有预约的用户</small>
        </article>
        <article class="metric-card">
          <span>场地使用率</span>
          <strong>{{ statisticsOverview.utilization_rate }}%</strong>
          <small>{{ statisticsOverview.occupied_slots }}/{{ statisticsOverview.capacity_slots }} 时间段</small>
        </article>
        <article class="metric-card">
          <span>启用场地</span>
          <strong>{{ statisticsOverview.enabled_courts }}/{{ statisticsOverview.total_courts }}</strong>
          <small>可预约场地数量</small>
        </article>
        <article class="metric-card">
          <span>预约状态</span>
          <strong>{{ statisticsOverview.confirmed_reservations }}/{{ statisticsOverview.completed_reservations }}</strong>
          <small>confirmed / completed</small>
        </article>
      </div>

      <div class="stat-layout">
        <section class="stat-panel">
          <div class="section-title">
            <h2>场地使用率</h2>
          </div>
          <div v-if="courtStatistics.length" class="bar-list">
            <div v-for="court in courtStatistics" :key="court.court_id" class="bar-item">
              <div>
                <strong>{{ court.court_no }} {{ court.court_name }}</strong>
                <span>{{ court.active_count }} 次 / {{ court.usage_rate }}%</span>
              </div>
              <div class="bar-track">
                <i :style="{ width: barWidth(court.active_count, maxCourtActiveCount) }"></i>
              </div>
            </div>
          </div>
          <p v-else class="empty-state">暂无场地统计数据</p>
        </section>

        <section class="stat-panel">
          <div class="section-title">
            <h2>热门时间段</h2>
          </div>
          <div v-if="timeSlotStatistics.length" class="bar-list">
            <div v-for="slot in timeSlotStatistics" :key="slot.time_slot" class="bar-item">
              <div>
                <strong>{{ slot.time_slot }}</strong>
                <span>{{ slot.reservation_count }} 次</span>
              </div>
              <div class="bar-track">
                <i :style="{ width: barWidth(slot.reservation_count, maxTimeSlotCount) }"></i>
              </div>
            </div>
          </div>
          <p v-else class="empty-state">暂无时间段统计数据</p>
        </section>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>用户</th>
              <th>预约总数</th>
              <th>已确认</th>
              <th>已完成</th>
              <th>已取消</th>
              <th>最近预约日期</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in userStatistics" :key="user.user_id">
              <td>{{ user.nickname || user.username }}</td>
              <td>{{ user.reservation_count }}</td>
              <td>{{ user.confirmed_count }}</td>
              <td>{{ user.completed_count }}</td>
              <td>{{ user.canceled_count }}</td>
              <td>{{ user.last_reserve_date || "-" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="activeTab === 'users'" class="admin-section">
      <form class="form-inline" @submit.prevent="submitUser">
        <input v-model="userForm.username" placeholder="用户名" />
        <input v-model="userForm.password" placeholder="密码" type="password" />
        <input v-model="userForm.nickname" placeholder="昵称" />
        <input v-model="userForm.contact" placeholder="联系方式" />
        <select v-model="userForm.role">
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
        <select v-model.number="userForm.status">
          <option :value="1">启用</option>
          <option :value="0">禁用</option>
        </select>
        <button class="primary-button" type="submit" :disabled="loading">新增用户</button>
      </form>

      <div class="toolbar-row">
        <label>
          角色
          <select v-model="userFilters.role" @change="refreshUsers(true)">
            <option value="">全部</option>
            <option value="user">user</option>
            <option value="admin">admin</option>
          </select>
        </label>
        <label>
          状态
          <select v-model="userFilters.status" @change="refreshUsers(true)">
            <option value="">全部</option>
            <option value="1">启用</option>
            <option value="0">禁用</option>
          </select>
        </label>
      </div>

      <div v-if="users.length === 0" class="empty-state">暂无用户数据</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>用户名</th>
              <th>昵称</th>
              <th>联系方式</th>
              <th>角色</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td>{{ user.username }}</td>
              <td>{{ user.nickname }}</td>
              <td>{{ user.contact || "-" }}</td>
              <td>
                <select :value="user.role" @change="changeUserRole(user, $event)">
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                </select>
              </td>
              <td><span class="state-pill" :class="user.status === 1 ? 'confirmed' : 'canceled'">{{ user.status === 1 ? "启用" : "禁用" }}</span></td>
              <td>
                <button class="text-button" type="button" @click="toggleUserStatus(user)">{{ user.status === 1 ? "禁用" : "启用" }}</button>
                <button class="text-button" type="button" @click="resetUserPassword(user)">重置密码</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="pagination-row">
        <button class="text-button" type="button" :disabled="userPage.page <= 1" @click="changePage(userPage, userPage.page - 1, () => refreshUsers())">上一页</button>
        <span>第 {{ userPage.page }} / {{ pageCount(userPage) }} 页，共 {{ userPage.total }} 条</span>
        <button class="text-button" type="button" :disabled="userPage.page >= pageCount(userPage)" @click="changePage(userPage, userPage.page + 1, () => refreshUsers())">下一页</button>
      </div>
    </div>

    <div v-if="activeTab === 'courts'" class="admin-section">
      <form class="form-inline" @submit.prevent="submitCourt">
        <input v-model="courtForm.court_no" placeholder="场地编号" />
        <input v-model="courtForm.court_name" placeholder="场地名称" />
        <input v-model="courtForm.description" placeholder="说明" />
        <input v-model="courtForm.price_per_hour_yuan" placeholder="每小时价格（元）" />
        <input v-model="courtForm.image_url" placeholder="图片路径，如 /courts/default-court.png" />
        <input v-model="courtForm.tags_text" placeholder="标签，逗号分隔" />
        <input v-model.number="courtForm.capacity" placeholder="容纳人数" type="number" min="1" max="50" />
        <select v-model.number="courtForm.status">
          <option :value="1">启用</option>
          <option :value="0">停用</option>
        </select>
        <button class="primary-button" type="submit" :disabled="loading">{{ editingCourtId ? "保存场地" : "新增场地" }}</button>
        <button class="text-button" type="button" @click="resetCourtForm">清空</button>
      </form>

      <div class="toolbar-row">
        <label>
          状态
          <select v-model="courtStatus" @change="refreshCourts(true)">
            <option value="">全部</option>
            <option value="1">启用</option>
            <option value="0">停用</option>
          </select>
        </label>
      </div>

      <div v-if="courts.length === 0" class="empty-state">暂无场地数据</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>编号</th>
              <th>名称</th>
              <th>说明</th>
              <th>价格</th>
              <th>标签</th>
              <th>人数</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="court in courts" :key="court.id">
              <td>{{ court.court_no }}</td>
              <td>{{ court.court_name }}</td>
              <td>{{ court.description || "-" }}</td>
              <td>{{ formatMoney(court.price_per_hour_cents) }}/小时</td>
              <td>{{ court.tags?.join("，") || "-" }}</td>
              <td>{{ court.capacity }}</td>
              <td><span class="state-pill" :class="court.status === 1 ? 'confirmed' : 'canceled'">{{ court.status === 1 ? "启用" : "停用" }}</span></td>
              <td>
                <button class="text-button" type="button" @click="editCourt(court)">编辑</button>
                <button class="text-button" type="button" @click="toggleCourtStatus(court)">{{ court.status === 1 ? "停用" : "启用" }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="pagination-row">
        <button class="text-button" type="button" :disabled="courtPage.page <= 1" @click="changePage(courtPage, courtPage.page - 1, () => refreshCourts())">上一页</button>
        <span>第 {{ courtPage.page }} / {{ pageCount(courtPage) }} 页，共 {{ courtPage.total }} 条</span>
        <button class="text-button" type="button" :disabled="courtPage.page >= pageCount(courtPage)" @click="changePage(courtPage, courtPage.page + 1, () => refreshCourts())">下一页</button>
      </div>
    </div>

    <div v-if="activeTab === 'reservations'" class="admin-section">
      <div class="toolbar-row">
        <label>
          状态
          <select v-model="reservationFilters.status" @change="refreshReservations(true)">
            <option value="">全部</option>
            <option value="confirmed">confirmed</option>
            <option value="canceled">canceled</option>
            <option value="pending">pending</option>
            <option value="completed">completed</option>
          </select>
        </label>
        <label>
          用户
          <input v-model="reservationFilters.username" placeholder="用户名或昵称" @keyup.enter="refreshReservations(true)" />
        </label>
        <label>
          场地
          <select v-model="reservationFilters.court_id" @change="refreshReservations(true)">
            <option value="">全部</option>
            <option v-for="court in courtOptions" :key="court.id" :value="String(court.id)">{{ court.court_no }} {{ court.court_name }}</option>
          </select>
        </label>
        <label>
          开始日期
          <input v-model="reservationFilters.date_from" type="date" />
        </label>
        <label>
          结束日期
          <input v-model="reservationFilters.date_to" type="date" />
        </label>
        <button class="primary-button" type="button" :disabled="loading" @click="refreshReservations(true)">查询预约</button>
      </div>

      <div v-if="reservations.length === 0" class="empty-state">暂无预约数据</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>预约号</th>
              <th>用户</th>
              <th>场地</th>
              <th>日期</th>
              <th>时间</th>
              <th>应付金额</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="reservation in reservations" :key="reservation.id">
              <td>{{ reservation.reservation_no }}</td>
              <td>{{ reservation.nickname || reservation.username }}</td>
              <td>{{ reservation.court_name }}</td>
              <td>{{ reservation.reserve_date }}</td>
              <td>{{ reservation.start_time }}-{{ reservation.end_time }}</td>
              <td>{{ formatMoney(reservation.payable_amount_cents) }}</td>
              <td><span class="state-pill" :class="reservation.status">{{ reservation.status }}</span></td>
              <td>
                <button
                  class="text-button"
                  type="button"
                  :disabled="['canceled', 'completed', 'expired'].includes(reservation.status)"
                  @click="cancelAdminReservation(reservation)"
                >
                  取消
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="pagination-row">
        <button class="text-button" type="button" :disabled="reservationPage.page <= 1" @click="changePage(reservationPage, reservationPage.page - 1, () => refreshReservations())">上一页</button>
        <span>第 {{ reservationPage.page }} / {{ pageCount(reservationPage) }} 页，共 {{ reservationPage.total }} 条</span>
        <button class="text-button" type="button" :disabled="reservationPage.page >= pageCount(reservationPage)" @click="changePage(reservationPage, reservationPage.page + 1, () => refreshReservations())">下一页</button>
      </div>
    </div>

    <div v-if="activeTab === 'announcements'" class="admin-section">
      <form class="form-stack compact-form" @submit.prevent="submitAnnouncement">
        <input v-model="announcementForm.title" placeholder="公告标题" />
        <textarea v-model="announcementForm.content" placeholder="公告内容" rows="4"></textarea>
        <select v-model.number="announcementForm.status">
          <option :value="1">显示</option>
          <option :value="0">隐藏</option>
        </select>
        <div class="button-row">
          <button class="primary-button" type="submit" :disabled="loading">{{ editingAnnouncementId ? "保存公告" : "新增公告" }}</button>
          <button class="text-button" type="button" @click="resetAnnouncementForm">清空</button>
        </div>
      </form>

      <div class="toolbar-row">
        <label>
          状态
          <select v-model="announcementStatus" @change="refreshAnnouncements(true)">
            <option value="">全部</option>
            <option value="1">显示</option>
            <option value="0">隐藏</option>
          </select>
        </label>
      </div>

      <div v-if="announcements.length === 0" class="empty-state">暂无公告数据</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>标题</th>
              <th>状态</th>
              <th>更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="announcement in announcements" :key="announcement.id">
              <td>{{ announcement.title }}</td>
              <td><span class="state-pill" :class="announcement.status === 1 ? 'confirmed' : 'canceled'">{{ announcement.status === 1 ? "显示" : "隐藏" }}</span></td>
              <td>{{ announcement.updated_at }}</td>
              <td>
                <button class="text-button" type="button" @click="editAnnouncement(announcement)">编辑</button>
                <button class="text-button" type="button" @click="toggleAnnouncementStatus(announcement)">{{ announcement.status === 1 ? "隐藏" : "显示" }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="pagination-row">
        <button class="text-button" type="button" :disabled="announcementPage.page <= 1" @click="changePage(announcementPage, announcementPage.page - 1, () => refreshAnnouncements())">上一页</button>
        <span>第 {{ announcementPage.page }} / {{ pageCount(announcementPage) }} 页，共 {{ announcementPage.total }} 条</span>
        <button class="text-button" type="button" :disabled="announcementPage.page >= pageCount(announcementPage)" @click="changePage(announcementPage, announcementPage.page + 1, () => refreshAnnouncements())">下一页</button>
      </div>
    </div>

    <div v-if="activeTab === 'configs'" class="admin-section">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>配置键</th>
              <th>配置值</th>
              <th>说明</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="config in configs" :key="config.config_key">
              <td>{{ config.config_key }}</td>
              <td><input v-model="config.config_value" /></td>
              <td>{{ config.description }}</td>
              <td><button class="text-button" type="button" @click="saveConfig(config)">保存</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="activeTab === 'logs'" class="admin-section">
      <div class="toolbar-row">
        <label>
          模块
          <select v-model="logFilters.module" @change="searchOperationLogs">
            <option value="">全部</option>
            <option value="user">用户</option>
            <option value="court">场地</option>
            <option value="reservation">预约</option>
            <option value="announcement">公告</option>
            <option value="config">规则</option>
          </select>
        </label>
        <label>
          操作
          <select v-model="logFilters.action" @change="searchOperationLogs">
            <option value="">全部</option>
            <option value="create">create</option>
            <option value="update">update</option>
            <option value="status">status</option>
            <option value="role">role</option>
            <option value="cancel">cancel</option>
            <option value="hide">hide</option>
          </select>
        </label>
        <label>
          操作人
          <input v-model="logFilters.username" placeholder="用户名" @keyup.enter="searchOperationLogs" />
        </label>
        <label>
          开始日期
          <input v-model="logFilters.date_from" type="date" />
        </label>
        <label>
          结束日期
          <input v-model="logFilters.date_to" type="date" />
        </label>
        <button class="primary-button" type="button" :disabled="loading" @click="searchOperationLogs">查询日志</button>
      </div>

      <div v-if="operationLogs.length === 0" class="empty-state">暂无操作日志</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>操作人</th>
              <th>模块</th>
              <th>操作</th>
              <th>目标</th>
              <th>详情</th>
              <th>IP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in operationLogs" :key="log.id">
              <td>{{ log.created_at }}</td>
              <td>{{ log.username || "-" }}</td>
              <td>{{ log.module }}</td>
              <td>{{ log.action }}</td>
              <td>{{ log.target_type || "-" }} #{{ log.target_id || "-" }}</td>
              <td>{{ operationDetail(log.detail) }}</td>
              <td>{{ log.ip || "-" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="pagination-row">
        <button class="text-button" type="button" :disabled="logPage.page <= 1" @click="changePage(logPage, logPage.page - 1, () => refreshOperationLogs())">上一页</button>
        <span>第 {{ logPage.page }} / {{ pageCount(logPage) }} 页，共 {{ logPage.total }} 条</span>
        <button class="text-button" type="button" :disabled="logPage.page >= pageCount(logPage)" @click="changePage(logPage, logPage.page + 1, () => refreshOperationLogs())">下一页</button>
      </div>
    </div>
  </section>
</template>
