<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { ApiRequestError } from '../api/http';
import { createWalkIn, quoteWalkIn, type WalkIn, type WalkInDraft, type WalkInQuote } from '../api/staff';
import type { CourtSlots, ReservationRules } from '../api/court';
import { useAuthStore } from '../stores/auth';
import { formatMoney } from '../views/admin/shared';

const props = defineProps<{ court: CourtSlots; start: string; rules: ReservationRules; parent?: WalkIn }>();
const emit = defineEmits<{ created: [order: WalkIn]; close: [] }>();
const auth = useAuthStore();
const storageKey = `bf_walkin_attempt_${auth.user?.id}`;
const end = ref(''), guestName = ref(''), guestContact = ref(''), error = ref('');
const quote = ref<WalkInQuote>(), busy = ref(false);
const attempt = ref<{ body: WalkInDraft; parent?: number }>();
let revision = 0;
const minute = (v: string) => Number(v.slice(0,2))*60 + Number(v.slice(3,5));
const choices = computed(() => {
  let next = props.start;
  const values: string[] = [];
  for (const slot of props.court.slots) {
    if (slot.start_time < next) continue;
    if (slot.start_time !== next || slot.status !== 'available' || minute(slot.end_time)-minute(props.start)>props.rules.max_reservation_minutes) break;
    values.push(slot.end_time); next = slot.end_time;
  }
  return values;
});
end.value = choices.value[0] || '';
watch([end, guestName, guestContact], () => { revision++; quote.value = undefined; error.value = ''; });
async function price() {
  const version = ++revision;
  busy.value = true; quote.value = undefined; error.value = '';
  try {
    const result = (await quoteWalkIn({ court_id: props.court.court_id, reserve_date: props.court.date, start_time: props.start, end_time: end.value }, props.parent?.id)).data;
    if (version === revision) quote.value = result;
  } catch (e) { if (version === revision) error.value = e instanceof Error ? e.message : '核价失败'; }
  finally { busy.value = false; }
}
async function submit() {
  if (busy.value || (!quote.value && !attempt.value)) return;
  if (!attempt.value && quote.value) {
    attempt.value = { body: { court_id: props.court.court_id, reserve_date: props.court.date, start_time: props.start,
      end_time: end.value, guest_name: guestName.value, guest_contact: guestContact.value,
      expected_amount_cents: quote.value.payable_amount_cents, request_key: crypto.randomUUID() }, parent: props.parent?.id };
    sessionStorage.setItem(storageKey, JSON.stringify(attempt.value));
  }
  busy.value = true; error.value = '';
  try {
    const result = (await createWalkIn(attempt.value!.body, attempt.value!.parent)).data;
    sessionStorage.removeItem(storageKey); attempt.value = undefined; emit('created',result);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '提交结果待确认';
    if (e instanceof ApiRequestError && e.status && e.status < 500 && e.status !== 401) {
      sessionStorage.removeItem(storageKey); attempt.value = undefined; quote.value = undefined;
    } else error.value += '。请使用原请求重试，或关闭后从待确认请求恢复。';
  } finally { busy.value = false; }
}
</script>
<template>
  <div class="walkin-form">
    <p class="booking-location">{{ court.court.court_name }} · {{ court.date }}</p>
    <p class="booking-rule">{{ parent ? '续场从原单结束时开始，按连续整段原价计费。' : '到店按当前整段原价计费，已过去的分钟不扣减。' }}收款完成后确认场地。</p>
    <el-form label-position="top" :disabled="busy || Boolean(attempt)" @submit.prevent="price">
      <el-form-item label="计费开始"><strong>{{ start }}</strong></el-form-item>
      <el-form-item label="使用至"><el-select v-model="end" placeholder="暂无连续空场"><el-option v-for="value in choices" :key="value" :label="value" :value="value" /></el-select></el-form-item>
      <template v-if="!parent"><el-form-item label="客户称呼（选填）"><el-input v-model="guestName" maxlength="50" placeholder="用于现场识别" /></el-form-item><el-form-item label="联系方式（选填）"><el-input v-model="guestContact" maxlength="50" placeholder="无需注册客户账号" /></el-form-item></template>
      <p v-else>客户：{{ parent.guest_name || '散客' }}</p>
      <el-button v-if="!quote && !attempt" native-type="submit" :disabled="!end" :loading="busy">核对金额</el-button>
    </el-form>
    <div v-if="quote" class="walkin-price"><span>{{ start }}–{{ end }} · 整段原价</span><strong>{{ formatMoney(quote.payable_amount_cents) }}</strong><small>使用模拟支付宝收款，不扣前台账户余额。</small></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <div class="dialog-actions"><el-button :disabled="busy" @click="emit('close')">关闭</el-button><el-button v-if="quote || attempt" type="primary" :loading="busy" @click="submit">{{ attempt ? '使用原请求重试' : '确认金额，创建待收款单' }}</el-button></div>
  </div>
</template>
<style scoped>
.booking-location { font-size: 18px; font-weight: 600; }
.booking-rule { color: #687369; line-height: 1.8; font-size: 14px; }
.walkin-price { border-block: 1px solid #dce3dd; padding: 18px 0; margin: 20px 0; display: grid; gap: 8px; }
.walkin-price strong { font-size: 30px; color: #246044; font-variant-numeric: tabular-nums; }
.walkin-price small { color: #687369; }
.walkin-form .el-select { width: 100%; }
.dialog-actions { flex-wrap: wrap; }
</style>
