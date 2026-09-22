<script setup lang="ts">
import { computed, onMounted, ref, watchEffect } from "vue";

import { getMemberTransactions, type MemberTransaction } from "../api/member";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();

const nickname = ref("");
const contact = ref("");
const oldPassword = ref("");
const newPassword = ref("");
const profileMessage = ref("");
const passwordMessage = ref("");
const errorMessage = ref("");
const ledgerError = ref("");
const loadingProfile = ref(false);
const loadingPassword = ref(false);
const ledgerLoading = ref(false);
const ledgerRows = ref<MemberTransaction[]>([]);
const ledgerFilter = ref("");
const ledgerPage = ref({ page: 1, page_size: 8, total: 0 });

const currentUser = computed(() => authStore.user);
const currentMember = computed(() => currentUser.value?.member);

function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatSignedMoney(cents: number) {
  if (cents > 0) return `+${formatMoney(cents)}`;
  if (cents < 0) return `-${formatMoney(Math.abs(cents))}`;
  return formatMoney(0);
}

function formatSignedPoints(points: number) {
  if (points > 0) return `+${points.toLocaleString("zh-CN")}`;
  return points.toLocaleString("zh-CN");
}

function validityText(value: string | null | undefined) {
  return value ? `有效期至 ${value}` : "长期有效";
}

function discountText(rate: number) {
  return rate >= 100 ? "无折扣" : `${rate / 10} 折`;
}

function changeClass(value: number) {
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return "neutral";
}

function relatedText(transaction: MemberTransaction) {
  if (transaction.reservation_id) return `关联预约 #${transaction.reservation_id}`;
  if (transaction.shop_order_id) return `关联商城订单 #${transaction.shop_order_id}`;
  if (transaction.operator_username) return `操作人：${transaction.operator_username}`;
  return "会员账户流水";
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

async function loadLedger(reset = false) {
  if (reset) ledgerPage.value.page = 1;
  ledgerLoading.value = true;
  ledgerError.value = "";
  try {
    const response = await getMemberTransactions({
      transaction_type: ledgerFilter.value || undefined,
      page: ledgerPage.value.page,
      page_size: ledgerPage.value.page_size,
    });
    ledgerRows.value = response.data.items;
    ledgerPage.value.total = response.data.total;
  } catch (error) {
    ledgerError.value = error instanceof Error ? error.message : "余额明细加载失败";
  } finally {
    ledgerLoading.value = false;
  }
}

async function changeLedgerPage(nextPage: number) {
  ledgerPage.value.page = nextPage;
  await loadLedger();
}

onMounted(() => loadLedger());
</script>

<template>
  <section class="page-header">
    <h1>账号资料</h1>
    <p v-if="currentUser">{{ currentUser.nickname || currentUser.username }}，在这里查看会员权益和账号信息。</p>
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
            <el-tag :type="currentMember.level !== currentMember.effective_level ? 'info' : 'success'" effect="plain">{{ currentMember.level_label }}{{ currentMember.level !== currentMember.effective_level ? ' · 已到期' : '' }}</el-tag>
          </div>
        </template>
        <div class="member-profile-main">
          <strong>{{ currentMember.level_label }}</strong>
          <span>{{ validityText(currentMember.expires_at) }}{{ currentMember.level !== currentMember.effective_level ? '，当前按普通会员价格结算' : '' }}</span>
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

    <el-col :xs="24">
      <el-card shadow="never" class="panel-card list-page-card member-ledger-card" v-loading="ledgerLoading">
        <template #header>
          <div class="card-header-row">
            <strong>余额明细</strong>
            <span>展示余额和积分每一次变动</span>
          </div>
        </template>

        <el-alert
          v-if="ledgerError"
          class="page-alert"
          :title="ledgerError"
          type="error"
          show-icon
          :closable="false"
        />

        <div class="list-toolbar">
          <el-radio-group v-model="ledgerFilter" @change="() => loadLedger(true)">
            <el-radio-button :value="''">全部</el-radio-button>
            <el-radio-button :value="'reservation_charge'">预约扣款</el-radio-button>
            <el-radio-button :value="'reservation_refund'">预约退款</el-radio-button>
            <el-radio-button :value="'reservation_reschedule'">改期差额</el-radio-button>
            <el-radio-button :value="'shop_purchase'">商城支付</el-radio-button>
            <el-radio-button :value="'shop_refund'">商城退款</el-radio-button>
            <el-radio-button :value="'admin_adjust'">后台调整</el-radio-button>
          </el-radio-group>
          <el-button plain :loading="ledgerLoading" @click="loadLedger()">刷新</el-button>
        </div>

        <el-empty v-if="ledgerRows.length === 0 && !ledgerLoading" description="暂无余额明细" />
        <div v-else class="member-ledger-list">
          <article v-for="transaction in ledgerRows" :key="transaction.id" class="member-ledger-item">
            <div class="member-ledger-main">
              <div class="member-ledger-title">
                <el-tag effect="plain">{{ transaction.transaction_type_label }}</el-tag>
                <strong>{{ transaction.reason || transaction.transaction_type_label }}</strong>
              </div>
              <p>{{ relatedText(transaction) }}</p>
              <span>{{ transaction.created_at }}</span>
            </div>
            <div class="member-ledger-values">
              <strong :class="changeClass(transaction.balance_change_cents)">
                {{ formatSignedMoney(transaction.balance_change_cents) }}
              </strong>
              <span>余额 {{ formatMoney(transaction.balance_before_cents) }} 至 {{ formatMoney(transaction.balance_after_cents) }}</span>
              <small :class="changeClass(transaction.points_change)">
                积分 {{ formatSignedPoints(transaction.points_change) }}
              </small>
            </div>
          </article>
        </div>

        <el-pagination
          class="element-pagination"
          :current-page="ledgerPage.page"
          :page-size="ledgerPage.page_size"
          :total="ledgerPage.total"
          layout="prev, pager, next, total"
          @current-change="changeLedgerPage"
        />
      </el-card>
    </el-col>
  </el-row>
</template>
