<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessageBox } from "element-plus";

import {
  cancelReservation,
  getMyReservations,
  payReservationOrder,
  type Reservation,
  type ReservationStatus,
} from "../api/reservation";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();

const filters: Array<{ label: string; value: "" | ReservationStatus }> = [
  { label: "全部", value: "" },
  { label: "待支付", value: "pending" },
  { label: "已确认", value: "confirmed" },
  { label: "已取消", value: "canceled" },
  { label: "已过期", value: "expired" },
  { label: "已完成", value: "completed" },
];

const activeStatus = ref<"" | ReservationStatus>("");
const reservations = ref<Reservation[]>([]);
const loading = ref(false);
const actionId = ref<number | null>(null);
const total = ref(0);
const message = ref("");
const errorMessage = ref("");

function canCancel(reservation: Reservation) {
  if (!["pending", "confirmed"].includes(reservation.status)) {
    return false;
  }
  return new Date(`${reservation.reserve_date}T${reservation.start_time}`) > new Date();
}

function canPay(reservation: Reservation) {
  return reservation.status === "pending" && reservation.order_status === "pending" && Boolean(reservation.order_id);
}

function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function statusType(status: ReservationStatus) {
  const map: Record<ReservationStatus, "primary" | "success" | "info" | "warning" | "danger"> = {
    pending: "warning",
    confirmed: "success",
    canceled: "info",
    expired: "danger",
    completed: "primary",
  };
  return map[status];
}

function statusText(status: ReservationStatus) {
  const map: Record<ReservationStatus, string> = {
    pending: "待支付",
    confirmed: "已确认",
    canceled: "已取消",
    expired: "已过期",
    completed: "已完成",
  };
  return map[status];
}

function orderExpiryText(reservation: Reservation) {
  return reservation.order_expires_at || "-";
}

async function loadReservations() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await getMyReservations({
      status: activeStatus.value || undefined,
      page_size: 50,
    });
    reservations.value = response.data.items;
    total.value = response.data.total;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "预约记录加载失败";
  } finally {
    loading.value = false;
  }
}

async function switchStatus(status: "" | ReservationStatus) {
  activeStatus.value = status;
  message.value = "";
  await loadReservations();
}

async function switchStatusValue(value: string | number | boolean) {
  await switchStatus(String(value) as "" | ReservationStatus);
}

async function pay(reservation: Reservation) {
  if (!reservation.order_id) return;
  try {
    await ElMessageBox.confirm(
      `确认使用会员余额支付 ${formatMoney(reservation.order_amount_cents ?? reservation.payable_amount_cents)}？支付后预约将立即确认。`,
      "支付待支付预约",
      {
        confirmButtonText: "确认支付",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  actionId.value = reservation.id;
  message.value = "";
  errorMessage.value = "";
  try {
    await payReservationOrder(reservation.order_id);
    await authStore.fetchProfile();
    message.value = "支付成功，预约已确认";
    await loadReservations();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "支付失败";
    await loadReservations();
  } finally {
    actionId.value = null;
  }
}

async function cancel(reservation: Reservation) {
  const tip = reservation.status === "pending"
    ? "确认取消该待支付预约？取消后会释放场地占用，不涉及退款。"
    : "确认取消该预约？取消后会退回余额并扣回对应积分。";
  try {
    await ElMessageBox.confirm(tip, "取消预约", {
      confirmButtonText: "确认取消",
      cancelButtonText: "再看看",
      type: "warning",
    });
  } catch {
    return;
  }
  actionId.value = reservation.id;
  message.value = "";
  errorMessage.value = "";
  try {
    await cancelReservation(reservation.id);
    await authStore.fetchProfile();
    message.value = "预约已取消";
    await loadReservations();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "取消预约失败";
  } finally {
    actionId.value = null;
  }
}

onMounted(loadReservations);
</script>

<template>
  <section class="page-header">
    <p class="eyebrow">用户端</p>
    <h1>我的预约</h1>
    <p>查看自己的预约记录，处理待支付订单，并取消尚未开始的预约。</p>
  </section>

  <el-card shadow="never" class="panel-card">
    <div class="section-title element-section-title">
      <el-radio-group :model-value="activeStatus" @change="switchStatusValue">
        <el-radio-button v-for="filter in filters" :key="filter.value || 'all'" :value="filter.value">
          {{ filter.label }}
        </el-radio-button>
      </el-radio-group>
      <el-tag effect="plain">共 {{ total }} 条</el-tag>
    </div>

    <el-alert v-if="message" class="page-alert" :title="message" type="success" show-icon :closable="false" />
    <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />

    <el-table v-loading="loading" :data="reservations" empty-text="暂无预约记录" stripe>
      <el-table-column prop="reservation_no" label="预约号" min-width="160" />
      <el-table-column prop="court_name" label="场地" min-width="110" />
      <el-table-column prop="reserve_date" label="日期" min-width="115" />
      <el-table-column label="时间" min-width="130">
        <template #default="{ row }">{{ row.start_time }}-{{ row.end_time }}</template>
      </el-table-column>
      <el-table-column label="原价" min-width="110">
        <template #default="{ row }">{{ formatMoney(row.original_amount_cents) }}</template>
      </el-table-column>
      <el-table-column label="折扣" min-width="110">
        <template #default="{ row }">-{{ formatMoney(row.discount_amount_cents) }}</template>
      </el-table-column>
      <el-table-column label="应付金额" min-width="120">
        <template #default="{ row }">{{ formatMoney(row.payable_amount_cents) }}</template>
      </el-table-column>
      <el-table-column label="积分" min-width="90">
        <template #default="{ row }">+{{ row.points_awarded }}</template>
      </el-table-column>
      <el-table-column label="状态" min-width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" effect="plain">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="支付截止" min-width="160">
        <template #default="{ row }">{{ row.status === "pending" ? orderExpiryText(row) : "-" }}</template>
      </el-table-column>
      <el-table-column label="操作" fixed="right" width="150">
        <template #default="{ row }">
          <el-button
            v-if="canPay(row)"
            link
            type="primary"
            :disabled="actionId === row.id"
            :loading="actionId === row.id"
            @click="pay(row)"
          >
            支付
          </el-button>
          <el-button
            link
            type="danger"
            :disabled="!canCancel(row) || actionId === row.id"
            :loading="actionId === row.id"
            @click="cancel(row)"
          >
            取消
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
