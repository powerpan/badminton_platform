<script setup lang="ts">
import { onMounted, ref } from "vue";

import type { Announcement } from "../api/announcement";
import {
  adminCancelReservation,
  adminCreateAnnouncement,
  adminCreateCourt,
  adminCreateUser,
  adminGetAnnouncements,
  adminGetConfigs,
  adminGetCourts,
  adminGetReservations,
  adminGetUsers,
  adminUpdateAnnouncement,
  adminUpdateAnnouncementStatus,
  adminUpdateConfig,
  adminUpdateCourt,
  adminUpdateCourtStatus,
  adminUpdateUserRole,
  adminUpdateUserStatus,
  type ConfigItem,
} from "../api/admin";
import type { UserInfo } from "../api/auth";
import type { Court } from "../api/court";
import type { Reservation } from "../api/reservation";

type AdminTab = "users" | "courts" | "reservations" | "announcements" | "configs";

const tabs: Array<{ key: AdminTab; label: string }> = [
  { key: "users", label: "用户" },
  { key: "courts", label: "场地" },
  { key: "reservations", label: "预约" },
  { key: "announcements", label: "公告" },
  { key: "configs", label: "规则" },
];

const activeTab = ref<AdminTab>("users");
const loading = ref(false);
const message = ref("");
const errorMessage = ref("");

const users = ref<UserInfo[]>([]);
const userForm = ref({
  username: "",
  password: "",
  nickname: "",
  contact: "",
  role: "user",
  status: 1,
});

const courts = ref<Court[]>([]);
const editingCourtId = ref<number | null>(null);
const courtForm = ref({
  court_no: "",
  court_name: "",
  description: "",
  status: 1,
});

const reservations = ref<Reservation[]>([]);
const reservationStatus = ref("");

const announcements = ref<Announcement[]>([]);
const editingAnnouncementId = ref<number | null>(null);
const announcementForm = ref({
  title: "",
  content: "",
  status: 1,
});

const configs = ref<ConfigItem[]>([]);

function setMessage(text: string) {
  message.value = text;
  errorMessage.value = "";
}

function setError(error: unknown, fallback: string) {
  errorMessage.value = error instanceof Error ? error.message : fallback;
  message.value = "";
}

async function loadUsers() {
  const response = await adminGetUsers({ page_size: 100 });
  users.value = response.data.items;
}

async function submitUser() {
  loading.value = true;
  try {
    await adminCreateUser(userForm.value);
    userForm.value = { username: "", password: "", nickname: "", contact: "", role: "user", status: 1 };
    await loadUsers();
    setMessage("用户已创建");
  } catch (error) {
    setError(error, "创建用户失败");
  } finally {
    loading.value = false;
  }
}

async function toggleUserStatus(user: UserInfo) {
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
  const response = await adminGetCourts({ page_size: 100 });
  courts.value = response.data.items;
}

function editCourt(court: Court) {
  editingCourtId.value = court.id;
  courtForm.value = {
    court_no: court.court_no,
    court_name: court.court_name,
    description: court.description || "",
    status: court.status,
  };
}

function resetCourtForm() {
  editingCourtId.value = null;
  courtForm.value = { court_no: "", court_name: "", description: "", status: 1 };
}

async function submitCourt() {
  loading.value = true;
  try {
    if (editingCourtId.value) {
      await adminUpdateCourt(editingCourtId.value, courtForm.value);
      setMessage("场地已更新");
    } else {
      await adminCreateCourt(courtForm.value);
      setMessage("场地已创建");
    }
    resetCourtForm();
    await loadCourts();
  } catch (error) {
    setError(error, "保存场地失败");
  } finally {
    loading.value = false;
  }
}

async function toggleCourtStatus(court: Court) {
  loading.value = true;
  try {
    await adminUpdateCourtStatus(court.id, court.status === 1 ? 0 : 1);
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
    status: reservationStatus.value || undefined,
    page_size: 100,
  });
  reservations.value = response.data.items;
}

async function cancelAdminReservation(reservation: Reservation) {
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
  const response = await adminGetAnnouncements({ page_size: 100 });
  announcements.value = response.data.items;
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
    await loadAnnouncements();
  } catch (error) {
    setError(error, "保存公告失败");
  } finally {
    loading.value = false;
  }
}

async function toggleAnnouncementStatus(announcement: Announcement) {
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

async function saveConfig(config: ConfigItem) {
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
    if (activeTab.value === "users") await loadUsers();
    if (activeTab.value === "courts") await loadCourts();
    if (activeTab.value === "reservations") await loadReservations();
    if (activeTab.value === "announcements") await loadAnnouncements();
    if (activeTab.value === "configs") await loadConfigs();
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
    <p>集中管理用户、场地、预约、公告和预约规则配置。</p>
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

      <div class="table-wrap">
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
              <td><button class="text-button" type="button" @click="toggleUserStatus(user)">{{ user.status === 1 ? "禁用" : "启用" }}</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="activeTab === 'courts'" class="admin-section">
      <form class="form-inline" @submit.prevent="submitCourt">
        <input v-model="courtForm.court_no" placeholder="场地编号" />
        <input v-model="courtForm.court_name" placeholder="场地名称" />
        <input v-model="courtForm.description" placeholder="说明" />
        <select v-model.number="courtForm.status">
          <option :value="1">启用</option>
          <option :value="0">停用</option>
        </select>
        <button class="primary-button" type="submit" :disabled="loading">{{ editingCourtId ? "保存场地" : "新增场地" }}</button>
        <button class="text-button" type="button" @click="resetCourtForm">清空</button>
      </form>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>编号</th>
              <th>名称</th>
              <th>说明</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="court in courts" :key="court.id">
              <td>{{ court.court_no }}</td>
              <td>{{ court.court_name }}</td>
              <td>{{ court.description || "-" }}</td>
              <td><span class="state-pill" :class="court.status === 1 ? 'confirmed' : 'canceled'">{{ court.status === 1 ? "启用" : "停用" }}</span></td>
              <td>
                <button class="text-button" type="button" @click="editCourt(court)">编辑</button>
                <button class="text-button" type="button" @click="toggleCourtStatus(court)">{{ court.status === 1 ? "停用" : "启用" }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="activeTab === 'reservations'" class="admin-section">
      <div class="toolbar-row">
        <label>
          状态
          <select v-model="reservationStatus" @change="loadReservations">
            <option value="">全部</option>
            <option value="confirmed">confirmed</option>
            <option value="canceled">canceled</option>
            <option value="pending">pending</option>
            <option value="completed">completed</option>
          </select>
        </label>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>预约号</th>
              <th>用户</th>
              <th>场地</th>
              <th>日期</th>
              <th>时间</th>
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
              <td><span class="state-pill" :class="reservation.status">{{ reservation.status }}</span></td>
              <td><button class="text-button" type="button" :disabled="reservation.status === 'canceled'" @click="cancelAdminReservation(reservation)">取消</button></td>
            </tr>
          </tbody>
        </table>
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

      <div class="table-wrap">
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
  </section>
</template>
