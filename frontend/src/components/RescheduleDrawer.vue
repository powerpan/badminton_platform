<script setup lang="ts">
import { ApiRequestError } from '../api/http';
import { computed, onUnmounted, ref, watch } from 'vue';
import { getAllCourts, getReservationRules, type Court, type ReservationRules } from '../api/court';
import type { Reservation } from '../api/reservation';
import { getRescheduleQuote, rescheduleReservation, type BookingTarget, type RescheduleQuote } from '../api/operations';
const visible = defineModel<boolean>({ default: false });
const props = defineProps<{ reservation: Reservation | null }>();
const emit = defineEmits<{ changed: []; paymentRequired: [paymentId: number] }>();
const courts = ref<Court[]>([]), rules = ref<ReservationRules>();
const target = ref<BookingTarget>({ court_id: 0, reserve_date: '', start_time: '', end_time: '' });
const quote = ref<RescheduleQuote>(), error = ref(''), loading = ref(false), submitting = ref(false), requestKey = ref('');
let version = 0;
const step = computed(() => { const n = rules.value?.slot_interval_minutes || 60; return `${String(Math.floor(n / 60)).padStart(2, '0')}:${String(n % 60).padStart(2, '0')}`; });
watch(target, () => { version++; quote.value = undefined; requestKey.value = ''; loading.value = false; error.value = ''; }, { deep: true });
watch(visible, async (value) => {
  version++; quote.value = undefined; error.value = '';
  if (!value || !props.reservation) return;
  const r = props.reservation;
  target.value = { court_id: r.court_id, reserve_date: r.reserve_date, start_time: r.start_time, end_time: r.end_time };
  loading.value = true;
  try { const [c, r] = await Promise.all([getAllCourts(1), getReservationRules()]); courts.value = c; rules.value = r.data; }
  catch (e) { error.value = e instanceof Error ? e.message : '改期信息加载失败'; }
  finally { loading.value = false; }
});
async function preview() {
  if (!props.reservation) return;
  const current = ++version; loading.value = true; error.value = ''; quote.value = undefined; requestKey.value = '';
  try {
    const response = await getRescheduleQuote(props.reservation.id, { ...target.value });
    if (current === version) { quote.value = response.data; requestKey.value = crypto.randomUUID(); }
  } catch (e) { if (current === version) error.value = e instanceof Error ? e.message : '报价失败'; }
  finally { if (current === version) loading.value = false; }
}
async function submit() {
  if (!quote.value || !props.reservation || submitting.value) return;
  submitting.value = true; error.value = '';
  try {
    const response = await rescheduleReservation(props.reservation.id, { ...quote.value.target, expected_revision: quote.value.revision, expected_amount_cents: quote.value.payable_amount_cents, request_key: requestKey.value });
    visible.value = false;
    if (response.data.requires_payment && response.data.payment) emit('paymentRequired', response.data.payment.id);
    else emit('changed');
  } catch (e) {
    error.value = e instanceof Error ? e.message : '改期失败，请重试';
    if (e instanceof ApiRequestError && e.status === 409) { quote.value = undefined; requestKey.value = ''; }
  }
  finally { submitting.value = false; }
}
function disabledDate(day: Date) { const text = `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,'0')}-${String(day.getDate()).padStart(2,'0')}`; return !rules.value || text < rules.value.min_date || text > rules.value.max_date; }
onUnmounted(() => { version++; });
</script>

<template>
  <el-drawer v-model="visible" title="预约改期" size="min(520px, 100vw)" class="admin-edit-drawer" :close-on-click-modal="!submitting" :close-on-press-escape="!submitting" :show-close="!submitting">
    <p v-if="reservation" class="muted-text">原场次：{{ reservation.reserve_date }} {{ reservation.start_time }}–{{ reservation.end_time }} · {{ reservation.court_name }}</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <el-form v-if="rules" label-position="top" :disabled="submitting" @submit.prevent="preview">
      <el-form-item label="新日期"><el-date-picker v-model="target.reserve_date" type="date" value-format="YYYY-MM-DD" :disabled-date="disabledDate" :clearable="false" /></el-form-item>
      <el-form-item label="新场地"><el-select v-model="target.court_id"><el-option v-for="court in courts" :key="court.id" :value="court.id" :label="court.court_name" /></el-select></el-form-item>
      <el-form-item label="开始时间"><el-time-select v-model="target.start_time" :start="rules.business_start_time" :end="rules.business_end_time" :step="step" :clearable="false" /></el-form-item>
      <el-form-item label="结束时间"><el-time-select v-model="target.end_time" :start="rules.business_start_time" :end="rules.business_end_time" :step="step" :min-time="target.start_time" :clearable="false" /></el-form-item>
      <el-button native-type="submit" :loading="loading">计算改期差价</el-button>
    </el-form>
    <div v-if="quote" class="reschedule-quote" role="status">
      <p>新场次合计 <strong>¥{{ (quote.payable_amount_cents / 100).toFixed(2) }}</strong></p>
      <p>{{ quote.difference_cents > 0 ? '需补差价' : quote.difference_cents < 0 ? '原渠道退款' : '无需补差价' }} <b v-if="quote.difference_cents">¥{{ (Math.abs(quote.difference_cents) / 100).toFixed(2) }}</b></p>
      <p v-if="reservation?.order_pay_method === 'mock_alipay' && quote.difference_cents > 0">确认后生成模拟支付宝补差单，付款成功才会改期，目标场次不提前占用。</p>
      <p class="muted-text">按新日期的会员权益结算。确认成功后更新原预约，失败时保留原场次。</p>
      <el-button type="primary" :loading="submitting" @click="submit">确认改期</el-button>
    </div>
  </el-drawer>
</template>
