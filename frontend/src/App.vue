<script setup lang="ts">
import { computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "./stores/auth";
import { useNotificationStore } from "./stores/notification";

const authStore = useAuthStore();
const notificationStore = useNotificationStore();
const route = useRoute();
const router = useRouter();

const routeTitleMap: Record<string, string> = {
  home: "运营总览",
  login: "会员登录",
  register: "会员注册",
  "forgot-password": "找回密码",
  announcements: "公告中心",
  "announcement-detail": "公告详情",
  courts: "场地预订",
  reservations: "我的预订",
  profile: "会员中心",
  notifications: "通知中心",
  help: "帮助中心",
  events: "活动赛事",
  "event-detail": "活动详情",
  community: "球友圈",
  shop: "商城",
  "shop-orders": "商城订单",
  admin: "管理后台",
};

const routeTitle = computed(() => routeTitleMap[String(route.name || "")] || "羽毛球平台");

const primaryNav = computed(() => [
  { label: "首页", to: "/", icon: "home", visible: true },
  { label: "场地预订", to: "/courts", icon: "grid", visible: authStore.isLoggedIn },
  { label: "我的预订", to: "/reservations", icon: "ticket", visible: authStore.isLoggedIn },
  { label: "会员中心", to: "/profile", icon: "user", visible: authStore.isLoggedIn },
  { label: "管理后台", to: "/admin", icon: "admin", visible: authStore.isAdmin },
  { label: "活动赛事", to: "/events", icon: "flag", visible: true },
  { label: "球友圈", to: "/community", icon: "circle", visible: true },
  { label: "商城", to: "/shop", icon: "cart", visible: true },
  { label: "帮助中心", to: "/help", icon: "help", visible: true },
]);

const guestNav = [
  { label: "登录", to: "/login", icon: "login" },
  { label: "注册", to: "/register", icon: "register" },
];

function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function validityText(expiresAt: string | null | undefined) {
  return expiresAt ? `有效期至 ${expiresAt}` : "长期有效";
}

async function logout() {
  await authStore.logout();
  notificationStore.clear();
  await router.push("/login");
}

onMounted(async () => {
  if (!authStore.token) return;
  try {
    await authStore.fetchProfile();
    await notificationStore.fetchUnreadCount();
  } catch {
    authStore.clearSession();
    notificationStore.clear();
  }
});

watch(
  () => authStore.isLoggedIn,
  async (isLoggedIn) => {
    if (!isLoggedIn) {
      notificationStore.clear();
      return;
    }
    try {
      await notificationStore.fetchUnreadCount();
    } catch {
      notificationStore.clear();
    }
  },
);
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
          <span></span>
        </span>
        <div>
          <strong>GREENBIRD</strong>
          <small>BADMINTON CLUB</small>
        </div>
      </div>

      <nav class="nav-list">
        <RouterLink
          v-for="item in primaryNav.filter((nav) => nav.visible)"
          :key="item.to"
          :to="item.to"
          class="nav-item"
        >
          <span class="nav-icon" :class="`nav-icon-${item.icon}`"></span>
          <span>{{ item.label }}</span>
        </RouterLink>
        <template v-if="!authStore.isLoggedIn">
          <RouterLink v-for="item in guestNav" :key="item.to" :to="item.to" class="nav-item">
            <span class="nav-icon" :class="`nav-icon-${item.icon}`"></span>
            <span>{{ item.label }}</span>
          </RouterLink>
        </template>
      </nav>

      <div class="session-box">
        <template v-if="authStore.user">
          <div class="session-title">
            <span>{{ authStore.user.member.level_label }}</span>
            <small>{{ validityText(authStore.user.member.expires_at) }}</small>
          </div>
          <div class="session-balance">
            <small>余额</small>
            <strong>{{ formatMoney(authStore.user.member.balance_cents) }}</strong>
          </div>
          <div class="session-balance">
            <small>积分</small>
            <strong>{{ authStore.user.member.points.toLocaleString("zh-CN") }}</strong>
          </div>
          <small v-if="authStore.user.must_change_password" class="warning-line">默认密码待修改</small>
          <RouterLink class="session-link" to="/profile">会员权益</RouterLink>
        </template>
        <template v-else>
          <span>未登录</span>
          <small>登录后可预约场地</small>
        </template>
      </div>
    </aside>

    <main class="main-panel">
      <header class="topbar">
        <h1>{{ routeTitle }}</h1>
        <div class="topbar-tools">
          <span class="weather-dot"></span>
          <span>28°C</span>
          <RouterLink v-if="authStore.isLoggedIn" class="notice-link" to="/notifications" aria-label="通知中心">
            <span class="notice-bell">
              <span v-if="notificationStore.unreadCount > 0" class="notice-count">
                {{ notificationStore.unreadCount > 99 ? "99+" : notificationStore.unreadCount }}
              </span>
            </span>
          </RouterLink>
          <div v-if="authStore.user" class="user-chip">
            <span class="avatar">{{ (authStore.user.nickname || authStore.user.username).slice(0, 1) }}</span>
            <div>
              <strong>{{ authStore.user.nickname || authStore.user.username }}</strong>
              <small>{{ authStore.user.role === "admin" ? "管理员" : "会员卡" }}</small>
            </div>
            <button type="button" class="logout-button" @click="logout">退出</button>
          </div>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>
