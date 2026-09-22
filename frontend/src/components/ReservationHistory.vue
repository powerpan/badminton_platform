<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue';
import { getReservationChanges, type ReservationChange, type BookingSnapshot } from '../api/operations';
const courtText = (snapshot: BookingSnapshot) => snapshot.court_name ? `${snapshot.court_no} ${snapshot.court_name}` : '原场地资料已不可用';
const timeText = (value: string) => value.slice(0, 5);
const props = defineProps<{ reservationId: number }>();
const rows = ref<ReservationChange[]>([]), error = ref('');
let version = 0;
async function load() {
  const request = ++version; error.value = ''; rows.value = [];
  try { const r = await getReservationChanges(props.reservationId); if (request === version) rows.value = r.data.items; }
  catch { if (request === version) error.value = '改期历史暂时无法加载'; }
}
watch(() => props.reservationId, load, { immediate: true });
onUnmounted(() => { version++; });
</script>
<template>
  <div v-if="error" class="quiet-state">{{ error }} <el-button link @click="load">重试</el-button></div>
  <section v-else-if="rows.length" class="reservation-change-history"><h3>改期记录</h3>
    <div v-for="row in rows" :key="row.id"><small>{{ row.created_at }}</small><p>{{ row.before_snapshot.reserve_date }} {{ timeText(row.before_snapshot.start_time) }}–{{ timeText(row.before_snapshot.end_time) }} · {{ courtText(row.before_snapshot) }}<br />→ {{ row.after_snapshot.reserve_date }} {{ timeText(row.after_snapshot.start_time) }}–{{ timeText(row.after_snapshot.end_time) }} · {{ courtText(row.after_snapshot) }}</p><span>余额 {{ row.balance_change_cents >= 0 ? '+' : '' }}{{ (row.balance_change_cents / 100).toFixed(2) }} 元</span></div>
  </section>
</template>
