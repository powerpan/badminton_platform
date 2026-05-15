<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "./stores/auth";

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const routeTitleMap: Record<string, string> = {
  home: "运营总览",
  login: "会员登录",
  register: "会员注册",
  "forgot-password": "找回密码",
  courts: "场地预订",
  reservations: "我的预订",
  profile: "会员中心",
  admin: "管理后台",
};

const routeTitle = computed(() => routeTitleMap[String(route.name || "")] || "羽毛球平台");

const primaryNav = computed(() => [
  { label: "首页", to: "/", icon: "home", visible: true },
  { label: "场地预订", to: "/courts", icon: "grid", visible: authStore.isLoggedIn },
  { label: "我的预订", to: "/reservations", icon: "ticket", visible: authStore.isLoggedIn },
  { label: "会员中心", to: "/profile", icon: "user", visible: authStore.isLoggedIn },
  { label: "管理后台", to: "/admin", icon: "admin", visible: authStore.isAdmin },
]);

const guestNav = [
  { label: "登录", to: "/login", icon: "login" },
  { label: "注册", to: "/register", icon: "register" },
];

const plannedNav = [
  { label: "活动赛事", icon: "flag" },
  { label: "球友圈", icon: "circle" },
  { label: "商城", icon: "cart" },
  { label: "帮助中心", icon: "help" },
];

async function logout() {
  await authStore.logout();
  await router.push("/login");
}
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
        <button
          v-for="item in plannedNav"
          :key="item.label"
          type="button"
          class="nav-item nav-item-muted"
          disabled
        >
          <span class="nav-icon" :class="`nav-icon-${item.icon}`"></span>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div class="session-box">
        <template v-if="authStore.user">
          <div class="session-title">
            <span>尊享会员卡</span>
            <small>有效期至 2026-12-31</small>
          </div>
          <div class="session-balance">
            <small>余额</small>
            <strong>￥1,248.00</strong>
          </div>
          <div class="session-balance">
            <small>积分</small>
            <strong>2,560</strong>
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
          <span class="notice-bell">3</span>
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
