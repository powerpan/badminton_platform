<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { getCaptcha } from "../api/auth";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const username = ref("admin");
const password = ref("admin123456");
const captchaId = ref("");
const captchaCode = ref("");
const captchaImage = ref("");
const errorMessage = ref("");
const loading = ref(false);
const captchaLoading = ref(false);

async function loadCaptcha() {
  captchaLoading.value = true;
  try {
    const response = await getCaptcha();
    captchaId.value = response.data.captcha_id;
    captchaImage.value = response.data.image_data;
    captchaCode.value = "";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "验证码加载失败";
  } finally {
    captchaLoading.value = false;
  }
}

async function handleLogin() {
  errorMessage.value = "";
  loading.value = true;
  try {
    await authStore.login(username.value.trim(), password.value, captchaId.value, captchaCode.value.trim());
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/";
    await router.push(redirect);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "登录失败";
    await loadCaptcha();
  } finally {
    loading.value = false;
  }
}

onMounted(loadCaptcha);
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
        <label>
          验证码
          <div class="captcha-row">
            <input v-model="captchaCode" autocomplete="off" maxlength="4" required />
            <button class="captcha-image-button" :disabled="captchaLoading" type="button" @click="loadCaptcha">
              <img v-if="captchaImage" :src="captchaImage" alt="验证码" />
              <span v-else>{{ captchaLoading ? "加载中" : "刷新" }}</span>
            </button>
          </div>
        </label>
        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
        <button class="primary-button" :disabled="loading" type="submit">
          {{ loading ? "登录中..." : "登录" }}
        </button>
      </form>
      <p class="muted-link">
        还没有账号？<RouterLink to="/register">去注册</RouterLink>
        <span> · </span>
        <RouterLink to="/forgot-password">忘记密码</RouterLink>
      </p>
    </div>
  </section>
</template>
