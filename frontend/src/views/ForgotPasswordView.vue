<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { confirmPasswordReset, getCaptcha, requestPasswordReset } from "../api/auth";

const username = ref("");
const contact = ref("");
const captchaId = ref("");
const captchaCode = ref("");
const captchaImage = ref("");
const resetToken = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
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

async function handleVerify() {
  errorMessage.value = "";
  successMessage.value = "";
  loading.value = true;
  try {
    const response = await requestPasswordReset({
      username: username.value.trim(),
      contact: contact.value.trim(),
      captcha_id: captchaId.value,
      captcha_code: captchaCode.value.trim(),
    });
    resetToken.value = response.data.reset_token;
    successMessage.value = "身份验证通过，请设置新密码";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "身份验证失败";
    await loadCaptcha();
  } finally {
    loading.value = false;
  }
}

async function handleReset() {
  errorMessage.value = "";
  successMessage.value = "";
  if (newPassword.value !== confirmPassword.value) {
    errorMessage.value = "两次输入的新密码不一致";
    return;
  }
  loading.value = true;
  try {
    await confirmPasswordReset({
      reset_token: resetToken.value,
      new_password: newPassword.value,
    });
    successMessage.value = "密码重置成功，请返回登录";
    newPassword.value = "";
    confirmPassword.value = "";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "密码重置失败";
  } finally {
    loading.value = false;
  }
}

onMounted(loadCaptcha);
</script>

<template>
  <section class="auth-layout">
    <div class="auth-panel">
      <p class="eyebrow">找回密码</p>
      <h1>重置登录密码</h1>
      <form v-if="!resetToken" class="form-stack" @submit.prevent="handleVerify">
        <label>
          用户名
          <input v-model="username" autocomplete="username" required />
        </label>
        <label>
          联系方式
          <input v-model="contact" autocomplete="tel" required />
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
        <p v-if="successMessage" class="success-text">{{ successMessage }}</p>
        <button class="primary-button" :disabled="loading" type="submit">
          {{ loading ? "验证中..." : "验证身份" }}
        </button>
      </form>
      <form v-else class="form-stack" @submit.prevent="handleReset">
        <label>
          新密码
          <input v-model="newPassword" autocomplete="new-password" minlength="6" required type="password" />
        </label>
        <label>
          确认新密码
          <input v-model="confirmPassword" autocomplete="new-password" minlength="6" required type="password" />
        </label>
        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
        <p v-if="successMessage" class="success-text">{{ successMessage }}</p>
        <button class="primary-button" :disabled="loading" type="submit">
          {{ loading ? "提交中..." : "重置密码" }}
        </button>
      </form>
      <p class="muted-link"><RouterLink to="/login">返回登录</RouterLink></p>
    </div>
  </section>
</template>
