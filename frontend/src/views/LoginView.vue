<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { getCaptcha } from "../api/auth";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const username = ref("");
const password = ref("");
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
    const redirect = safeRedirect(route.query.redirect);
    await router.push(redirect === "/" ? authStore.homePath : redirect);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "登录失败";
    await loadCaptcha();
  } finally {
    loading.value = false;
  }
}

function safeRedirect(value: unknown) {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) {
    return authStore.homePath;
  }
  try {
    const resolved = router.resolve(value);
    return resolved.matched.length ? resolved.fullPath : authStore.homePath;
  } catch {
    return authStore.homePath;
  }
}

onMounted(loadCaptcha);
</script>

<template>
  <section class="auth-layout">
    <el-card class="auth-panel element-auth-card" shadow="never">
      <h1>欢迎回到 BF 羽毛球馆</h1>
      <el-form label-position="top" class="element-form" @submit.prevent="handleLogin">
        <el-form-item label="用户名" required>
          <el-input v-model="username" autocomplete="username" size="large" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="password" autocomplete="current-password" type="password" show-password size="large" />
        </el-form-item>
        <el-form-item label="验证码" required>
          <div class="captcha-row">
            <el-input v-model="captchaCode" autocomplete="off" maxlength="4" size="large" />
            <el-button class="captcha-image-button element-captcha" :loading="captchaLoading" native-type="button" @click="loadCaptcha">
              <img v-if="captchaImage" :src="captchaImage" alt="验证码" />
              <span v-else>刷新</span>
            </el-button>
          </div>
        </el-form-item>
        <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
        <el-button class="full-button" type="primary" size="large" :loading="loading" native-type="submit">
          登录
        </el-button>
      </el-form>
      <p class="muted-link">
        还没有账号？<RouterLink to="/register">去注册</RouterLink>
        <span> · </span>
        <RouterLink to="/forgot-password">忘记密码</RouterLink>
      </p>
    </el-card>
  </section>
</template>
