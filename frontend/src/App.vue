<script setup lang="ts">
import { useRouter } from "vue-router";

import { useAuthStore } from "./stores/auth";

const authStore = useAuthStore();
const router = useRouter();

async function logout() {
  authStore.clearSession();
  await router.push("/login");
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">BF</span>
        <div>
          <strong>羽毛球馆管理平台</strong>
          <small>Badminton Facility</small>
        </div>
      </div>

      <nav class="nav-list">
        <RouterLink to="/">首页</RouterLink>
        <RouterLink v-if="!authStore.isLoggedIn" to="/login">登录</RouterLink>
        <RouterLink v-if="!authStore.isLoggedIn" to="/register">注册</RouterLink>
        <RouterLink to="/courts">场地预约</RouterLink>
        <RouterLink to="/reservations">我的预约</RouterLink>
        <RouterLink to="/profile">个人中心</RouterLink>
        <RouterLink to="/admin">管理后台</RouterLink>
      </nav>

      <div class="session-box">
        <template v-if="authStore.user">
          <span>{{ authStore.user.nickname || authStore.user.username }}</span>
          <small>{{ authStore.user.role }}</small>
          <button type="button" @click="logout">退出登录</button>
        </template>
        <template v-else>
          <span>未登录</span>
          <small>登录后可预约场地</small>
        </template>
      </div>
    </aside>

    <main class="main-panel">
      <RouterView />
    </main>
  </div>
</template>
