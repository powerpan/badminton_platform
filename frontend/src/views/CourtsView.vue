<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { getCourtSlots, getCourts, type Court, type SlotItem } from "../api/court";
import { createReservation } from "../api/reservation";

const courts = ref<Court[]>([]);
const selectedCourtId = ref<number | null>(null);
const selectedDate = ref(new Date().toISOString().slice(0, 10));
const slots = ref<SlotItem[]>([]);
const selectedSlot = ref<SlotItem | null>(null);
const remark = ref("");
const loading = ref(false);
const submitting = ref(false);
const message = ref("");
const errorMessage = ref("");

const selectedCourt = computed(() => courts.value.find((court) => court.id === selectedCourtId.value) || null);

async function loadCourts() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await getCourts({ page_size: 100 });
    courts.value = response.data.items;
    if (!selectedCourtId.value && courts.value.length > 0) {
      selectedCourtId.value = courts.value[0].id;
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "场地加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadSlots() {
  if (!selectedCourtId.value) {
    slots.value = [];
    return;
  }
  loading.value = true;
  errorMessage.value = "";
  selectedSlot.value = null;
  try {
    const response = await getCourtSlots(selectedCourtId.value, selectedDate.value);
    slots.value = response.data.slots;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "时间段加载失败";
  } finally {
    loading.value = false;
  }
}

function chooseSlot(slot: SlotItem) {
  if (slot.status !== "available") {
    return;
  }
  selectedSlot.value = slot;
}

async function submitReservation() {
  if (!selectedCourtId.value || !selectedSlot.value) {
    errorMessage.value = "请先选择可预约时间段";
    return;
  }
  submitting.value = true;
  errorMessage.value = "";
  message.value = "";
  try {
    await createReservation({
      court_id: selectedCourtId.value,
      reserve_date: selectedDate.value,
      start_time: selectedSlot.value.start_time,
      end_time: selectedSlot.value.end_time,
      remark: remark.value,
    });
    remark.value = "";
    await loadSlots();
    message.value = "预约成功";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "预约提交失败";
  } finally {
    submitting.value = false;
  }
}

watch([selectedCourtId, selectedDate], async () => {
  message.value = "";
  await loadSlots();
});

onMounted(async () => {
  await loadCourts();
});
</script>

<template>
  <section class="page-header">
    <p class="eyebrow">用户端</p>
    <h1>场地预约</h1>
    <p>选择场地和日期后，系统会按后台规则生成可预约时间段。</p>
  </section>

  <section class="workspace-grid">
    <div class="panel">
      <div class="toolbar-row">
        <label>
          日期
          <input v-model="selectedDate" type="date" />
        </label>
      </div>

      <div v-if="loading && courts.length === 0">正在加载场地...</div>
      <div v-else class="court-list">
        <button
          v-for="court in courts"
          :key="court.id"
          type="button"
          class="court-tile"
          :class="{ active: selectedCourtId === court.id }"
          @click="selectedCourtId = court.id"
        >
          <strong>{{ court.court_name }}</strong>
          <span>{{ court.court_no }}</span>
          <small>{{ court.description || "标准羽毛球场" }}</small>
        </button>
      </div>
    </div>

    <div class="panel">
      <div class="section-title">
        <div>
          <h2>{{ selectedCourt?.court_name || "未选择场地" }}</h2>
          <p>{{ selectedDate }}</p>
        </div>
        <span v-if="loading">刷新中...</span>
      </div>

      <div class="slot-grid">
        <button
          v-for="slot in slots"
          :key="`${slot.start_time}-${slot.end_time}`"
          type="button"
          class="slot-button"
          :class="[slot.status, { active: selectedSlot?.start_time === slot.start_time }]"
          :disabled="slot.status !== 'available'"
          @click="chooseSlot(slot)"
        >
          <span>{{ slot.start_time }}-{{ slot.end_time }}</span>
          <small>{{ slot.status }}</small>
        </button>
      </div>

      <form class="form-stack reserve-form" @submit.prevent="submitReservation">
        <label>
          备注
          <input v-model="remark" maxlength="255" placeholder="可选" />
        </label>
        <button class="primary-button" type="submit" :disabled="submitting || !selectedSlot">
          {{ submitting ? "提交中..." : "提交预约" }}
        </button>
      </form>

      <p v-if="message" class="success-text">{{ message }}</p>
      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
    </div>
  </section>
</template>
