<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import WalkInForm from '../components/WalkInForm.vue';
import RechargeWorkbench from '../components/RechargeWorkbench.vue';
import PickupWorkbench from '../components/PickupWorkbench.vue';
import type { CourtSlots, ReservationRules, SlotItem } from '../api/court';
import { getStaffSchedule, getWalkIns, getWalkIn, createWalkIn, cancelWalkIn, mockCollect, type WalkIn, type WalkInDraft } from '../api/staff';
import { ApiRequestError } from '../api/http';
import { useAuthStore } from '../stores/auth';
import { addDays, confirmAction, formatMoney } from './admin/shared';

const auth = useAuthStore();
const day = ref(addDays(0)), items = ref<CourtSlots[]>([]), orders = ref<WalkIn[]>([]), rules = ref<ReservationRules>();
const loading = ref(false), busy = ref(false), error = ref(''), total = ref(0), page = ref(1), status = ref(''), orderNo = ref('');
const view = ref('schedule'), selected = ref<WalkIn>(), detailVisible = ref(false);
const collectionNotice = ref('');
const selection = ref<{ court: CourtSlots; start: string; parent?: WalkIn }>();
const pendingRecovery = ref(false), storageKey = `bf_walkin_attempt_${auth.user?.id}`;
const labels = { available: '空闲', reserved: '已占用', locked: '处理中', disabled: '不可用', maintenance: '维护 / 包场' };
const paymentLabel = { pending: '待收款', succeeded: '已收款', canceled: '已撤销', expired: '已超时', refunded: '已退款' };
let latestRequest = 0, offset = 0, tick: ReturnType<typeof setInterval>;
const clock = ref(Date.now());
const timeAt = (date: string, time: string) => Date.parse(`${date}T${time.slice(0,5)}:00+08:00`);
const secondsLeft = computed(() => selected.value ? Math.max(0,Math.ceil((Date.parse(selected.value.payment.expires_at)-clock.value)/1000)) : 0);
const currentSlot = (slot: SlotItem) => slot.status==='available' && timeAt(day.value,slot.start_time)<=clock.value && clock.value<timeAt(day.value,slot.end_time);

async function load() {
  const request = ++latestRequest;
  error.value = ''; loading.value = true;
  try {
    const [schedule,list] = await Promise.all([getStaffSchedule(day.value),getWalkIns({date:day.value,status:status.value||undefined,order_no:orderNo.value||undefined,page:page.value,page_size:10})]);
    if (request !== latestRequest) return;
    items.value = schedule.data.items; rules.value = schedule.data.rules; offset = Date.parse(schedule.data.server_now)-Date.now(); clock.value = Date.now()+offset;
    orders.value = list.data.items; total.value = list.data.total;
  } catch (e) { if (request !== latestRequest) return; items.value = []; orders.value = []; error.value = e instanceof Error ? e.message : '工作区加载失败'; }
  finally { if (request === latestRequest) loading.value = false; }
}
function filter() { page.value = 1; void load(); }
function select(court: CourtSlots, slot: SlotItem) {
  if (!currentSlot(slot) || busy.value || pendingRecovery.value) return;
  selection.value = { court, start: slot.start_time };
}
async function detail(id: number) {
  busy.value = true;
  try { selected.value = (await getWalkIn(id)).data; collectionNotice.value = ''; detailVisible.value = true; }
  catch (e) { ElMessage.error(e instanceof Error ? e.message : '订单查询失败'); }
  finally { busy.value = false; }
}
async function created(order: WalkIn) {
  selection.value = undefined; selected.value = order; collectionNotice.value = ''; detailVisible.value = true; view.value = 'orders'; pendingRecovery.value = false; await load();
}
function closeForm() { selection.value = undefined; pendingRecovery.value = Boolean(sessionStorage.getItem(storageKey)); }
async function recover() {
  const raw = sessionStorage.getItem(storageKey);
  if (!raw || busy.value) return;
  busy.value = true;
  try {
    const previous = JSON.parse(raw) as { body: WalkInDraft; parent?: number };
    const result = (await createWalkIn(previous.body,previous.parent)).data;
    sessionStorage.removeItem(storageKey); await created(result);
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '原请求仍待确认，请稍后重试');
    if (e instanceof ApiRequestError && e.status && e.status < 500 && e.status !== 401) { sessionStorage.removeItem(storageKey); pendingRecovery.value = false; }
  } finally { busy.value = false; }
}
async function collect(action: 'confirm' | 'fail' | 'cancel') {
  const order = selected.value;
  if (!order || busy.value) return;
  if (action === 'confirm' && !await confirmAction(`模拟收取 ${formatMoney(order.payment.amount_cents)}，确认 ${order.court_name} ${order.start_time}–${order.end_time}？`, '模拟支付宝收款')) return;
  if (action === 'cancel' && !await confirmAction('撤销此未付款订场并释放场地占用？')) return;
  busy.value = true; collectionNotice.value = '';
  try {
    const current = (await getWalkIn(order.id)).data;
    selected.value = current;
    if (current.payment.status !== 'pending') { ElMessage.info('订单状态已更新，请查看收款结果'); return; }
    if (current.payment.amount_cents !== order.payment.amount_cents) { ElMessage.warning('金额已变化，请重新确认'); return; }
    const key = crypto.randomUUID();
    selected.value = action==='cancel' ? (await cancelWalkIn(order.id,key)).data : (await mockCollect(order.payment.id,action,key)).data;
    ElMessage.success(action==='confirm' ? '模拟收款完成，场地已确认' : action==='cancel' ? '已撤销并释放场地' : '已记录模拟失败，仍可在截止前重试');
  } catch (e) {
    try {
      const current = (await getWalkIn(order.id)).data;
      selected.value = current;
      if (current.payment.status === 'succeeded') {
        ElMessage.success('已核实收款成功，请勿重复收款');
      } else if (current.payment.status !== 'pending') {
        ElMessage.info(`已核实订单状态：${paymentLabel[current.payment.status]}`);
      } else {
        collectionNotice.value = `${e instanceof Error ? e.message : '操作响应未确认'}。查询显示原单仍待收款，请刷新收款结果后重试。`;
      }
    } catch {
      collectionNotice.value = '暂时无法确认收款结果，请刷新原工作单核实，勿重新开场收款。';
    }
  } finally { busy.value = false; await load(); }
}
async function extend() {
  if (!selected.value) return;
  busy.value = true;
  try {
    const parent = (await getWalkIn(selected.value.id)).data;
    const schedule = (await getStaffSchedule(parent.reserve_date)).data;
    const court = schedule.items.find(c => c.court_id===parent.court_id);
    if (!court || parent.status!=='confirmed' || timeAt(parent.reserve_date,parent.end_time)<=Date.parse(schedule.server_now)) { ElMessage.warning('原场次已结束或不可续场'); return; }
    rules.value = schedule.rules; detailVisible.value = false;
    selection.value = { court, start: parent.end_time, parent };
  } catch (e) { ElMessage.error(e instanceof Error ? e.message : '续场排期查询失败'); }
  finally { busy.value = false; }
}
onMounted(() => { pendingRecovery.value = Boolean(sessionStorage.getItem(storageKey)); void load(); tick = setInterval(() => { clock.value=Date.now()+offset; },1000); });
onUnmounted(() => { clearInterval(tick); latestRequest++; });
</script>
<template>
  <section class="staff-workspace">
    <header class="staff-heading"><div><p class="staff-eyebrow">BF · 到店服务</p><h1>前台工作台</h1><p>办理到店开场、收款续场、会员储值和商品取货。</p></div><el-button v-if="['schedule','orders'].includes(view)" :loading="loading" @click="load">刷新工作区</el-button></header>
    <el-alert v-if="pendingRecovery" title="有一笔创建请求的结果待确认，请先恢复原请求。" type="warning" :closable="false"><el-button :loading="busy" @click="recover">恢复待确认请求</el-button></el-alert>
    <el-form v-if="['schedule','orders'].includes(view)" class="staff-filters" label-position="top" @submit.prevent="filter"><el-form-item label="日期"><el-date-picker v-model="day" value-format="YYYY-MM-DD" :clearable="false" @change="filter" /></el-form-item><el-button native-type="submit">查询</el-button></el-form>
    <el-tabs v-model="view"><el-tab-pane label="场地排期" name="schedule" /><el-tab-pane label="散客工作单" name="orders" /><el-tab-pane label="商品取货" name="pickup" /><el-tab-pane label="会员储值" name="recharge" /></el-tabs>
    <el-alert v-if="error && ['schedule','orders'].includes(view)" :title="error" type="error" :closable="false" show-icon />
    <PickupWorkbench v-if="view==='pickup'" /><RechargeWorkbench v-if="view==='recharge'" />
    <div v-if="view==='schedule'" v-loading="loading">
      <p class="staff-result-count">仅当前所在的空闲时段可直接开场；后续连续时段在开场表单中选择。</p>
      <section v-for="item in items" :key="item.court_id" class="desk-court"><h2>{{ item.court.court_name }} <small>{{ item.court.court_no }} · {{ formatMoney(item.court.price_per_hour_cents) }} / 小时</small></h2>
        <ul class="desk-slots"><li v-for="slot in item.slots" :key="slot.start_time" :class="slot.status"><span>{{ slot.start_time }}–{{ slot.end_time }}</span><strong>{{ labels[slot.status] }}</strong><small v-if="slot.unavailable_reason">{{ slot.unavailable_reason }}</small><el-button v-if="currentSlot(slot)" size="small" :disabled="busy || pendingRecovery" @click="select(item,slot)">开场收款</el-button></li></ul>
      </section>
      <el-empty v-if="!items.length && !loading && !error" description="暂无场地" />
    </div>
    <div v-else-if="view==='orders'" v-loading="loading">
      <el-form class="staff-filters" label-position="top" @submit.prevent="filter"><el-form-item label="收款 / 使用状态"><el-select v-model="status" clearable @change="filter"><el-option label="待收款" value="pending" /><el-option label="已确认" value="confirmed" /><el-option label="已结束" value="completed" /><el-option label="已取消" value="canceled" /><el-option label="已超时" value="expired" /></el-select></el-form-item><el-form-item label="完整单号"><el-input v-model="orderNo" placeholder="订场、订单或支付单号" clearable maxlength="64" /></el-form-item><el-button native-type="submit">查询工作单</el-button></el-form>
      <p class="staff-result-count">{{ day }} · 共 {{ total }} 笔散客订场</p>
      <article v-for="order in orders" :key="order.id" class="walkin-row"><div><strong>{{ order.court_name }} · {{ order.start_time }}–{{ order.end_time }}</strong><p>{{ order.guest_name || '散客' }} · {{ order.source==='walk_in_extension' ? '续场' : '到店开场' }} · 经办 {{ order.operator_name_snapshot }}</p><small>{{ order.reservation_no }}</small></div><div class="walkin-row-end"><strong>{{ formatMoney(order.payment.amount_cents) }}</strong><span>{{ paymentLabel[order.payment.status] }}</span><el-button :disabled="busy" @click="detail(order.id)">{{ order.payment.status==='pending' ? '继续收款' : '查看工作单' }}</el-button></div></article>
      <el-empty v-if="!orders.length && !loading && !error" description="此条件下没有散客工作单" />
      <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="prev, pager, next" @current-change="load" />
    </div>
    <el-drawer :model-value="Boolean(selection)" :title="selection?.parent ? '续场' : '到店开场'" size="min(500px, 100vw)" :close-on-click-modal="false" @close="closeForm">
      <WalkInForm v-if="selection && rules" :key="`${selection.court.court_id}-${selection.start}-${selection.parent?.id}`" v-bind="selection" :rules="rules" @created="created" @close="closeForm" />
    </el-drawer>
    <el-drawer v-model="detailVisible" title="散客工作单" size="min(520px, 100vw)" :close-on-click-modal="false">
      <template v-if="selected"><el-alert v-if="collectionNotice" :title="collectionNotice" type="warning" :closable="false" show-icon /><p class="desk-detail-title">{{ selected.court_name }} · {{ selected.start_time }}–{{ selected.end_time }}</p><p>{{ selected.reserve_date }} · {{ selected.guest_name || '散客' }}</p><p class="desk-payment-status">{{ paymentLabel[selected.payment.status] }} <span v-if="selected.payment.status==='pending'">· 剩余 {{ Math.floor(secondsLeft/60) }} 分 {{ secondsLeft%60 }} 秒</span></p>
        <div class="desk-amount"><span>模拟支付宝 · {{ selected.source==='walk_in_extension' ? '续场' : '整段原价' }}</span><strong>{{ formatMoney(selected.payment.amount_cents) }}</strong></div>
        <dl class="desk-detail-list"><dt>订场号</dt><dd>{{ selected.reservation_no }}</dd><dt>收款单号</dt><dd>{{ selected.payment.payment_no }}</dd><dt>经办人</dt><dd>{{ selected.operator_name_snapshot }}</dd><dt v-if="selected.guest_contact">联系方式</dt><dd v-if="selected.guest_contact">{{ selected.guest_contact }}</dd><dt v-if="selected.parent_reservation_id">原订场</dt><dd v-if="selected.parent_reservation_id"><el-button link @click="detail(selected.parent_reservation_id)">#{{ selected.parent_reservation_id }}</el-button></dd></dl>
        <p class="desk-note">项目内模拟收款。成功后确认场地，不扣前台或客户的储值余额。</p>
        <div v-if="selected.payment.status==='pending'" class="desk-actions"><el-button type="primary" :disabled="secondsLeft===0" :loading="busy" @click="collect('confirm')">模拟付款成功</el-button><el-button :disabled="busy || secondsLeft===0" @click="collect('fail')">模拟付款失败</el-button><el-button :disabled="busy" @click="collect('cancel')">撤销未付款单</el-button></div>
        <p v-if="selected.payment.status==='pending' && secondsLeft===0" class="desk-note">收款截止时间已到，请刷新确认释放结果。</p>
        <div class="desk-actions"><el-button :loading="busy" @click="detail(selected.id)">刷新收款结果</el-button><el-button v-if="selected.status==='confirmed' && selected.payment.status==='succeeded'" :disabled="busy || pendingRecovery" @click="extend">续场</el-button></div>
        <p v-if="selected.payment.status==='succeeded'" class="desk-note">已付款订单如需退款，由场地管理员处理。提前离场不自动退款。</p>
        <div v-if="selected.chain && selected.chain.length>1"><h3>关联场次</h3><p v-for="entry in selected.chain" :key="entry.id"><el-button link :disabled="busy" @click="detail(entry.id)">#{{ entry.id }} · {{ entry.start_time.slice(0,5) }}–{{ entry.end_time.slice(0,5) }}</el-button></p></div>
      </template>
    </el-drawer>
  </section>
</template>
<style scoped>
.desk-court { padding-block: 20px; border-bottom: 1px solid #dce3dd; }
.desk-court h2 { font-size: 20px; }
.desk-court h2 small { font-size: 13px; color: #6b776f; font-weight: normal; margin-left: 12px; }
.desk-slots { display: grid; grid-template-columns: repeat(auto-fill,minmax(140px,1fr)); list-style: none; padding: 0; gap: 8px; }
.desk-slots li { padding: 12px; background: #edf0ec; display: grid; align-content: start; gap: 8px; font-size: 12px; color: #757d75; border-radius: 3px; overflow-wrap: anywhere; }
.desk-slots li.available { color: #276044; background: #e7f0e6; }
.desk-slots li.reserved, .desk-slots li.locked { color: #855527; background: #f4ebde; }
.desk-slots li.maintenance { color: #744b48; background: #f3e6e3; }
.walkin-row { display: flex; justify-content: space-between; gap: 18px; padding: 22px 0; border-bottom: 1px solid #dce3dd; overflow-wrap: anywhere; }
.walkin-row p, .walkin-row small { color: #697469; font-size: 13px; }
.walkin-row-end { display: grid; gap: 10px; justify-items: end; flex-shrink: 0; }
.walkin-row-end span { font-size: 13px; color: #526b56; }
.desk-detail-title { font-size: 21px; font-weight: 600; }
.desk-payment-status { color: #386444; }.desk-payment-status span { font-size: 13px; }
.desk-amount { display: grid; gap: 12px; padding: 22px 0; border-block: 1px solid #dce3dd; margin: 24px 0; }
.desk-amount strong { font-size: 36px; color: #246044; font-variant-numeric: tabular-nums; }
.desk-detail-list { display: grid; grid-template-columns: 80px minmax(0,1fr); gap: 15px 12px; font-size: 13px; line-height: 1.6; }
.desk-detail-list dt { color: #768077; }.desk-detail-list dd { margin: 0; overflow-wrap: anywhere; }
.desk-note { color: #68766c; font-size: 13px; line-height: 1.8; }
.desk-actions { display: flex; gap: 10px; flex-wrap: wrap; margin-block: 22px; }.desk-actions .el-button { margin-left: 0; }
@media(max-width:600px) { .walkin-row { flex-direction: column; }.walkin-row-end { display: flex; align-items: center; flex-wrap: wrap; }.walkin-row-end .el-button { margin-left: auto; }.desk-court h2 small { display: block; margin: 8px 0 0; } }
</style>
