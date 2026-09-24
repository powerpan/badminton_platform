<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import { getOperationsReport, type OperationsReport } from '../api/operations';
const props = defineProps<{ dateFrom: string; dateTo: string; refreshKey: number }>();
const report = ref<OperationsReport>(), error = ref(''), loading = ref(false), showDays = ref(false);
let version = 0;
const hourly = computed(() => report.value?.hourly.filter(row => row.booked_minutes > 0) || []);
const maxMinutes = computed(() => Math.max(1, ...hourly.value.map(row => row.booked_minutes)));
const maxDaily = computed(() => Math.max(1,...(report.value?.daily.map(row => row.total) || [])));
const money = (n: number) => `¥${(n/100).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
const percent = (n: number | null) => n === null ? '暂无记录' : `${n}%`;
async function load() {
  const request = ++version; loading.value = true; error.value = '';
  try { const response = await getOperationsReport({date_from:props.dateFrom,date_to:props.dateTo}); if (request===version) report.value=response.data; }
  catch(e) { if(request===version) error.value=e instanceof Error?e.message:'经营数据加载失败'; }
  finally { if(request===version) loading.value=false; }
}
watch(() => [props.dateFrom,props.dateTo,props.refreshKey], load, {immediate:true});
onUnmounted(() => {version++;});
</script>
<template>
  <section class="operations-dashboard" :aria-busy="loading">
    <div class="operations-heading"><div><h2>预约经营</h2><p v-if="report">{{ report.date_from }} 至 {{ report.date_to }} · 更新于 {{ new Date(report.generated_at).toLocaleTimeString('zh-CN') }}</p></div><span v-if="loading" role="status">加载中…</span></div>
    <el-alert v-if="error" :title="`${error}${report ? '，下方保留上次数据' : ''}`" type="error" :closable="false" show-icon><el-button link @click="load">重试</el-button></el-alert>
    <template v-if="report">
      <div class="operations-metrics">
        <div><span>余额扣费</span><strong>{{ money(report.charges_cents) }}</strong></div><div><span>退回余额</span><strong>{{ money(report.refunds_cents) }}</strong></div><div><span>净扣费</span><strong>{{ money(report.net_cents) }}</strong></div>
      </div>
      <p class="metric-caption">按流水发生日期汇总预约扣费、退款和改期差额，共 {{ report.ledger_count }} 笔；不包含模拟渠道收退款、充值和商城。退款可能对应其他日期的预约。</p>
      <RouterLink :to="{path:'/admin/transactions',query:{date_from:report.date_from,date_to:report.date_to}}">查看两种渠道与全部业务流水</RouterLink>
      <p class="reconciliation-note" :class="{ warning: report.reconciliation.mismatches > 0 }">场次订单核对：{{ report.reconciliation.orders }} 笔，{{ report.reconciliation.mismatches }} 笔不一致，{{ report.reconciliation.unverified }} 笔缺少凭据待核对。按场次日期选订单，优先核对统一收退款，旧单查原账户记录。</p>
      <div class="operations-metrics">
        <div><span>取消率</span><strong>{{ percent(report.cancellation_rate) }}</strong><small>{{ report.canceled }} / {{ report.total }} 条预约</small></div>
        <div><span>已记录到场率</span><strong>{{ percent(report.attendance_rate) }}</strong><small>已到场 {{ report.checked_in }} · 未到场 {{ report.no_show }}</small></div>
        <div><span>到场记录覆盖率</span><strong>{{ percent(report.attendance_coverage) }}</strong><small>已结束首场/线上预约 {{ report.ended }} · 未记录 {{ report.unrecorded }}</small></div>
      </div>
      <p class="metric-caption">预约指标按场次日期。取消率 = 已取消 / 全部预约；到场率只计算已结束的线上预约和到店首场，续场不重复计新到店；未记录不会算作未到场。</p>
      <div class="operations-charts">
        <section><h3>每日预约</h3><p class="metric-caption">全部预约笔数；绿色条从零开始，取消数单独列示。</p>
          <p v-if="!report.total" class="quiet-state">此范围暂无预约。</p>
          <div v-else class="trend-scroll" tabindex="0" aria-label="每日预约图，数值同时列在数据表中">
            <div v-for="day in report.daily" :key="day.date" class="trend-column"><strong>{{ day.total }}</strong><div class="trend-track"><span :style="{height:`${day.total/maxDaily*100}%`}"></span></div><span>{{ day.date.slice(5) }}</span></div>
          </div>
          <el-button link :aria-expanded="showDays" @click="showDays=!showDays">{{ showDays ? '收起每日数据' : '查看每日数据' }}</el-button>
          <el-table v-if="showDays" :data="report.daily" max-height="320"><el-table-column prop="date" label="日期" min-width="115" /><el-table-column prop="total" label="总预约" /><el-table-column prop="canceled" label="取消" /><el-table-column prop="booked_minutes" label="有效分钟" min-width="100" /></el-table>
        </section>
        <section><h3>时段热度</h3><p class="metric-caption">有效预约在各小时内的占用分钟数，包含待支付；跨两小时分别计入。</p>
          <p v-if="!hourly.length" class="quiet-state">此范围暂无有效预约时长。</p>
          <div v-for="slot in hourly" :key="slot.hour" class="heat-row"><span>{{ slot.label }}</span><div class="heat-track"><i :style="{width:`${slot.booked_minutes/maxMinutes*100}%`}"></i></div><strong>{{ slot.booked_minutes }} 分</strong></div>
        </section>
      </div>
    </template>
  </section>
</template>
