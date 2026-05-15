<script setup lang="ts">
import { ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const username = ref("admin");
const password = ref("admin123456");
const errorMessage = ref("");
const loading = ref(false);

async function handleLogin() {
  errorMessage.value = "";
  loading.value = true;
  try {
    await authStore.login(username.value.trim(), password.value);
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.push(redirect);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "登录失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="auth-layout">
    <div class="auth-panel">
      <p class="eyebrow">账号登录</p>
      <h1>登录 BF 羽毛球馆管理平台</h1>
      <form class="form-stack" @submit.prevent="handleLogin">
        <label>
          用户名
          <input v-model="username" autocomplete="username" required />
        </label>
        <label>
          密码
          <input v-model="password" autocomplete="current-password" required type="password" />
        </label>
        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
        <button class="primary-button" :disabled="loading" type="submit">
          {{ loading ? "登录中..." : "登录" }}
        </button>
      </form>
      <p class="muted-link">还没有账号？<RouterLink to="/register">去注册</RouterLink></p>
    </div>
  </section>
</template>
