<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { findRechargeCustomers, createRecharge, getRecharge, getRecharges, cancelRecharge, type RechargeCustomer, type RechargeOrder, type RechargeDraft } from '../api/recharge';
import { ApiRequestError } from '../api/http';
import { useAuthStore } from '../stores/auth';
import { confirmAction, formatMoney } from '../views/admin/shared';
import { countdownText, formatDeadline } from '../utils/booking';
import PaymentDialog from './PaymentDialog.vue';
const props = withDefaults(defineProps<{ admin?: boolean }>(), { admin: false });
const auth = useAuthStore();
const query = ref(''), customers = ref<RechargeCustomer[]>([]), customer = ref<RechargeCustomer>();
const searched = ref(false), searching = ref(false), busy = ref(false), loading = ref(false), error = ref(''), searchError = ref('');
const amount = ref('100.00'), orders = ref<RechargeOrder[]>([]), selected = ref<RechargeOrder>();
const detailVisible = ref(false), paymentVisible = ref(false), paymentId = ref<number | null>(null);
const filters = ref({ date_from: '', date_to: '', status: '', order_no: '' }), page = ref(1), total = ref(0);
const now = ref(Date.now()); let offset = 0, listVersion = 0, searchVersion = 0, detailVersion = 0;
let timer: ReturnType<typeof setInterval> | undefined;
const recoveryKey = `bf-recharge-create:${auth.user?.id}`;
const recovery = ref<{ payload: RechargeDraft; customer: RechargeCustomer } | null>(null);
const labels = { pending: '待收款', paid: '已到账', canceled: '已撤销', expired: '已超时' };
const cents = computed(() => {
  const text = amount.value.trim(); if (!/^\d{1,8}(\.\d{1,2})?$/.test(text)) return null;
  const [whole, fraction = ''] = text.split('.'); const result = Number(whole) * 100 + Number(fraction.padEnd(2,'0'));
  return result > 0 && result <= 2147483647 ? result : null;
});
function forget() { recovery.value = null; sessionStorage.removeItem(recoveryKey); }
function syncClock(value?: string) { if (value) { offset = new Date(value).getTime() - Date.now(); now.value = Date.now()+offset; } }
watch(query, () => { searchVersion++; searching.value = false; searched.value = false; customers.value = []; customer.value = undefined; searchError.value = ''; });
watch(detailVisible, open => { if (!open) detailVersion++; });
async function search() {
  if (busy.value || recovery.value || !query.value.trim()) return;
  const version = ++searchVersion; searching.value = true; searchError.value = ''; customer.value = undefined;
  try { const response = await findRechargeCustomers(query.value.trim()); if (version === searchVersion) { customers.value = response.data.items; searched.value = true; } }
  catch(e) { if (version === searchVersion) searchError.value = e instanceof Error ? e.message : '客户查询失败'; }
  finally { if (version === searchVersion) searching.value = false; }
}
async function load(reset=false, quiet=false) {
  if (reset) page.value=1;
  const version = ++listVersion; if (!quiet) loading.value=true;
  try {
    const response=await getRecharges({...filters.value,page:page.value,page_size:10},props.admin);
    if(version!==listVersion)return;
    orders.value=response.data.items;total.value=response.data.total;syncClock(response.data.server_now);error.value='';
  } catch(e) { if(version===listVersion)error.value=e instanceof Error?e.message:'充值记录加载失败'; }
  finally { if(version===listVersion)loading.value=false; }
}
async function detail(order: RechargeOrder) {
  const version=++detailVersion;
  try { const response=await getRecharge(order.id,props.admin);if(version===detailVersion){selected.value=response.data;syncClock(response.data.server_now);detailVisible.value=true;} }
  catch(e){ElMessage.error(e instanceof Error?e.message:'充值凭证查询失败');}
}
async function submit() {
  if(busy.value)return;busy.value=true;searchError.value='';
  try {
    if(!recovery.value){
      if(!customer.value || cents.value===null){searchError.value='请确认客户并输入正数金额，最多两位小数';return;}
      const draft={payload:{user_id:customer.value.id,amount_cents:cents.value,request_key:crypto.randomUUID()},customer:{...customer.value}};
      if(!await confirmAction(`确认向 ${draft.customer.nickname || draft.customer.username}（账号 ${draft.customer.username}）储值 ${formatMoney(draft.payload.amount_cents)}？本设备模拟收款成功后，款项才会存入该客户账户。`))return;
      recovery.value=draft;sessionStorage.setItem(recoveryKey,JSON.stringify(draft));
    }
    const response=await createRecharge(recovery.value.payload);forget();selected.value=response.data;syncClock(response.data.server_now);detailVisible.value=true;
    customer.value=undefined;customers.value=[];searched.value=false;await load();
  } catch(e) {
    if(e instanceof ApiRequestError && e.status && e.status>=400 && e.status<500)forget();
    searchError.value=e instanceof Error?e.message:'开单结果尚未确认，请恢复原请求';
  } finally { busy.value=false; }
}
async function collect(order: RechargeOrder){
  if(busy.value)return;busy.value=true;
  try {
    const response=await getRecharge(order.id,props.admin);selected.value=response.data;
    if(response.data.status!=='pending'){await load();detailVisible.value=true;return;}
    detailVisible.value=false;paymentId.value=response.data.payment_id;paymentVisible.value=true;
  }catch(e){ElMessage.error(e instanceof Error?e.message:'收款信息查询失败');}
  finally{busy.value=false;}
}
async function cancel(order: RechargeOrder){
  if(busy.value)return;busy.value=true;
  const keyName=`bf-recharge-cancel:${auth.user?.id}:${order.id}`;
  try{
    if(!await confirmAction(`撤销 ${order.customer.username} 的 ${formatMoney(order.amount_cents)} 未收款充值单？本单尚未入账。`))return;
    const key=sessionStorage.getItem(keyName)||crypto.randomUUID();sessionStorage.setItem(keyName,key);
    const response=await cancelRecharge(order.id,key);sessionStorage.removeItem(keyName);selected.value=response.data;
    ElMessage.success('未收款充值单已撤销');await load();
  }catch(e){
    if(e instanceof ApiRequestError && e.status && e.status>=400 && e.status<500)sessionStorage.removeItem(keyName);
    ElMessage.error(e instanceof Error?e.message:'撤销结果尚未确认，请查原单');await detail(order);await load();
  }finally{busy.value=false;}
}
async function changed(){
  await load();
  if(selected.value && detailVisible.value)await detail(selected.value);
}
function refreshVisible(){if(!document.hidden && !busy.value && !loading.value && !paymentVisible.value)void load(false,true);}
onMounted(()=>{
  try{recovery.value=JSON.parse(sessionStorage.getItem(recoveryKey)||'null');}catch{forget();}
  void load();let ticks=0;timer=setInterval(()=>{now.value=Date.now()+offset;if(++ticks%15===0)refreshVisible();},1000);
  document.addEventListener('visibilitychange',refreshVisible);
});
onUnmounted(()=>{listVersion++;searchVersion++;detailVersion++;clearInterval(timer);document.removeEventListener('visibilitychange',refreshVisible);});
</script>
<template>
  <section class="recharge-workbench">
    <h2>办理储值</h2><p class="muted-text">先确认客户，在本设备模拟收款后到账。每笔记录保留客户、金额与经办人。</p>
    <el-alert v-if="recovery" title="上次开单结果尚未确认" type="warning" :closable="false">
      <p>客户 {{ recovery.customer.username }} · {{ formatMoney(recovery.payload.amount_cents) }}。请恢复原请求，避免重复充值。</p><el-button :loading="busy" @click="submit">恢复上次充值单</el-button>
    </el-alert>
    <el-alert v-if="searchError" :title="searchError" type="error" :closable="false" />
    <el-form class="recharge-search" label-position="top" @submit.prevent="search">
      <el-form-item label="查找客户"><el-input v-model="query" :disabled="busy || !!recovery" placeholder="完整用户名或登记联系方式" maxlength="50" clearable /></el-form-item>
      <el-button native-type="submit" :loading="searching" :disabled="busy || !!recovery || !query.trim()">查询客户</el-button>
    </el-form>
    <p v-if="searched && !customers.length" class="muted-text">未找到可充值账户，请核对完整用户名或登记联系方式。</p>
    <ul v-if="customers.length" class="recharge-customers">
      <li v-for="item in customers" :key="item.id" :class="{selected:customer?.id===item.id}">
        <div><strong>{{ item.nickname || item.username }}</strong><p>账号 {{ item.username }} · {{ item.contact_masked || '未登记联系方式' }}</p><span>当前余额 {{ formatMoney(item.balance_cents) }}</span></div>
        <el-button :disabled="busy || !!recovery" :type="customer?.id===item.id?'primary':'default'" @click="customer=item">{{ customer?.id===item.id?'已选定':'选择客户' }}</el-button>
      </li>
    </ul>
    <el-form v-if="customer" class="recharge-amount-form" label-position="top" @submit.prevent="submit">
      <p>储值到账账户：<strong>{{ customer.username }}</strong></p>
      <el-form-item label="储值金额（元）"><el-input v-model="amount" inputmode="decimal" :disabled="busy || !!recovery" maxlength="11" placeholder="例如 100.00" /></el-form-item>
      <p class="muted-text">只增加储值余额，会员等级和积分保持不变。</p><el-button type="primary" native-type="submit" :loading="busy" :disabled="cents===null || !!recovery">确认客户与金额</el-button>
    </el-form>
    <section class="recharge-history">
      <h2>{{ admin?'全部充值记录':'我的充值工作单' }}</h2>
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <el-form class="recharge-filters" label-position="top" @submit.prevent="load(true)">
        <el-form-item label="开始日期"><el-date-picker v-model="filters.date_from" value-format="YYYY-MM-DD" placeholder="不限" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="filters.date_to" value-format="YYYY-MM-DD" placeholder="不限" /></el-form-item>
        <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部"><el-option v-for="(label,value) in labels" :key="value" :value="value" :label="label" /></el-select></el-form-item>
        <el-form-item label="完整单号"><el-input v-model="filters.order_no" placeholder="充值单号或收款单号" maxlength="64" clearable /></el-form-item>
        <el-button native-type="submit" :loading="loading">查询记录</el-button>
      </el-form>
      <div v-loading="loading">
        <p class="muted-text">共 {{ total }} 笔 · 模拟支付宝</p>
        <article v-for="order in orders" :key="order.id" class="recharge-row">
          <div><strong>{{ order.customer.nickname || order.customer.username }} · {{ order.customer.username }}</strong><p>{{ formatDeadline(order.created_at) }} · 开单 {{ order.operator_name_snapshot }}</p><small>{{ order.recharge_no }}</small></div>
          <div class="recharge-row-end"><strong>{{ formatMoney(order.amount_cents) }}</strong><span>{{ labels[order.status] }}</span><small v-if="order.status==='pending'">剩余 {{ countdownText(order.expires_at,now) }}</small><el-button :disabled="busy" @click="detail(order)">{{ order.status==='pending'?'继续办理':'查看凭证' }}</el-button></div>
        </article>
        <el-empty v-if="!orders.length && !loading && !error" description="暂无充值工作单" />
      </div>
      <el-pagination v-model:current-page="page" :page-size="10" :total="total" layout="prev,pager,next" @current-change="load()" />
    </section>
    <el-drawer v-model="detailVisible" title="会员储值单" size="min(480px,100vw)" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
      <template v-if="selected">
        <h2>{{ selected.customer.nickname || selected.customer.username }}</h2><p>到账账号：{{ selected.customer.username }} · {{ selected.customer.contact_masked || '未登记联系方式' }}</p>
        <div class="recharge-receipt-amount"><strong>{{ formatMoney(selected.amount_cents) }}</strong><span>{{ labels[selected.status] }} · 模拟支付宝</span></div>
        <dl class="recharge-details"><dt>充值单</dt><dd>{{ selected.recharge_no }}</dd><dt>收款单</dt><dd>{{ selected.payment_no }}</dd><dt>开单人员</dt><dd>{{ selected.operator_name_snapshot }}</dd><dt>创建时间</dt><dd>{{ formatDeadline(selected.created_at) }}</dd><template v-if="selected.canceled_at"><dt>撤销时间</dt><dd>{{ formatDeadline(selected.canceled_at) }}</dd></template><template v-if="selected.status==='pending'"><dt>付款截止</dt><dd>{{ formatDeadline(selected.expires_at) }}</dd></template>
          <template v-if="selected.credit"><dt>实际收款</dt><dd>{{ selected.credit.operator_username }}</dd><dt>到账时间</dt><dd>{{ formatDeadline(selected.credit.created_at) }}</dd><dt>入账前余额</dt><dd>{{ formatMoney(selected.credit.balance_before_cents) }}</dd><dt>本笔到账后</dt><dd>{{ formatMoney(selected.credit.balance_after_cents) }}</dd></template>
        </dl>
        <p class="muted-text">充值成功只增加目标客户储值，不改变等级与积分。已到账误操作请保留单号交管理员核查。</p>
        <div class="recharge-actions"><el-button :disabled="busy" @click="detail(selected)">刷新状态</el-button><template v-if="selected.status==='pending'"><el-button type="primary" :disabled="busy" @click="collect(selected)">前往模拟收款</el-button><el-button :loading="busy" @click="cancel(selected)">撤销未收款单</el-button></template></div>
      </template>
    </el-drawer>
    <PaymentDialog v-model="paymentVisible" :payment-id="paymentId" @paid="changed" @updated="changed" @update:model-value="value=>{if(!value)void load();}" />
  </section>
</template>
<style scoped>
.recharge-workbench{padding-block:20px;line-height:1.6}.recharge-search{display:flex;align-items:end;gap:12px;max-width:650px;margin:24px 0}.recharge-search :deep(.el-form-item){flex:1;margin:0}.recharge-customers{list-style:none;padding:0;max-width:760px}.recharge-customers li{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:16px;border:1px solid #dce3dd;margin-block:12px}.recharge-customers li.selected{border-color:#386348;background:#f3f6f0}.recharge-customers p{margin:4px 0;color:#667167}.recharge-amount-form{max-width:460px;margin-block:24px}.recharge-history{border-top:1px solid #dce3dd;padding-top:24px;margin-top:32px}.recharge-filters{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin-bottom:20px}.recharge-filters :deep(.el-form-item){margin:0;flex:1 1 150px;min-width:0}.recharge-filters :deep(.el-date-editor){width:100%}.recharge-row{display:flex;gap:20px;justify-content:space-between;border-bottom:1px solid #e0e6de;padding:22px 0;overflow-wrap:anywhere}.recharge-row p,.recharge-row small{font-size:13px;color:#6b766c}.recharge-row-end{display:grid;justify-items:end;gap:6px;flex-shrink:0}.recharge-receipt-amount{display:grid;gap:10px;padding:24px 0;border-block:1px solid #dce3dd;margin:24px 0}.recharge-receipt-amount strong{font-size:34px;color:#315c3e}.recharge-details{display:grid;grid-template-columns:90px minmax(0,1fr);gap:16px;font-size:13px}.recharge-details dd{margin:0;overflow-wrap:anywhere}.recharge-details dt{color:#657467}.recharge-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:24px}.recharge-actions :deep(.el-button){margin:0}
@media(max-width:600px){.recharge-search{align-items:stretch;flex-direction:column}.recharge-row{flex-direction:column}.recharge-row-end{display:flex;flex-wrap:wrap;align-items:center}.recharge-row-end .el-button{margin-left:auto}.recharge-customers li{align-items:start;flex-direction:column}}
</style>
