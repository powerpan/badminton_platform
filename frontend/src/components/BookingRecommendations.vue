<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import { getRecommendations, type Recommendation } from '../api/operations';
import type { Court, ReservationRules } from '../api/court';
const props = defineProps<{ date: string; courts: Court[]; rules: ReservationRules; disabled?: boolean }>();
const emit = defineEmits<{ select: [candidate: Recommendation] }>();
const open = defineModel<boolean>({ default: false });
const loading = ref(false), searched = ref(false), error = ref('');
const earliest = ref('18:00'), duration = ref(props.rules.slot_interval_minutes), preferred = ref<number>();
const items = ref<Recommendation[]>([]);
let version = 0;
const durations = computed(() => Array.from({ length: Math.floor(props.rules.max_reservation_minutes / props.rules.slot_interval_minutes) }, (_, i) => (i + 1) * props.rules.slot_interval_minutes));
watch([() => props.date, earliest, duration, preferred, () => props.rules.slot_interval_minutes, () => props.rules.max_reservation_minutes], () => {
  version++; items.value = []; searched.value = false; error.value = ''; loading.value = false;
  const interval = props.rules.slot_interval_minutes;
  duration.value = Math.max(interval, Math.min(props.rules.max_reservation_minutes, Math.floor(duration.value / interval) * interval));
});
async function search() {
  if (props.disabled || loading.value) return;
  const request = ++version; loading.value = true; error.value = '';
  try {
    const response = await getRecommendations({ reserve_date: props.date, earliest_time: earliest.value, duration_minutes: duration.value, preferred_court_id: preferred.value });
    if (request === version) { items.value = response.data.items; searched.value = true; }
  } catch (e) { if (request === version) error.value = e instanceof Error ? e.message : '推荐暂时无法加载'; }
  finally { if (request === version) loading.value = false; }
}
onUnmounted(() => { version++; });
</script>

<template>
  <section v-show="open" class="booking-recommendations">
    <div class="recommendation-heading"><h2>找空闲场次</h2><el-button text :disabled="disabled" @click="open = false">收起</el-button></div>
    <div class="recommendation-body">
      <el-form label-position="top" class="operations-form" :disabled="disabled" @submit.prevent="search">
        <el-form-item label="最早开始"><el-time-select v-model="earliest" start="00:00" end="23:30" step="00:30" :clearable="false" /></el-form-item>
        <el-form-item label="打多久"><el-select v-model="duration"><el-option v-for="value in durations" :key="value" :value="value" :label="`${value} 分钟`" /></el-select></el-form-item>
        <el-form-item label="偏好场地"><el-select v-model="preferred" clearable placeholder="都可以"><el-option v-for="court in courts" :key="court.id" :value="court.id" :label="court.court_name" /></el-select></el-form-item>
        <el-form-item><el-button type="primary" native-type="submit" :loading="loading">找空闲场次</el-button></el-form-item>
      </el-form>
      <p class="muted-text">优先接近最早时间，再比较场地偏好和会员价。推荐不占位。</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <p v-else-if="searched && !items.length" class="quiet-state" role="status">没有完整空闲场次，试试更短时长、其他日期或更早时间。</p>
      <div v-for="item in items" :key="`${item.court_id}-${item.start_time}`" class="recommendation-row">
        <div><strong>{{ item.start_time }}–{{ item.end_time }} · {{ item.court_name }}</strong><p>{{ item.reasons.join(' · ') }}</p></div>
        <b>¥{{ (item.payable_amount_cents / 100).toFixed(2) }}</b><el-button :disabled="disabled" @click="emit('select', item)">选择这场</el-button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.booking-recommendations { border-block: 1px solid #e3e7e4; padding: 14px 0; margin: 12px 0 18px; }
.recommendation-heading { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.recommendation-heading h2 { font-size: 16px; margin: 0; }
.recommendation-body > .muted-text { font-size: 12px; color: #717973; }
</style>
