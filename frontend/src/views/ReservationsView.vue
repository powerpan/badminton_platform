<script setup lang="ts">
import { onMounted, ref } from "vue";

import {
  cancelReservation,
  getMyReservations,
  type Reservation,
  type ReservationStatus,
} from "../api/reservation";

const filters: Array<{ label: string; value: "" | ReservationStatus }> = [
  { label: "全部", value: "" },
  { label: "已确认", value: "confirmed" },
  { label: "已取消", value: "canceled" },
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
  if (reservation.status !== "confirmed") {
    return false;
  }
  return new Date(`${reservation.reserve_date}T${reservation.start_time}`) > new Date();
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

async function cancel(id: number) {
  actionId.value = id;
  message.value = "";
  errorMessage.value = "";
  try {
    await cancelReservation(id);
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
    <p>查看自己的预约记录，并取消尚未开始的已确认预约。</p>
  </section>

  <section class="panel">
    <div class="section-title">
      <div class="tabs">
        <button
          v-for="filter in filters"
          :key="filter.value || 'all'"
          type="button"
          :class="{ active: activeStatus === filter.value }"
          @click="switchStatus(filter.value)"
        >
          {{ filter.label }}
        </button>
      </div>
      <span>共 {{ total }} 条</span>
    </div>

    <p v-if="loading">正在加载预约记录...</p>
    <div v-else-if="reservations.length === 0" class="empty-state">暂无预约记录</div>
    <div v-else class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>预约号</th>
            <th>场地</th>
            <th>日期</th>
            <th>时间</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="reservation in reservations" :key="reservation.id">
            <td>{{ reservation.reservation_no }}</td>
            <td>{{ reservation.court_name }}</td>
            <td>{{ reservation.reserve_date }}</td>
            <td>{{ reservation.start_time }}-{{ reservation.end_time }}</td>
            <td>
              <span class="state-pill" :class="reservation.status">{{ reservation.status }}</span>
            </td>
            <td>
              <button
                type="button"
                class="text-button"
                :disabled="!canCancel(reservation) || actionId === reservation.id"
                @click="cancel(reservation.id)"
              >
                {{ actionId === reservation.id ? "处理中" : "取消" }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="message" class="success-text">{{ message }}</p>
    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
  </section>
</template>
