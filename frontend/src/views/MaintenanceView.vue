<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { getAllCourts, type Court } from '../api/court';
import { getMaintenanceBlocks, type MaintenanceBlock } from '../api/operations';
import { addDays } from './admin/shared';

const rows = ref<MaintenanceBlock[]>([]), courts = ref<Court[]>([]);
const loading = ref(false), error = ref('');
const filters = ref({ date_from: addDays(0), date_to: addDays(7), court_id: undefined as number | undefined, status: '' });
const labels = { scheduled: '待开始', in_progress: '安排中', ended: '时段已结束', released: '已释放' };
let latestRequest = 0;
async function load() {
  const request = ++latestRequest;
  loading.value = true; error.value = '';
  try { const data = (await getMaintenanceBlocks({ ...filters.value })).data.items; if (request === latestRequest) rows.value = data; }
  catch (e) { if (request !== latestRequest) return; rows.value = []; error.value = e instanceof Error ? e.message : '维修安排加载失败'; }
  finally { if (request === latestRequest) loading.value = false; }
}
onMounted(async () => {
  try { courts.value = await getAllCourts(); }
  catch (e) { error.value = e instanceof Error ? e.message : '场地列表加载失败'; return; }
  await load();
});
</script>
<template>
  <section class="staff-workspace">
    <header class="staff-heading"><div><p class="staff-eyebrow">BF · 场馆保障</p><h1>维修安排</h1><p>查看场地、维护原因与安排时间。场地恢复开放由管理员确认。</p></div><el-button :loading="loading" @click="load">刷新安排</el-button></header>
    <el-form class="staff-filters" label-position="top" @submit.prevent="load">
      <el-form-item label="开始日期"><el-date-picker v-model="filters.date_from" value-format="YYYY-MM-DD" :clearable="false" /></el-form-item>
      <el-form-item label="结束日期"><el-date-picker v-model="filters.date_to" value-format="YYYY-MM-DD" :clearable="false" /></el-form-item>
      <el-form-item label="场地"><el-select v-model="filters.court_id" clearable placeholder="全部场地"><el-option v-for="court in courts" :key="court.id" :value="court.id" :label="court.court_name" /></el-select></el-form-item>
      <el-form-item label="安排状态"><el-select v-model="filters.status" clearable placeholder="全部状态"><el-option v-for="(label, value) in labels" :key="value" :value="value" :label="label" /></el-select></el-form-item>
      <el-button native-type="submit" type="primary" :loading="loading">查询</el-button>
    </el-form>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <div v-loading="loading" class="maintenance-list" aria-live="polite">
      <p class="staff-result-count">共 {{ rows.length }} 项安排</p>
      <article v-for="row in rows" :key="row.id" class="maintenance-row">
        <div class="maintenance-date"><strong>{{ row.reserve_date }}</strong><span>{{ row.start_time }}–{{ row.end_time }}</span></div>
        <div class="maintenance-detail"><h2>{{ row.court_name }} <small>{{ row.court_no }}</small></h2><p>{{ row.reason }}</p></div>
        <span class="maintenance-status" :class="row.schedule_status">{{ labels[row.schedule_status] }}</span>
      </article>
      <el-empty v-if="!rows.length && !loading && !error" description="所选范围暂无维修安排" />
    </div>
  </section>
</template>
