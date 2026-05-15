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
const currentMember = computed(() => currentUser.value?.member);

function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function validityText(value: string | null | undefined) {
  return value ? `有效期至 ${value}` : "长期有效";
}

function discountText(rate: number) {
  return rate >= 100 ? "无折扣" : `${rate / 10} 折`;
}

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

  <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />

  <el-row :gutter="18" class="element-grid">
    <el-col v-if="currentUser?.must_change_password" :xs="24">
      <el-alert title="默认管理员密码提醒" description="当前管理员账号仍在使用默认密码，请先完成密码修改，再继续用于演示或部署。" type="warning" show-icon :closable="false" />
    </el-col>

    <el-col v-if="currentMember" :xs="24" :lg="10">
      <el-card shadow="never" class="panel-card member-profile-card">
        <template #header>
          <div class="card-header-row">
            <strong>会员账户</strong>
            <el-tag type="success" effect="plain">{{ currentMember.level_label }}</el-tag>
          </div>
        </template>
        <div class="member-profile-main">
          <strong>{{ currentMember.level_label }}</strong>
          <span>{{ validityText(currentMember.expires_at) }}</span>
        </div>
        <div class="member-metric-list">
          <div>
            <span>余额</span>
            <strong>{{ formatMoney(currentMember.balance_cents) }}</strong>
          </div>
          <div>
            <span>积分</span>
            <strong>{{ currentMember.points.toLocaleString("zh-CN") }}</strong>
          </div>
          <div>
            <span>当前折扣</span>
            <strong>{{ discountText(currentMember.effective_discount_rate) }}</strong>
          </div>
        </div>
      </el-card>
    </el-col>

    <el-col :xs="24" :lg="7">
      <el-card shadow="never" class="panel-card">
        <template #header><strong>基本信息</strong></template>
        <el-form label-position="top" class="element-form" @submit.prevent="saveProfile">
          <el-form-item label="昵称">
            <el-input v-model="nickname" />
          </el-form-item>
          <el-form-item label="联系方式">
            <el-input v-model="contact" />
          </el-form-item>
          <el-alert v-if="profileMessage" :title="profileMessage" type="success" show-icon :closable="false" />
          <el-button type="primary" :loading="loadingProfile" native-type="submit">保存资料</el-button>
        </el-form>
      </el-card>
    </el-col>

    <el-col :xs="24" :lg="7">
      <el-card shadow="never" class="panel-card">
        <template #header><strong>修改密码</strong></template>
        <el-form label-position="top" class="element-form" @submit.prevent="savePassword">
          <el-form-item label="旧密码" required>
            <el-input v-model="oldPassword" autocomplete="current-password" type="password" show-password />
          </el-form-item>
          <el-form-item label="新密码" required>
            <el-input v-model="newPassword" autocomplete="new-password" type="password" show-password />
          </el-form-item>
          <el-alert v-if="passwordMessage" :title="passwordMessage" type="success" show-icon :closable="false" />
          <el-button type="primary" :loading="loadingPassword" native-type="submit">修改密码</el-button>
        </el-form>
      </el-card>
    </el-col>
  </el-row>
</template>
