<script setup lang="ts">
import { computed, ref, watchEffect } from "vue";

import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();

const nickname = ref("");
const contact = ref("");
const oldPassword = ref("");
const newPassword = ref("");
const profileMessage = ref("");
const passwordMessage = ref("");
const errorMessage = ref("");
const loadingProfile = ref(false);
const loadingPassword = ref(false);

const currentUser = computed(() => authStore.user);

watchEffect(() => {
  if (authStore.user) {
    nickname.value = authStore.user.nickname;
    contact.value = authStore.user.contact;
  }
});

async function saveProfile() {
  errorMessage.value = "";
  profileMessage.value = "";
  loadingProfile.value = true;
  try {
    await authStore.updateProfile({
      nickname: nickname.value.trim(),
      contact: contact.value.trim(),
    });
    profileMessage.value = "个人信息已保存";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "保存失败";
  } finally {
    loadingProfile.value = false;
  }
}

async function savePassword() {
  errorMessage.value = "";
  passwordMessage.value = "";
  loadingPassword.value = true;
  try {
    await authStore.changePassword({
      old_password: oldPassword.value,
      new_password: newPassword.value,
    });
    oldPassword.value = "";
    newPassword.value = "";
    passwordMessage.value = "密码已修改";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "修改失败";
  } finally {
    loadingPassword.value = false;
  }
}
</script>

<template>
  <section class="page-header">
    <p class="eyebrow">个人中心</p>
    <h1>账号资料</h1>
    <p v-if="currentUser">当前登录：{{ currentUser.username }} / {{ currentUser.role }}</p>
  </section>

  <section class="module-grid">
    <div v-if="currentUser?.must_change_password" class="panel warning-panel">
      <h2>默认管理员密码提醒</h2>
      <p>当前管理员账号仍在使用默认密码，请先完成密码修改，再继续用于演示或部署。</p>
    </div>

    <form class="panel form-stack" @submit.prevent="saveProfile">
      <h2>基本信息</h2>
      <label>
        昵称
        <input v-model="nickname" />
      </label>
      <label>
        联系方式
        <input v-model="contact" />
      </label>
      <p v-if="profileMessage" class="success-text">{{ profileMessage }}</p>
      <button class="primary-button" :disabled="loadingProfile" type="submit">
        {{ loadingProfile ? "保存中..." : "保存资料" }}
      </button>
    </form>

    <form class="panel form-stack" @submit.prevent="savePassword">
      <h2>修改密码</h2>
      <label>
        旧密码
        <input v-model="oldPassword" autocomplete="current-password" required type="password" />
      </label>
      <label>
        新密码
        <input v-model="newPassword" autocomplete="new-password" minlength="6" required type="password" />
      </label>
      <p v-if="passwordMessage" class="success-text">{{ passwordMessage }}</p>
      <button class="primary-button" :disabled="loadingPassword" type="submit">
        {{ loadingPassword ? "修改中..." : "修改密码" }}
      </button>
    </form>
  </section>

  <p v-if="errorMessage" class="error-text profile-error">{{ errorMessage }}</p>
</template>
