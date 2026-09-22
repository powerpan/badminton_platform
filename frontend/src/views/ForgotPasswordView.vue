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
    <el-card class="auth-panel element-auth-card" shadow="never">
      <h1>重置登录密码</h1>
      <el-form v-if="!resetToken" label-position="top" class="element-form" @submit.prevent="handleVerify">
        <el-form-item label="用户名" required>
          <el-input v-model="username" autocomplete="username" size="large" />
        </el-form-item>
        <el-form-item label="联系方式" required>
          <el-input v-model="contact" autocomplete="tel" size="large" />
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
          验证身份
        </el-button>
      </el-form>
      <el-form v-else label-position="top" class="element-form" @submit.prevent="handleReset">
        <el-form-item label="新密码" required>
          <el-input v-model="newPassword" autocomplete="new-password" type="password" show-password size="large" />
        </el-form-item>
        <el-form-item label="确认新密码" required>
          <el-input v-model="confirmPassword" autocomplete="new-password" type="password" show-password size="large" />
        </el-form-item>
        <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
        <el-alert v-if="successMessage" :title="successMessage" type="success" show-icon :closable="false" />
        <el-button class="full-button" type="primary" size="large" :loading="loading" native-type="submit">
          重置密码
        </el-button>
      </el-form>
      <p class="muted-link"><RouterLink to="/login">返回登录</RouterLink></p>
    </el-card>
  </section>
</template>
