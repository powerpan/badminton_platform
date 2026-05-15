<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import { getCaptcha } from "../api/auth";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const router = useRouter();

const username = ref("");
const nickname = ref("");
const contact = ref("");
const password = ref("");
const captchaId = ref("");
const captchaCode = ref("");
const captchaImage = ref("");
const errorMessage = ref("");
const successMessage = ref("");
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
      captcha_id: captchaId.value,
      captcha_code: captchaCode.value.trim(),
    });
    successMessage.value = "注册成功，请登录";
    await router.push("/login");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "注册失败";
    await loadCaptcha();
  } finally {
    loading.value = false;
  }
}

onMounted(loadCaptcha);
</script>

<template>
  <section class="auth-layout">
    <el-card class="auth-panel element-auth-card" shadow="never">
      <p class="eyebrow">新用户注册</p>
      <h1>创建普通用户账号</h1>
      <el-form label-position="top" class="element-form" @submit.prevent="handleRegister">
        <el-form-item label="用户名" required>
          <el-input v-model="username" autocomplete="username" size="large" />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="nickname" autocomplete="name" size="large" />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-input v-model="contact" autocomplete="tel" size="large" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="password" autocomplete="new-password" type="password" show-password size="large" />
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
        <el-alert v-if="successMessage" :title="successMessage" type="success" show-icon :closable="false" />
        <el-button class="full-button" type="primary" size="large" :loading="loading" native-type="submit">
          注册
        </el-button>
      </el-form>
      <p class="muted-link">已有账号？<RouterLink to="/login">去登录</RouterLink></p>
    </el-card>
  </section>
</template>
