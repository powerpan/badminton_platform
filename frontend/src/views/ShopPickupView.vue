<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { getPickupCode, getShopOrder, type PickupCredential, type ShopOrder } from '../api/shop';
import MobileHandoffDialog from '../components/MobileHandoffDialog.vue';
import { useAuthStore } from '../stores/auth';
import { formatDeadline } from '../utils/booking';
const route = useRoute(), router = useRouter(), auth = useAuthStore();
const order = ref<ShopOrder>(), credential = ref<PickupCredential>(), loading = ref(false), error = ref(''), handoffVisible = ref(false);
const labels = { ready: '已付款，待到馆取货', frozen: '退款审核中，暂不可取货', redeemed: '商品已领取', invalid: '取货码已失效' };
let version = 0, lastAutoOrder = 0;
async function load() {
  const id = Number(route.params.id), current = ++version; loading.value = true; error.value = '';
  try {
    if (!Number.isSafeInteger(id) || id <= 0) throw new Error('订单编号无效');
    const [detail, code] = await Promise.all([getShopOrder(id), getPickupCode(id)]);
    if (current !== version) return;
    order.value = detail.data; credential.value = code.data;
    if (code.data.status !== 'ready') handoffVisible.value = false;
    if (route.query.handoff === '1' && lastAutoOrder !== id && code.data.status === 'ready') {
      lastAutoOrder = id;
      handoffVisible.value = auth.user?.role === 'user' && !window.matchMedia('(max-width: 768px)').matches;
      await router.replace({ path: route.path });
    }
  } catch (e) { if (current === version) { credential.value = undefined; handoffVisible.value = false; error.value = e instanceof Error ? e.message : '取货凭证加载失败'; } }
  finally { if (current === version) loading.value = false; }
}
watch(() => route.params.id, () => { order.value = undefined; credential.value = undefined; handoffVisible.value = false; void load(); }, { immediate: true });
const timer = setInterval(() => { if (!document.hidden && !loading.value) void load(); }, 15000);
onUnmounted(() => { version++; clearInterval(timer); });
</script>
<template>
  <section class="pickup-page" v-loading="loading">
    <header><p>BF · 到馆自提</p><h1>商品取货凭证</h1></header>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <article v-if="credential && order" class="pickup-card" aria-live="polite">
      <h2>{{ labels[credential.status] }}</h2>
      <template v-if="credential.code">
        <img :src="credential.qr_data_url || ''" alt="商品取货二维码，供前台查单" width="240" height="240" />
        <strong class="pickup-number">{{ credential.code.match(/.{1,4}/g)?.join(' ') }}</strong>
        <p>请截图保存，到馆后向前台出示。<br />前台核对全部商品后确认领取。</p>
      </template>
      <p v-if="credential.redeemed_at">领取时间 {{ formatDeadline(credential.redeemed_at) }}</p>
      <ul><li v-for="item in order.items" :key="item.id"><span>{{ item.product_name_snapshot }}</span><b>× {{ item.quantity }}</b></li></ul>
      <p class="order-number">订单 {{ order.order_no }}</p>
      <small>是否可领取以柜台查询结果为准。退款审核期间暂停取货，同一订单只可领取一次。</small>
    </article>
    <div class="pickup-actions">
      <el-button v-if="credential?.status === 'ready' && auth.user?.role === 'user'" class="phone-view-action" type="primary" @click="handoffVisible = true">在手机查看</el-button>
      <el-button :loading="loading" @click="load">刷新取货状态</el-button><el-button @click="router.push('/shop/orders')">返回我的订单</el-button>
    </div>
    <MobileHandoffDialog v-if="order" v-model="handoffVisible" :order-id="order.id" />
  </section>
</template>
<style scoped>
.pickup-page { max-width: 480px; margin: 24px auto; }.pickup-page header { margin-bottom: 22px; }.pickup-page header p { color: #69776d; font-size: 13px; }.pickup-page h1 { font-size: 28px; }.pickup-card { background: white; border: 1px solid #dce5df; border-radius: 8px; padding: 24px; text-align: center; line-height: 1.8; }
.pickup-card h2 { font-size: 20px; margin: 0 0 16px; }.pickup-card img { display: block; margin: auto; max-width: 100%; height: auto; }.pickup-number { display: block; font-size: 23px; letter-spacing: 2px; color: #155b43; font-variant-numeric: tabular-nums; }.pickup-card ul { list-style: none; padding: 0; border-top: 1px solid #e1e7e2; }.pickup-card li { display: flex; justify-content: space-between; gap: 16px; padding: 8px 0; text-align: left; }.pickup-card small,.order-number { color: #6c766d; font-size: 12px; overflow-wrap: anywhere; }
.pickup-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 20px; }.pickup-actions :deep(.el-button) { margin-left: 0; }
@media(max-width:768px) { .pickup-page { margin: 12px auto; }.pickup-card { padding: 20px 16px; }.phone-view-action { display: none; } }
</style>
