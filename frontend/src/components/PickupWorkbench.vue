<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue';
import { lookupPickup, redeemPickup, type PickupLookup } from '../api/shop';
import { formatDeadline } from '../utils/booking';
import { useAuthStore } from '../stores/auth';
import { confirmAction, formatMoney } from '../views/admin/shared';
const auth = useAuthStore();
const code = ref(''), order = ref<PickupLookup>(), error = ref(''), notice = ref(''), loading = ref(false), busy = ref(false);
let version = 0;
const labels = { ready: '待取货', frozen: '退款审核中，禁止交付', redeemed: '已取货', invalid: '已退款，凭证失效' };
watch(code, () => { version++; loading.value = false; order.value = undefined; error.value = ''; notice.value = ''; });
async function query() {
  if (busy.value) return;
  const current = ++version; loading.value = true; error.value = ''; notice.value = ''; order.value = undefined;
  try { const response = await lookupPickup(code.value); if (current === version) order.value = response.data; }
  catch (e) { if (current === version) error.value = e instanceof Error ? e.message : '查单失败'; }
  finally { if (current === version) loading.value = false; }
}
async function redeem() {
  if (!order.value?.can_redeem || busy.value) return;
  busy.value = true; error.value = ''; notice.value = '';
  const currentOrder = order.value, currentCode = code.value;
  const storageKey = `bf-pickup:${auth.user?.id}:${currentOrder.id}`;
  try {
    if (!await confirmAction(`确认已核对订单 ${currentOrder.order_no} 的全部商品，并交付给客户？同一订单只可领取一次。`)) return;
    const key = sessionStorage.getItem(storageKey) || crypto.randomUUID(); sessionStorage.setItem(storageKey, key);
    await redeemPickup(currentCode, key);
    const response = await lookupPickup(currentCode); order.value = response.data;
    sessionStorage.removeItem(storageKey);
    notice.value = '整单商品已核销，请勿重复交付。';
  } catch (e) {
    error.value = e instanceof Error ? e.message : '提交结果未确认';
    try {
      order.value = (await lookupPickup(currentCode)).data;
      if (order.value.pickup_status === 'redeemed') { error.value = ''; notice.value = '查询确认该单已核销，请勿重复交付。'; }
    } catch { order.value = undefined; error.value += '。请重新查询取货码确认结果。'; }
  } finally { busy.value = false; }
}
onUnmounted(() => { version++; });
</script>
<template>
  <section class="pickup-workbench">
    <h2>商品取货</h2><p class="muted-text">输入客户出示的取货码，核对整单商品后确认交付。</p>
    <el-form label-position="top" class="pickup-search" @submit.prevent="query">
      <el-form-item label="取货码"><el-input v-model="code" :disabled="busy" placeholder="12 位取货码或二维码内容" maxlength="64" clearable /></el-form-item>
      <el-button type="primary" native-type="submit" :disabled="busy || !code.trim()" :loading="loading">查询取货单</el-button>
    </el-form>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="notice" :title="notice" type="success" :closable="false" />
    <section v-if="order" class="pickup-result" aria-live="polite">
      <h3>{{ labels[order.pickup_status] }}</h3><p class="pickup-order-number">{{ order.order_no }}</p>
      <ul><li v-for="(item, index) in order.items" :key="index"><span>{{ item.product_name_snapshot }}</span><b>× {{ item.quantity }}</b><span>{{ formatMoney(item.subtotal_cents) }}</span></li></ul>
      <p>订单金额 {{ formatMoney(order.total_amount_cents) }}</p>
      <p v-if="order.redeemed_at">已由 {{ order.redeemed_by_name }} 于 {{ formatDeadline(order.redeemed_at) }} 确认取货</p>
      <el-button v-if="order.can_redeem" type="primary" :loading="busy" :disabled="loading" @click="redeem">确认整单交付</el-button>
    </section>
  </section>
</template>
<style scoped>
.pickup-workbench { max-width: 760px; padding-block: 20px; }
.pickup-search { display: flex; align-items: end; gap: 16px; margin: 24px 0; }
.pickup-search :deep(.el-form-item) { flex: 1; margin-bottom: 0; }
.pickup-result { margin-top: 24px; border-top: 1px solid #dce3dd; padding-top: 20px; }
.pickup-result ul { list-style: none; padding: 0; }.pickup-result li { display: grid; grid-template-columns: minmax(0,1fr) auto auto; gap: 20px; border-bottom: 1px solid #e2e7e1; padding: 16px 0; }
.pickup-order-number { overflow-wrap: anywhere; color: #6d786e; font-size: 13px; }
@media(max-width:540px) { .pickup-search { align-items: stretch; flex-direction: column; gap: 12px; }.pickup-result li { gap: 10px; } }
</style>
