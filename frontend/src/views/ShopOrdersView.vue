<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import ProductImage from '../components/ProductImage.vue';
import PaymentDialog from '../components/PaymentDialog.vue';
import PickupCodeDialog from '../components/PickupCodeDialog.vue';
import { getMyShopOrders, getShopOrder, cancelShopOrder, requestShopOrderRefund, type ShopOrder } from '../api/shop';
import { ApiRequestError } from '../api/http';
import { useAuthStore } from '../stores/auth';
import { countdownText, formatDeadline } from '../utils/booking';
import { formatMoney, payMethodText } from './admin/shared';

const auth = useAuthStore();
const orders = ref<ShopOrder[]>([]), selectedOrder = ref<ShopOrder | null>(null);
const detailVisible = ref(false), paymentVisible = ref(false), pickupVisible = ref(false);
const paymentId = ref<number | null>(null), pickupOrderId = ref<number | null>(null);
const filter = ref(''), page = ref({ page: 1, page_size: 10, total: 0 });
const loading = ref(false), busy = ref(false), errorMessage = ref(''), now = ref(Date.now());
const statuses: Record<string, string> = { pending: '待付款', paid: '待取货', refund_requested: '退款待审核', completed: '已取货', canceled: '已取消', expired: '已过期' };
let version = 0, detailVersion = 0, offset = 0, timer: ReturnType<typeof setInterval> | undefined;
function statusTagType(status: string) { return status === 'paid' || status === 'completed' ? 'success' : status === 'pending' || status === 'refund_requested' ? 'warning' : 'info'; }
function syncClock(server?: string) { if (server) { offset = new Date(server.replace(' ', 'T')).getTime() - Date.now(); now.value = Date.now() + offset; } }
async function loadOrders(reset = false, quiet = false) {
  if (reset) page.value.page = 1;
  const current = ++version; if (!quiet) loading.value = true;
  try {
    const response = await getMyShopOrders({ status: filter.value || undefined, page: page.value.page, page_size: page.value.page_size });
    if (current !== version) return;
    orders.value = response.data.items; page.value.total = response.data.total; syncClock(response.data.server_now); errorMessage.value = '';
  } catch (e) { if (current === version) errorMessage.value = e instanceof Error ? e.message : '订单加载失败'; }
  finally { if (current === version) loading.value = false; }
}
async function openDetail(order: ShopOrder) {
  const current = ++detailVersion;
  try { const response = await getShopOrder(order.id); if (current !== detailVersion) return; selectedOrder.value = response.data; syncClock(response.data.server_now); detailVisible.value = true; }
  catch (e) { ElMessage.error(e instanceof Error ? e.message : '订单详情加载失败'); }
}
async function refreshDetails(quiet = false) {
  await loadOrders(false, quiet);
  const id = selectedOrder.value?.id;
  if (detailVisible.value && id) {
    const current = ++detailVersion;
    try {
      const response = await getShopOrder(id);
      if (current === detailVersion && detailVisible.value && selectedOrder.value?.id === id) selectedOrder.value = response.data;
    } catch (e) { if (!quiet) ElMessage.error(e instanceof Error ? e.message : '详情刷新失败'); }
  }
}
async function pay(order: ShopOrder) {
  if (busy.value) return; busy.value = true;
  try {
    const latest = (await getShopOrder(order.id)).data;
    if (latest.status !== 'pending' || !latest.payment_id) { await refreshDetails(); ElMessage.info('订单状态已更新，请核对'); return; }
    paymentId.value = latest.payment_id; detailVisible.value = false; paymentVisible.value = true;
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '付款状态查询失败'); }
  finally { busy.value = false; }
}
function pickup(order: ShopOrder) { pickupOrderId.value = order.id; detailVisible.value = false; pickupVisible.value = true; }
async function paymentUpdated() { await Promise.allSettled([refreshDetails(), auth.fetchProfile()]); }
async function changeOrder(order: ShopOrder, action: 'cancel' | 'refund') {
  if (busy.value) return; busy.value = true;
  const storageKey = `bf-shop-action:${auth.user?.id}:${order.id}:${action}`;
  try {
    const saved = sessionStorage.getItem(storageKey);
    let command: { request_key: string; reason: string } | null = saved ? JSON.parse(saved) : null;
    if (!command) {
      let reason = '用户申请商城订单退款';
      try {
        if (action === 'cancel') await ElMessageBox.confirm('确认取消待付款订单并释放商品？本订单尚未收款。', '取消订单', { confirmButtonText: '确认取消', cancelButtonText: '保留订单' });
        else {
          const result = await ElMessageBox.prompt(`填写订单 ${order.order_no} 的退款原因。审核期间取货码暂停使用，通过后沿原支付渠道退款。`, '申请退款', { confirmButtonText: '提交申请', cancelButtonText: '返回', inputValue: reason, inputPattern: /^.{1,255}$/, inputErrorMessage: '请输入 1–255 字的退款原因' });
          reason = String(result.value || reason).trim();
        }
      } catch { return; }
      command = { request_key: crypto.randomUUID(), reason }; sessionStorage.setItem(storageKey, JSON.stringify(command));
    }
    if (action === 'cancel') await cancelShopOrder(order.id, command.request_key);
    else await requestShopOrderRefund(order.id, command);
    sessionStorage.removeItem(storageKey);
    ElMessage.success(action === 'cancel' ? '订单已取消' : '退款申请已提交，取货码暂停使用');
    await refreshDetails();
  } catch (e) {
    if (e instanceof ApiRequestError && e.status && e.status >= 400 && e.status < 500) sessionStorage.removeItem(storageKey);
    ElMessage.error(e instanceof Error ? e.message : '结果尚未确认，请刷新查看或重试原请求');
    await refreshDetails();
  } finally { busy.value = false; }
}
async function changePage(value: number) { page.value.page = value; await loadOrders(); }
watch(detailVisible, value => { if (!value) detailVersion++; });
function refreshOnFocus() { if (!document.hidden && !busy.value && !loading.value) void refreshDetails(true); }
onMounted(() => {
  void loadOrders(); let ticks = 0;
  timer = setInterval(() => { now.value = Date.now() + offset; if (++ticks % 15 === 0) refreshOnFocus(); }, 1000);
  document.addEventListener('visibilitychange', refreshOnFocus);
});
onUnmounted(() => { version++; detailVersion++; clearInterval(timer); document.removeEventListener('visibilitychange', refreshOnFocus); });
</script>

<template>
  <section class="page-header"><h1>我的商城订单</h1><p>付款后到店出示取货码，由前台核对商品并确认领取。</p></section>
  <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />
  <el-card shadow="never" class="panel-card list-page-card" v-loading="loading">
    <div class="list-toolbar shop-order-toolbar">
      <el-select v-model="filter" aria-label="订单状态" placeholder="全部订单" style="width: 160px" clearable @change="loadOrders(true)">
        <el-option label="全部订单" value="" /><el-option v-for="(label, key) in statuses" :key="key" :label="label" :value="key" />
      </el-select>
      <el-button :disabled="busy" @click="refreshDetails()">刷新状态</el-button><RouterLink class="inline-action" to="/shop">继续购物</RouterLink>
    </div>
    <el-empty v-if="!orders.length && !loading" description="暂无商城订单" />
    <div v-else class="order-list">
      <article v-for="order in orders" :key="order.id" class="order-item shop-order-item">
        <div class="order-main"><strong>{{ order.order_no }}</strong><span>{{ formatDeadline(order.created_at) }}</span><span>{{ payMethodText(order.pay_method) }}</span></div>
        <div class="shop-order-state"><el-tag :type="statusTagType(order.status)" effect="plain">{{ statuses[order.status] }}</el-tag><b>{{ formatMoney(order.total_amount_cents) }}</b><small v-if="order.status === 'pending'">付款剩余 {{ countdownText(order.expires_at, now) }}</small></div>
        <div class="order-actions">
          <el-button link type="primary" :disabled="busy" @click="openDetail(order)">详情</el-button>
          <template v-if="order.status === 'pending'"><el-button type="primary" :disabled="busy" @click="pay(order)">去付款</el-button><el-button link :disabled="busy" @click="changeOrder(order, 'cancel')">取消订单</el-button></template>
          <template v-if="order.status === 'paid'"><el-button type="primary" :disabled="busy" @click="pickup(order)">取货码</el-button><el-button link type="warning" :disabled="busy" @click="changeOrder(order, 'refund')">申请退款</el-button></template>
          <el-button v-else-if="order.pickup_status" link :disabled="busy" @click="pickup(order)">取货状态</el-button>
        </div>
      </article>
    </div>
    <el-pagination class="element-pagination" :current-page="page.page" :page-size="page.page_size" :total="page.total" layout="prev, pager, next, total" @current-change="changePage" />
  </el-card>
  <el-dialog v-model="detailVisible" title="订单详情" width="min(680px, 92vw)" class="detail-dialog">
    <div v-if="selectedOrder" class="order-detail">
      <el-descriptions :column="1" border class="compact-descriptions">
        <el-descriptions-item label="订单号">{{ selectedOrder.order_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ statuses[selectedOrder.status] }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ formatMoney(selectedOrder.total_amount_cents) }}</el-descriptions-item>
        <el-descriptions-item label="支付方式">{{ payMethodText(selectedOrder.pay_method) }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedOrder.status === 'pending'" label="付款截止">{{ selectedOrder.expires_at }}</el-descriptions-item>
        <el-descriptions-item label="支付时间">{{ selectedOrder.paid_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="取货时间">{{ selectedOrder.redeemed_at || selectedOrder.completed_at || '-' }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedOrder.redeemed_by_name" label="核销人员">{{ selectedOrder.redeemed_by_name }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedOrder.canceled_at" label="取消时间">{{ selectedOrder.canceled_at }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedOrder.cancel_reason" label="取消原因">{{ selectedOrder.cancel_reason }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedOrder.refund_requested_at" label="退款申请">{{ selectedOrder.refund_requested_at }} · {{ selectedOrder.refund_request_reason }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedOrder.refund_reviewed_at" label="退款审核">{{ selectedOrder.refund_reviewed_at }}</el-descriptions-item>
        <el-descriptions-item v-if="selectedOrder.refund_reject_reason" label="驳回原因">{{ selectedOrder.refund_reject_reason }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ selectedOrder.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
      <div class="cart-list"><article v-for="item in selectedOrder.items || []" :key="item.id" class="cart-item"><ProductImage :name="item.product_name_snapshot" :src="item.image_url_snapshot" /><div><strong>{{ item.product_name_snapshot }}</strong><span>{{ formatMoney(item.price_cents) }} × {{ item.quantity }}</span></div><b>{{ formatMoney(item.subtotal_cents) }}</b></article></div>
      <div class="dialog-actions">
        <el-button @click="detailVisible = false">关闭</el-button>
        <template v-if="selectedOrder.status === 'pending'"><el-button :disabled="busy" @click="changeOrder(selectedOrder, 'cancel')">取消订单</el-button><el-button type="primary" :disabled="busy" @click="pay(selectedOrder)">去付款</el-button></template>
        <template v-if="selectedOrder.status === 'paid'"><el-button type="primary" :disabled="busy" @click="pickup(selectedOrder)">出示取货码</el-button><el-button type="warning" :disabled="busy" @click="changeOrder(selectedOrder, 'refund')">申请退款</el-button></template>
      </div>
    </div>
  </el-dialog>
  <PaymentDialog v-model="paymentVisible" :payment-id="paymentId" @paid="paymentUpdated" @updated="refreshDetails()" />
  <PickupCodeDialog v-model="pickupVisible" :order-id="pickupOrderId" @update:model-value="value => { if (!value) void refreshDetails(); }" />
</template>
<style scoped>
.shop-order-toolbar { flex-wrap: wrap; gap: 12px; }
.shop-order-state { display: flex; flex-direction: column; align-items: start; gap: 8px; }
.shop-order-item .order-main strong { overflow-wrap: anywhere; }
.shop-order-item .order-actions { flex-wrap: wrap; gap: 10px; }
.shop-order-item .order-actions :deep(.el-button) { margin-left: 0; }
.dialog-actions { flex-wrap: wrap; gap: 8px; }
@media (max-width: 600px) { .shop-order-item { grid-template-columns: minmax(0,1fr); }.shop-order-item .order-actions { justify-content: flex-start; } }
</style>
