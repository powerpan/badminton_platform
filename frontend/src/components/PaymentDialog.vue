<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import { getPayment, paymentAction, type Payment, type PaymentAction } from '../api/payment';
import { useAuthStore } from '../stores/auth';
import { countdownText } from '../utils/booking';

const visible = defineModel<boolean>({ default: false });
const props = defineProps<{ paymentId: number | null }>();
const emit = defineEmits<{ paid: [payment: Payment]; updated: [] }>();
const auth = useAuthStore();
const payment = ref<Payment>(), loading = ref(false), busy = ref(false), error = ref(''), notice = ref('');
const now = ref(Date.now());
let version = 0, offset = 0, reported = false;
const keys = new Map<string, string>();
const timer = setInterval(() => { now.value = Date.now() + offset; }, 1000);
const pending = computed(() => payment.value?.status === 'pending' && new Date(payment.value.expires_at).getTime() > now.value);
const money = (cents: number) => `¥${(cents / 100).toFixed(2)}`;
const status = computed(() => ({ pending: '待付款', succeeded: '已付款', canceled: '已取消', expired: '已过期', refunded: '已退款' }[payment.value?.status || 'pending']));

async function refresh() {
  if (!props.paymentId) return;
  const current = ++version; loading.value = true;
  try {
    const response = await getPayment(props.paymentId);
    if (current !== version || !visible.value) return;
    payment.value = response.data;
    offset = new Date(response.data.server_now).getTime() - Date.now(); now.value = Date.now() + offset;
    if (payment.value.status === 'succeeded' && !reported) { reported = true; emit('paid', payment.value); }
  } finally { if (current === version) loading.value = false; }
}
async function query() {
  error.value = '';
  try { await refresh(); } catch (e) { error.value = e instanceof Error ? e.message : '付款状态暂时无法查询'; }
}
watch(() => [visible.value, props.paymentId] as const, async ([open]) => {
  version++; payment.value = undefined; error.value = ''; notice.value = ''; reported = false;
  if (open) await query();
});

async function submit(action: PaymentAction) {
  if (!props.paymentId || busy.value || !pending.value) return;
  busy.value = true; error.value = ''; notice.value = '';
  const storageKey = `bf-payment:${auth.user?.id}:${props.paymentId}:${action}`;
  let key = keys.get(storageKey);
  try {
    key ||= sessionStorage.getItem(storageKey) || crypto.randomUUID();
    keys.set(storageKey, key); sessionStorage.setItem(storageKey, key);
    await paymentAction(props.paymentId, action, key);
    await refresh();
    sessionStorage.removeItem(storageKey); keys.delete(storageKey);
    if (action === 'mock-fail') notice.value = '已模拟付款失败，本次没有收款，可以再次付款。';
    if (action === 'cancel') notice.value = '补差单已取消，原预约保持不变。';
    emit('updated');
  } catch (e) {
    error.value = e instanceof Error ? e.message : '请求未得到确认';
    try {
      await refresh();
      if (payment.value?.status === 'succeeded') error.value = '';
      else if (payment.value?.status === 'pending') error.value += '。已重新查询，当前仍待付款。';
    } catch { error.value += '。暂时无法确认结果，请查询状态或使用原请求重试。'; }
  } finally { busy.value = false; }
}
onUnmounted(() => { version++; clearInterval(timer); });
</script>

<template>
  <el-dialog v-model="visible" :title="payment?.business_type === 'recharge' ? '会员储值收款' : payment?.business_type === 'shop' ? '商城付款' : payment?.purpose === 'reschedule' ? '改期补差付款' : '预约付款'" width="min(460px, 92vw)" append-to-body :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
    <div class="payment-detail" v-loading="loading" aria-live="polite">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <template v-if="payment">
        <div class="payment-heading"><span>{{ payment.pay_method === 'balance' ? '储值余额' : '模拟支付宝' }}</span><strong>{{ money(payment.amount_cents) }}</strong><span>{{ status }}</span></div>
        <p v-if="payment.business_type === 'recharge' && payment.customer">到账客户：<strong>{{ payment.customer.nickname || payment.customer.username }}</strong>（账号 {{ payment.customer.username }}）<br />{{ payment.customer.contact_masked }}</p>
        <p v-if="payment.business_type === 'recharge' && payment.credit">本笔到账前余额 {{ money(payment.credit.balance_before_cents) }}，到账后 {{ money(payment.credit.balance_after_cents) }}。经办：{{ payment.credit.operator_username }}。</p>
        <p v-if="payment.target">新场次：{{ payment.target.court_name }} · {{ payment.target.reserve_date }} {{ payment.target.start_time }}–{{ payment.target.end_time }}</p>
        <p v-if="payment.purpose === 'reschedule' && payment.status === 'pending'">原预约仍有效。补差付款成功后才改期，付款时会再次检查目标场地。</p>
        <p v-if="payment.pay_method === 'mock_alipay'" class="muted-text">项目内模拟支付，无需真实转账。</p>
        <p v-if="payment.status === 'pending'">{{ countdownText(payment.expires_at, now) }}</p>
        <p v-if="payment.refunded_cents">已沿原渠道退款 {{ money(payment.refunded_cents) }}</p>
        <p v-if="payment.business_type === 'shop' && payment.status === 'succeeded'">付款成功，请到前台出示<RouterLink to="/shop/orders" @click="visible = false">订单取货码</RouterLink>领取商品。</p>
        <p class="payment-number">支付单 {{ payment.payment_no }}</p>
        <p v-if="notice" role="status">{{ notice }}</p>
      </template>
    </div>
    <template #footer>
      <div class="payment-actions">
        <el-button :disabled="busy || loading" @click="query">查询状态</el-button>
        <template v-if="pending">
          <el-button v-if="payment?.purpose === 'reschedule'" :disabled="busy || loading" @click="submit('cancel')">取消补差</el-button>
          <el-button v-if="payment?.pay_method === 'mock_alipay'" :disabled="busy || loading" @click="submit('mock-fail')">模拟失败</el-button>
          <el-button type="primary" :loading="busy" :disabled="loading" @click="submit(payment?.pay_method === 'balance' ? 'balance-pay' : 'mock-confirm')">{{ payment?.pay_method === 'balance' ? '确认余额付款' : '模拟付款成功' }}</el-button>
        </template>
        <el-button v-else :disabled="busy" @click="visible = false">关闭</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.payment-detail { min-height: 120px; line-height: 1.7; }
.payment-heading { display: grid; justify-items: center; gap: 6px; padding: 18px 0; }
.payment-heading strong { font-size: 34px; color: #244b38; font-variant-numeric: tabular-nums; }
.payment-number { font-size: 12px; color: #727970; overflow-wrap: anywhere; }
.payment-actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 10px; }
.payment-actions :deep(.el-button) { margin-left: 0; }
</style>
