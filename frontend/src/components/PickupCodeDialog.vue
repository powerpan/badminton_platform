<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue';
import { formatDeadline } from '../utils/booking';
import { getPickupCode, type PickupCredential } from '../api/shop';
const visible = defineModel<boolean>({ default: false });
const props = defineProps<{ orderId: number | null }>();
const credential = ref<PickupCredential>(), loading = ref(false), error = ref('');
let version = 0, timer: ReturnType<typeof setInterval> | undefined;
const labels = { ready: '请出示此码领取整单商品', frozen: '退款审核中，暂不可取货', redeemed: '商品已领取', invalid: '订单已退款，取货码已失效' };
async function load() {
  if (!props.orderId || !visible.value) return;
  const current = ++version; loading.value = true; error.value = '';
  try {
    const response = await getPickupCode(props.orderId);
    if (current === version && visible.value) credential.value = response.data;
  } catch (e) {
    if (current === version) { credential.value = undefined; error.value = e instanceof Error ? e.message : '取货码暂时无法查询'; }
  } finally { if (current === version) loading.value = false; }
}
watch(() => [visible.value, props.orderId] as const, ([open]) => {
  version++; credential.value = undefined; error.value = ''; clearInterval(timer);
  if (open) { void load(); timer = setInterval(() => { if (visible.value && !document.hidden && !loading.value) void load(); }, 15000); }
});
onUnmounted(() => { version++; clearInterval(timer); });
</script>
<template>
  <el-dialog v-model="visible" title="商品取货码" width="min(420px, 92vw)" append-to-body>
    <section class="pickup-code" v-loading="loading" aria-live="polite">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <template v-if="credential">
        <p>{{ labels[credential.status] }}</p>
        <img v-if="credential.qr_data_url" :src="credential.qr_data_url" alt="商城订单取货二维码" width="240" height="240" />
        <strong v-if="credential.code" class="pickup-code-text">{{ credential.code.match(/.{1,4}/g)?.join(' ') }}</strong>
        <p v-if="credential.code" class="muted-text">也可由前台输入上方 12 位取货码。核对商品后确认领取。</p>
        <small>{{ credential.order_no }}</small>
        <p v-if="credential.redeemed_at">领取时间 {{ formatDeadline(credential.redeemed_at) }}</p>
      </template>
    </section>
    <template #footer><el-button :loading="loading" @click="load">刷新取货状态</el-button><el-button @click="visible = false">关闭</el-button></template>
  </el-dialog>
</template>
<style scoped>
.pickup-code { display: grid; justify-items: center; gap: 8px; min-height: 100px; text-align: center; line-height: 1.7; }
.pickup-code img { max-width: 100%; height: auto; background: white; }
.pickup-code small { overflow-wrap: anywhere; max-width: 100%; color: #6c766d; }
.pickup-code-text { font-size: 21px; letter-spacing: 2px; font-variant-numeric: tabular-nums; }
</style>
