<script setup lang="ts">
import { ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const router = useRouter();

const username = ref("");
const nickname = ref("");
const contact = ref("");
const password = ref("");
const errorMessage = ref("");
const successMessage = ref("");
const loading = ref(false);

async function handleRegister() {
  errorMessage.value = "";
  successMessage.value = "";
  loading.value = true;
  try {
    await authStore.register({
      username: username.value.trim(),
      nickname: nickname.value.trim(),
      contact: contact.value.trim(),
      password: password.value,
    });
    successMessage.value = "注册成功，请登录";
    await router.push("/login");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "注册失败";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="auth-layout">
    <div class="auth-panel">
      <p class="eyebrow">新用户注册</p>
      <h1>创建普通用户账号</h1>
      <form class="form-stack" @submit.prevent="handleRegister">
        <label>
          用户名
          <input v-model="username" autocomplete="username" required />
        </label>
        <label>
          昵称
          <input v-model="nickname" autocomplete="name" />
        </label>
        <label>
          联系方式
          <input v-model="contact" autocomplete="tel" />
        </label>
        <label>
          密码
          <input v-model="password" autocomplete="new-password" minlength="6" required type="password" />
        </label>
        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
        <p v-if="successMessage" class="success-text">{{ successMessage }}</p>
        <button class="primary-button" :disabled="loading" type="submit">
          {{ loading ? "注册中..." : "注册" }}
        </button>
      </form>
      <p class="muted-link">已有账号？<RouterLink to="/login">去登录</RouterLink></p>
    </div>
  </section>
</template>
