<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { getTransactions, getTransaction, type FinanceFilters, type FinanceRecord, type FinanceResult, type FinanceDetail } from '../../api/finance';
import { addDays, formatMoney } from './shared';
import { formatDeadline } from '../../utils/booking';
import ReservationHistory from '../../components/ReservationHistory.vue';

const route = useRoute();
const businesses: Record<string,string> = { reservation:'线上订场',walk_in:'到店开场',walk_in_extension:'到店续场',shop:'商城',recharge:'柜台储值',reschedule:'改期差额',adjustment:'人工调整' };
const entries: Record<string,string> = { collection:'消费收款',refund:'退款',recharge:'储值入账',adjustment:'人工调整',points:'积分变动',unverified:'历史待核对' };
const methods: Record<string,string> = { balance:'储值余额',mock_alipay:'模拟支付宝',manual:'人工调整',unknown:'未记录' };
const statuses: Record<string,string> = { pending:'待付款',succeeded:'已成功',refunded:'已全额退款',canceled:'已撤销',expired:'已过期',recorded:'已记账',unverified:'待核对' };
const form = ref({ date_from:String(route.query.date_from || addDays(-29)),date_to:String(route.query.date_to || addDays(0)),business_type:'',entry_type:'',pay_method:'',status:'',customer:'',operator:'',order_no:'' });
const result = ref<FinanceResult | null>(null), loading = ref(false), error = ref('');
let listVersion = 0, detailVersion = 0;
const applied = ref<FinanceFilters>({});
const visible = ref(false), selected = ref<FinanceDetail | null>(null), detailLoading = ref(false), detailError = ref('');
const selectedSource = ref<FinanceRecord | null>(null);
const appliedText = computed(() => [businesses[applied.value.business_type || ''], entries[applied.value.entry_type || ''], methods[applied.value.pay_method || ''], statuses[applied.value.status || ''], applied.value.customer && `客户 ${applied.value.customer}`, applied.value.operator && `经办 ${applied.value.operator}`, applied.value.order_no && `单号 ${applied.value.order_no}`].filter(Boolean).join(' · ') || '全部业务');
const recordNumber = (row: FinanceRecord) => row.refund_no || row.payment_no || row.order_no || `${row.entry_type === 'adjustment' ? '调整' : '账户流水'} #${row.record_id}`;
const customerText = (row: FinanceRecord) => row.customer_name || row.customer_username || '未记名散客';
function parameters(): FinanceFilters { return Object.fromEntries(Object.entries(form.value).filter(([,v]) => v)); }

async function load(page = 1, params = parameters()) {
  const request = ++listVersion; loading.value = true; error.value = '';
  try {
    const response = await getTransactions({ ...params, page, page_size:20 });
    if (request !== listVersion) return;
    result.value = response.data; applied.value = { ...params };
  } catch (e) { if (request === listVersion) { result.value = null; error.value = e instanceof Error ? e.message : '流水暂时无法加载'; } }
  finally { if (request === listVersion) loading.value = false; }
}
async function openDetail(row: FinanceRecord) {
  selectedSource.value = row; selected.value = null; visible.value = true;
  const request = ++detailVersion; detailLoading.value = true; detailError.value = '';
  try { const response = await getTransaction(row.record_type,row.record_id); if (request === detailVersion && visible.value) selected.value = response.data; }
  catch (e) { if (request === detailVersion) detailError.value = e instanceof Error ? e.message : '详情加载失败'; }
  finally { if (request === detailVersion) detailLoading.value = false; }
}
function changePage(page: number) { void load(page, applied.value); }
watch(visible, open => { if (!open) { detailVersion++; detailLoading.value = false; } });
onMounted(() => load());
onUnmounted(() => { listVersion++; detailVersion++; });
</script>

<template>
  <section class="page-header"><h1>交易流水</h1><p>按资金发生时间查收款、退款、储值和调整，逐笔核对原始凭据。</p></section>
  <section class="finance-page" :aria-busy="loading">
    <el-form class="finance-filters" label-position="top" @submit.prevent="load()">
      <div class="filter-primary">
        <el-form-item label="开始日期"><el-date-picker v-model="form.date_from" type="date" value-format="YYYY-MM-DD" :clearable="false" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="form.date_to" type="date" value-format="YYYY-MM-DD" :clearable="false" /></el-form-item>
        <el-button type="primary" :loading="loading" native-type="submit">查询流水</el-button>
      </div>
      <details class="advanced-filters"><summary>更多筛选</summary><div class="filter-grid">
        <el-form-item label="业务类型"><el-select v-model="form.business_type" clearable placeholder="全部业务"><el-option v-for="(label,value) in businesses" :key="value" :label="label" :value="value" /></el-select></el-form-item>
        <el-form-item label="收支类型"><el-select v-model="form.entry_type" clearable placeholder="全部类型"><el-option v-for="(label,value) in entries" :key="value" :label="label" :value="value" /></el-select></el-form-item>
        <el-form-item label="渠道"><el-select v-model="form.pay_method" clearable placeholder="全部渠道"><el-option v-for="(label,value) in methods" :key="value" :label="label" :value="value" /></el-select></el-form-item>
        <el-form-item label="状态"><el-select v-model="form.status" clearable placeholder="全部状态"><el-option v-for="(label,value) in statuses" :key="value" :label="label" :value="value" /></el-select></el-form-item>
        <el-form-item label="客户"><el-input v-model="form.customer" maxlength="50" placeholder="账号、姓名或联系方式" /></el-form-item>
        <el-form-item label="经办人员"><el-input v-model="form.operator" maxlength="50" placeholder="收退款、开单或调整经办用户名" /></el-form-item>
        <el-form-item label="完整单号"><el-input v-model="form.order_no" maxlength="64" placeholder="业务、预约、付款或退款号" /></el-form-item>
      </div><p class="finance-note">成功收退款按实际经办人查询；尚未收款的记录按开单人查询。</p></details>
    </el-form>
    <el-alert v-if="error" type="error" :title="error" :closable="false" show-icon />
    <template v-if="result">
      <div class="finance-scope"><strong>{{ result.date_from }} 至 {{ result.date_to }}</strong><p>{{ appliedText }} · 共 {{ result.total }} 笔 · 汇总包含全部匹配记录</p></div>
      <div class="finance-totals">
        <section><h2>模拟渠道</h2><dl><div><dt>收款</dt><dd>{{ formatMoney(result.summary.channel_receipts_cents) }}</dd></div><div><dt>退款</dt><dd>{{ formatMoney(result.summary.channel_refunds_cents) }}</dd></div><div><dt>净收款</dt><dd>{{ formatMoney(result.summary.channel_net_cents) }}</dd></div></dl><p>其中储值充值 {{ formatMoney(result.summary.recharge_cents) }}，已包含在收款中。</p></section>
        <section><h2>消费结算</h2><dl><div><dt>消费收款</dt><dd>{{ formatMoney(result.summary.consumption_receipts_cents) }}</dd></div><div><dt>消费退款</dt><dd>{{ formatMoney(result.summary.consumption_refunds_cents) }}</dd></div><div><dt>消费净额</dt><dd>{{ formatMoney(result.summary.consumption_net_cents) }}</dd></div></dl><p>订场与商城的两种渠道合计；不含储值充值及人工调整。</p></section>
      </div>
      <div class="finance-breakdown"><p>余额消费 <strong>{{ formatMoney(result.summary.balance_consumption_cents) }}</strong> · 退回余额 <strong>{{ formatMoney(result.summary.balance_refunds_cents) }}</strong></p><p>人工调增 <strong>{{ formatMoney(result.summary.adjustment_increase_cents) }}</strong> · 人工调减 <strong>{{ formatMoney(result.summary.adjustment_decrease_cents) }}</strong></p></div>
      <p class="finance-note">余额消费使用已经储值的金额，不再算一次渠道收款。待付款、已撤销和未核对金额不进入成功收退款汇总。</p>
      <details class="reconciliation" :class="{ 'has-issues':result.reconciliation.mismatches || result.summary.unverified_count }"><summary>账户核对：{{ result.reconciliation.accounts }} 个相关账户，{{ result.reconciliation.mismatches }} 个不一致 · 历史待核对 {{ result.summary.unverified_count }} 笔</summary>
        <p>按本次记录涉及的客户，核对其完整账户流水与当前余额、积分；不局限本页或日期范围。{{ result.reconciliation.without_history }} 个账户尚无流水依据。初始余额沿用首笔记录，不能代替外部支付对账。</p>
        <p v-for="issue in result.reconciliation.issues" :key="issue.user_id">{{ issue.username }}：当前余额 {{ formatMoney(issue.balance_cents) }}，流水末余额 {{ issue.recorded_balance_cents == null ? '未记录' : formatMoney(issue.recorded_balance_cents) }}；积分 {{ issue.points }} / {{ issue.recorded_points ?? '未记录' }}<span v-if="issue.chain_mismatch">；历史流水衔接异常</span>。</p>
        <p v-if="result.reconciliation.mismatches > result.reconciliation.issues.length">最多列出 20 个异常账户，可按客户缩小查询范围。</p>
      </details>
      <el-table :data="result.items" stripe empty-text="此范围暂无流水" class="finance-table">
        <el-table-column label="发生时间" min-width="162"><template #default="{row}">{{ formatDeadline(row.occurred_at) }}</template></el-table-column>
        <el-table-column label="业务 / 收支" min-width="130"><template #default="{row}">{{ businesses[row.business_type] || '历史业务' }}<br /><small>{{ entries[row.entry_type] }}</small></template></el-table-column>
        <el-table-column label="客户 / 经办" min-width="145"><template #default="{row}">{{ customerText(row) }}<br /><small>{{ row.operator_name || '经办未记录' }}</small></template></el-table-column>
        <el-table-column label="金额 / 渠道" min-width="145"><template #default="{row}"><strong>{{ formatMoney(row.amount_cents) }}</strong><br /><small>{{ methods[row.pay_method] || row.pay_method }}</small></template></el-table-column>
        <el-table-column label="状态" min-width="105"><template #default="{row}">{{ statuses[row.status] || row.status }}</template></el-table-column>
        <el-table-column label="单号" min-width="210"><template #default="{row}"><span class="number-text">{{ recordNumber(row) }}</span></template></el-table-column>
        <el-table-column label="操作" fixed="right" width="82"><template #default="{row}"><el-button link type="primary" @click="openDetail(row)">凭据</el-button></template></el-table-column>
      </el-table>
      <div class="finance-cards"><p v-if="!result.items.length" class="quiet-state">此范围暂无流水</p><article v-for="row in result.items" :key="`${row.record_type}:${row.record_id}`"><div class="record-title"><strong>{{ entries[row.entry_type] }} · {{ formatMoney(row.amount_cents) }}</strong><span>{{ statuses[row.status] }}</span></div><p>{{ businesses[row.business_type] || '历史业务' }} · {{ methods[row.pay_method] || row.pay_method }}</p><p>{{ customerText(row) }} · {{ row.operator_name || '经办未记录' }}</p><p>{{ formatDeadline(row.occurred_at) }}</p><small class="number-text">{{ recordNumber(row) }}</small><el-button link type="primary" @click="openDetail(row)">查看凭据</el-button></article></div>
      <el-pagination :current-page="result.page" :page-size="result.page_size" :total="result.total" layout="prev, pager, next, total" :disabled="loading" @current-change="changePage" />
    </template>
    <p v-else-if="loading" role="status">正在读取交易与汇总…</p>
  </section>

  <el-drawer v-model="visible" title="交易凭据" size="min(650px, 100vw)" class="finance-drawer">
    <p v-if="detailLoading" role="status">正在读取原始记录…</p>
    <div v-else-if="detailError"><el-alert :title="detailError" type="error" :closable="false" /><el-button v-if="selectedSource" @click="openDetail(selectedSource)">重试</el-button></div>
    <div v-else-if="selected" class="finance-detail">
      <div class="record-title"><strong>{{ entries[selected.record.entry_type] }} · {{ formatMoney(selected.record.amount_cents) }}</strong><span>{{ statuses[selected.record.status] }}</span></div>
      <p class="number-text">{{ recordNumber(selected.record) }}</p>
      <p>{{ selected.record.description }}</p>
      <dl class="detail-facts"><dt>客户</dt><dd>{{ customerText(selected.record) }}<span v-if="selected.record.customer_username"> · {{ selected.record.customer_username }}</span></dd><dt>联系方式</dt><dd>{{ selected.record.customer_contact || '未登记' }}</dd><dt>{{ selected.record.record_type==='payment' && !selected.record.confirmed ? '开单经办' : '资金经办' }}</dt><dd>{{ selected.record.operator_name || '未记录' }}</dd><dt>开单人员</dt><dd>{{ selected.record.created_by_name || '未记录' }}</dd><dt>发生时间</dt><dd>{{ formatDeadline(selected.record.occurred_at) }}</dd><dt>渠道</dt><dd>{{ methods[selected.record.pay_method] || selected.record.pay_method }}</dd><dt>业务单号</dt><dd>{{ selected.record.order_no || selected.record.reservation_no || '账户调整' }}</dd></dl>
      <p v-if="selected.record.evidence==='account'" class="finance-note">此笔依据原账户流水记账，未补造统一支付单。</p>
      <p v-if="selected.record.status==='unverified'" class="finance-note">当前凭据不足，所列业务金额不计入已确认收退款。</p>
      <section v-if="selected.business?.reserve_date"><h3>关联场次</h3><p>{{ selected.business.court_name }} · {{ selected.business.reserve_date }}<br />{{ selected.business.start_time }}–{{ selected.business.end_time }}</p><RouterLink :to="`/admin/reservations?reservation_id=${selected.record.reservation_id}`">查看订场及续场详情</RouterLink></section>
      <section v-if="selected.items?.length"><h3>商城商品</h3><p v-for="item in selected.items" :key="item.product_id">{{ item.product_name }} × {{ item.quantity }} · {{ formatMoney(item.subtotal_cents) }}</p></section>
      <h3>关联收款</h3><p v-if="!selected.payments.length" class="finance-note">没有统一支付单。</p>
      <article v-for="payment in selected.payments" :key="payment.id"><div class="record-title"><strong>{{ payment.purpose==='reschedule' ? '改期补差' : '收款' }} · {{ formatMoney(payment.amount_cents) }}</strong><span>{{ statuses[payment.status] }}</span></div><p class="number-text">支付 #{{ payment.id }} · {{ payment.payment_no }}</p><p>{{ methods[payment.pay_method] }} · {{ payment.paid_at ? formatDeadline(payment.paid_at) : '尚未付款' }}</p><p>开单 {{ payment.operator_name_snapshot }} · 收款 {{ payment.collector_username || '未记录' }}</p></article>
      <h3>关联退款</h3><p v-if="!selected.refunds.length" class="finance-note">没有统一退款记录。</p>
      <article v-for="refund in selected.refunds" :key="refund.id"><strong>{{ formatMoney(refund.amount_cents) }} · {{ methods[refund.pay_method] }}</strong><p class="number-text">退款 #{{ refund.id }} · {{ refund.refund_no }}</p><p>原支付 #{{ refund.payment_order_id }} · {{ refund.operator_name_snapshot }} · {{ formatDeadline(refund.refunded_at) }}</p><p>{{ refund.reason }}</p></article>
      <h3>原账户流水</h3><p v-if="!selected.account_transactions.length" class="finance-note">本业务没有余额或积分变动。</p>
      <article v-for="entry in selected.account_transactions" :key="entry.id"><strong>流水 #{{ entry.id }} · {{ formatMoney(entry.balance_change_cents) }}</strong><p>{{ entry.reason }}</p><p>余额 {{ formatMoney(entry.balance_before_cents) }} → {{ formatMoney(entry.balance_after_cents) }} · 积分 {{ entry.points_change > 0 ? '+' : '' }}{{ entry.points_change }}</p><p>{{ entry.operator_username || '经办未记录' }} · {{ formatDeadline(entry.created_at) }}</p></article>
      <ReservationHistory v-if="selected.record.reservation_id" :reservation-id="selected.record.reservation_id" :items="selected.changes" />
    </div>
    <template #footer><el-button @click="visible=false">关闭</el-button></template>
  </el-drawer>
</template>

<style scoped>
.finance-page { background: #fff; border: 1px solid var(--el-border-color-lighter); padding: 24px; }
.filter-primary { display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
.filter-primary .el-form-item { margin: 0; }
.filter-primary .el-button { margin-bottom: 0; }
.advanced-filters { margin: 20px 0; }
summary { cursor: pointer; font-weight: 600; line-height: 1.7; }
.filter-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 14px; margin-top: 16px; }
.filter-grid .el-form-item { margin: 0; }
.finance-scope { margin-top: 24px; }
.finance-scope p,.finance-note,.finance-totals p,.reconciliation p { font-size: .85rem; color: var(--el-text-color-secondary); line-height: 1.7; }
.finance-totals { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 28px; padding: 12px 0; }
h2 { font-size: 1rem; margin: 8px 0 16px; }
.finance-totals dl { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 12px; margin: 0; }
dt { color: var(--el-text-color-secondary); font-size: .85rem; }
dd { margin: 6px 0 0; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
.finance-totals dd { font-size: clamp(1rem,1.3vw,1.35rem); font-weight: 650; }
.finance-breakdown { display: flex; flex-wrap: wrap; gap: 6px 24px; border-block: 1px solid var(--el-border-color-lighter); padding: 8px 0; font-size: .9rem; }
.reconciliation { margin: 18px 0 24px; font-size: .9rem; }
.has-issues summary { color: #94601b; }
.number-text { overflow-wrap: anywhere; line-height: 1.7; }
.finance-cards { display: none; }
.el-pagination { margin-top: 20px; justify-content: flex-end; }
.finance-detail p { font-size: .88rem; line-height: 1.7; overflow-wrap: anywhere; }
.finance-detail h3 { font-size: 1rem; margin-top: 26px; }
.finance-detail article,.finance-cards article { padding: 16px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.detail-facts { display: grid; grid-template-columns: 70px minmax(0,1fr); gap: 10px 12px; margin-block: 20px; font-size: .9rem; }
.detail-facts dd { margin: 0; }
.record-title { display: flex; gap: 12px; justify-content: space-between; flex-wrap: wrap; }
.record-title span { font-size: .85rem; color: var(--el-text-color-secondary); }
@media(max-width:1000px) { .filter-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } .finance-totals { grid-template-columns: 1fr; gap: 6px; } }
@media(max-width:640px) {
  .finance-page { padding: 16px; }
  .filter-primary { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 12px; }
  .filter-primary .el-button { grid-column: 1 / -1; justify-self: start; }
  .finance-filters :deep(.el-input),.finance-filters :deep(.el-date-editor) { width: 100%; min-width: 0; }
  .filter-grid { grid-template-columns: 1fr; }
  .finance-table { display: none; }
  .finance-cards { display: block; }
  .finance-cards p { margin: 5px 0; font-size: .85rem; line-height: 1.7; }
  .finance-cards small { display: block; color: var(--el-text-color-secondary); margin-bottom: 8px; }
  .finance-breakdown { display: block; }
  .finance-totals dl { gap: 8px; }
  .finance-totals dd { font-size: 1rem; }
}
</style>
