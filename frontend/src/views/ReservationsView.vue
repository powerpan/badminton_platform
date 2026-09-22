<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import RescheduleDrawer from "../components/RescheduleDrawer.vue";
import ReservationHistory from "../components/ReservationHistory.vue";
import BookingAgenda from "../components/BookingAgenda.vue";
import { ElMessageBox } from "element-plus";

import {
  cancelReservation,
  getMyReservations,
  getReservation,
  payReservationOrder,
  type Reservation,
  type ReservationStatus,
} from "../api/reservation";
import { useAuthStore } from "../stores/auth";
import { countdownText, remainingSeconds, formatDeadline } from "../utils/booking";

const authStore = useAuthStore();
const route = useRoute();
const agenda = ref<InstanceType<typeof BookingAgenda> | null>(null);

const filters: Array<{ label: string; value: "" | ReservationStatus }> = [
  { label: "全部", value: "" },
  { label: "待支付", value: "pending" },
  { label: "已确认", value: "confirmed" },
  { label: "已取消", value: "canceled" },
  { label: "已过期", value: "expired" },
  { label: "已结束", value: "completed" },
];

const initialStatus = filters.some(item => item.value === route.query.status) ? String(route.query.status) as ReservationStatus : "";
const activeStatus = ref<"" | ReservationStatus>(initialStatus);
const reservations = ref<Reservation[]>([]);
const selectedReservation = ref<Reservation | null>(null);
const detailVisible = ref(false);
const rescheduleVisible = ref(false);
async function afterReschedule() {
  await loadReservations(); await agenda.value?.refresh(); await authStore.fetchProfile();
  message.value = '改期成功，原预约已更新';
}
function canReschedule(reservation: Reservation) {
  return reservation.status === 'confirmed' && reservation.order_status === 'paid' && !reservation.attendance_outcome && canCancel(reservation);
}
function attendanceText(value: Reservation['attendance_outcome']) { return value === 'checked_in' ? '已到场核销' : value === 'no_show' ? '已确认未到场' : '未记录'; }
const loading = ref(false);
const actionId = ref<number | null>(null);
const total = ref(0);
const page = ref(1);
const pageSize = 10;
const now = ref(Date.now());
let requestVersion = 0;
let timer: ReturnType<typeof setInterval> | undefined;
let lastExpiryRefresh = 0;
const message = ref("");
const errorMessage = ref("");

function canCancel(reservation: Reservation) {
  if (reservation.attendance_outcome || !["pending", "confirmed"].includes(reservation.status)) {
    return false;
  }
  return new Date(`${reservation.reserve_date}T${reservation.start_time}`).getTime() > now.value;
}

function canPay(reservation: Reservation) {
  return reservation.status === "pending" && reservation.order_status === "pending" && Boolean(reservation.order_id)
    && remainingSeconds(reservation.order_expires_at, now.value) > 0;
}

function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function discountText(rate: number | null | undefined) {
  const value = rate || 100;
  return value >= 100 ? "无折扣" : `${value / 10} 折`;
}

function memberLevelText(level: string | null | undefined) {
  const labels: Record<string, string> = { normal: "普通会员", silver: "银卡会员", gold: "金卡会员", diamond: "钻石会员" };
  return level ? labels[level] || level : "—";
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
    completed: "已结束",
  };
  return map[status];
}

function payMethodText(value: string | null | undefined) {
  return value === "balance" ? "会员余额" : value || "-";
}

function openReservationDetail(reservation: Reservation) {
  selectedReservation.value = reservation;
  detailVisible.value = true;
}

async function loadReservations() {
  const version = ++requestVersion;
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await getMyReservations({
      status: activeStatus.value || undefined,
      page: page.value,
      page_size: pageSize,
    });
    if (version !== requestVersion) return;
    reservations.value = response.data.items;
    total.value = response.data.total;
    if (page.value > 1 && !reservations.value.length) {
      page.value = Math.max(1, Math.ceil(total.value / pageSize));
      await loadReservations();
      return;
    }
    if (selectedReservation.value) {
      selectedReservation.value = reservations.value.find(item => item.id === selectedReservation.value?.id) || selectedReservation.value;
    }
  } catch (error) {
    if (version !== requestVersion) return;
    errorMessage.value = error instanceof Error ? error.message : "预约记录加载失败";
  } finally {
    if (version === requestVersion) loading.value = false;
  }
}

async function switchStatus(status: "" | ReservationStatus) {
  activeStatus.value = status;
  page.value = 1;
  message.value = "";
  await loadReservations();
}

async function switchStatusValue(value: string | number | boolean) {
  await switchStatus(String(value) as "" | ReservationStatus);
}

async function pay(reservation: Reservation) {
  if (!reservation.order_id || actionId.value !== null) return;
  actionId.value = reservation.id; message.value = ''; errorMessage.value = '';
  try {
    const latest = (await getReservation(reservation.id)).data;
    if (selectedReservation.value?.id === latest.id) selectedReservation.value = latest;
    if (latest.status !== 'pending' || latest.order_status !== 'pending' || !latest.order_id) {
      await loadReservations(); errorMessage.value = '预约状态已变化，请查看最新记录'; return;
    }
    try {
      await ElMessageBox.confirm(
        `确认使用会员余额支付 ${formatMoney(latest.order_amount_cents ?? latest.payable_amount_cents)}？支付后预约将立即确认。`,
        '支付待支付预约', { confirmButtonText: '确认支付', cancelButtonText: '取消', type: 'warning' },
      );
    } catch { return; }
    const response = await payReservationOrder(latest.order_id);
    if (selectedReservation.value?.id === reservation.id) selectedReservation.value = response.data;
    await Promise.allSettled([authStore.fetchProfile(), agenda.value?.refresh(), loadReservations()]);
    message.value = '支付成功，预约已确认';
  } catch (error) {
    const failure = error instanceof Error ? error.message : '支付失败';
    await loadReservations(); errorMessage.value = failure;
  } finally { actionId.value = null; }
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
    const response = await cancelReservation(reservation.id);
    if (selectedReservation.value?.id === reservation.id) {
      selectedReservation.value = response.data;
    }
    await authStore.fetchProfile();
    await agenda.value?.refresh();
    message.value = "预约已取消";
    await loadReservations();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "取消预约失败";
  } finally {
    actionId.value = null;
  }
}

async function changePage(value: number) {
  page.value = value;
  await loadReservations();
}

function refreshOnVisible() {
  if (!document.hidden && !loading.value && actionId.value === null) void loadReservations();
}

watch(() => route.query.status, (value) => {
  const status = filters.some(item => item.value === value) ? String(value) as ReservationStatus : "";
  if (status !== activeStatus.value) void switchStatus(status);
});

onMounted(() => {
  void loadReservations();
  timer = setInterval(() => {
    now.value = Date.now();
    if (!loading.value && actionId.value === null && !document.hidden && now.value - lastExpiryRefresh > 5000
      && reservations.value.some(item => item.status === "pending" && !remainingSeconds(item.order_expires_at, now.value))) {
      lastExpiryRefresh = now.value;
      void loadReservations();
    }
  }, 1000);
  document.addEventListener("visibilitychange", refreshOnVisible);
});

onUnmounted(() => {
  requestVersion += 1;
  if (timer) clearInterval(timer);
  document.removeEventListener("visibilitychange", refreshOnVisible);
});
</script>

<template>
  <section class="page-header">
    <h1>我的预订</h1>
    <p>查看自己的预约记录，处理待支付订单，并取消尚未开始的预约。</p>
  </section>

  <BookingAgenda ref="agenda" detail-actions @open="openReservationDetail" />

  <el-card shadow="never" class="panel-card reservation-history">
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

    <el-table class="reservation-desktop-table" v-loading="loading" :data="reservations" empty-text="暂无预约记录" stripe>
      <el-table-column prop="reservation_no" label="预约号" min-width="150" />
      <el-table-column prop="court_name" label="场地" min-width="120" />
      <el-table-column prop="reserve_date" label="日期" min-width="115" />
      <el-table-column label="时间" min-width="120">
        <template #default="{ row }">{{ row.start_time }}-{{ row.end_time }}</template>
      </el-table-column>
      <el-table-column label="应付金额" min-width="120">
        <template #default="{ row }">{{ formatMoney(row.payable_amount_cents) }}</template>
      </el-table-column>
      <el-table-column label="状态" min-width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" effect="plain">{{ statusText(row.status) }}</el-tag>
          <small v-if="row.status === 'pending'" class="payment-countdown">{{ countdownText(row.order_expires_at, now) }}</small>
        </template>
      </el-table-column>
      <el-table-column label="操作" fixed="right" width="178">
        <template #default="{ row }">
          <el-button link type="primary" @click="openReservationDetail(row)">详情</el-button>
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
    <div class="reservation-mobile-list" v-loading="loading">
      <div v-if="!reservations.length && !loading" class="quiet-state">{{ activeStatus ? '暂无此状态的预约' : '还没有预约记录' }}<RouterLink to="/courts" class="text-action">去预订场地</RouterLink></div>
      <article v-for="item in reservations" :key="item.id" class="reservation-line">
        <div class="reservation-line-heading"><strong>{{ item.court_name }}</strong><el-tag :type="statusType(item.status)" effect="plain">{{ statusText(item.status) }}</el-tag></div>
        <p>{{ item.reserve_date }} · {{ item.start_time }}–{{ item.end_time }}</p>
        <small>{{ item.reservation_no }}</small>
        <span v-if="item.status === 'pending'" class="payment-countdown">{{ countdownText(item.order_expires_at, now) }}</span>
        <div class="reservation-line-actions"><b>{{ formatMoney(item.payable_amount_cents) }}</b>
          <el-button @click="openReservationDetail(item)">详情</el-button>
          <el-button v-if="canPay(item)" type="primary" :loading="actionId === item.id" @click="pay(item)">支付</el-button>
          <el-button v-if="canCancel(item)" link type="danger" :loading="actionId === item.id" @click="cancel(item)">取消</el-button>
        </div>
      </article>
    </div>
    <el-pagination class="element-pagination" :current-page="page" :page-size="pageSize" :total="total"
      layout="prev, pager, next, total" @current-change="changePage" />
  </el-card>

  <el-dialog v-model="detailVisible" title="预约详情" width="min(680px, 92vw)" class="detail-dialog">
    <div v-if="selectedReservation" class="record-detail">
      <el-descriptions :column="1" border class="compact-descriptions">
        <el-descriptions-item label="预约号">{{ selectedReservation.reservation_no }}</el-descriptions-item>
        <el-descriptions-item label="场地">{{ selectedReservation.court_no }} {{ selectedReservation.court_name }}</el-descriptions-item>
        <el-descriptions-item label="日期时间">
          {{ selectedReservation.reserve_date }} {{ selectedReservation.start_time }}-{{ selectedReservation.end_time }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusType(selectedReservation.status)" effect="plain">{{ statusText(selectedReservation.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="会员折扣">
          {{ memberLevelText(selectedReservation.member_level_snapshot) }} / {{ discountText(selectedReservation.discount_rate) }}
        </el-descriptions-item>
        <el-descriptions-item label="场地费">{{ formatMoney(selectedReservation.original_amount_cents) }}</el-descriptions-item>
        <el-descriptions-item label="优惠金额">-{{ formatMoney(selectedReservation.discount_amount_cents) }}</el-descriptions-item>
        <el-descriptions-item label="应付金额">{{ formatMoney(selectedReservation.payable_amount_cents) }}</el-descriptions-item>
        <el-descriptions-item label="积分">+{{ selectedReservation.points_awarded || 0 }}</el-descriptions-item>
        <el-descriptions-item label="订单号">{{ selectedReservation.order_no || "-" }}</el-descriptions-item>
        <el-descriptions-item label="支付方式">{{ payMethodText(selectedReservation.order_pay_method) }}</el-descriptions-item>
        <el-descriptions-item label="支付截止">{{ formatDeadline(selectedReservation.order_expires_at) }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedReservation.status === 'pending'" label="剩余支付时间">{{ countdownText(selectedReservation.order_expires_at, now) }}</el-descriptions-item>
        <el-descriptions-item label="支付时间">{{ selectedReservation.order_paid_at || "-" }}</el-descriptions-item>
        <el-descriptions-item label="取消时间">{{ selectedReservation.canceled_at || selectedReservation.order_canceled_at || "-" }}</el-descriptions-item>
        <el-descriptions-item label="到场情况">{{ attendanceText(selectedReservation.attendance_outcome) }}<span v-if="selectedReservation.attendance_recorded_at"> · {{ selectedReservation.attendance_recorded_at }}</span></el-descriptions-item>
        <el-descriptions-item label="备注">{{ selectedReservation.remark || "-" }}</el-descriptions-item>
      </el-descriptions>
      <ReservationHistory v-if="detailVisible" :reservation-id="selectedReservation.id" />
      <div class="dialog-actions">
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="canReschedule(selectedReservation)" type="primary" @click="detailVisible = false; rescheduleVisible = true">预约改期</el-button>
        <el-button v-if="canPay(selectedReservation)" type="primary" :loading="actionId === selectedReservation.id" @click="pay(selectedReservation)">支付</el-button>
        <el-button v-if="canCancel(selectedReservation)" type="danger" plain :loading="actionId === selectedReservation.id" @click="cancel(selectedReservation)">取消预约</el-button>
      </div>
    </div>
  </el-dialog>
  <RescheduleDrawer v-model="rescheduleVisible" :reservation="selectedReservation" @changed="afterReschedule" />
</template>
