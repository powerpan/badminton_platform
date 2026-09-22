<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { getAllCourts, getReservationRules, type Court, type ReservationRules } from '../api/court';
import { createCourtBlock, getCourtBlocks, releaseCourtBlock, type CourtBlock } from '../api/operations';
import { addDays, confirmAction } from '../views/admin/shared';
const items = ref<CourtBlock[]>([]), courts = ref<Court[]>([]), rules = ref<ReservationRules>();
const visible = ref(false), loading = ref(false), saving = ref(false), error = ref('');
const range = ref({ date_from: addDays(0), date_to: addDays(7) });
const form = ref({ court_id: 0, reserve_date: addDays(1), start_time: '09:00', end_time: '10:00', reason: '' });
const step = computed(() => { const n = rules.value?.slot_interval_minutes || 60; return `${String(Math.floor(n / 60)).padStart(2,'0')}:${String(n % 60).padStart(2,'0')}`; });
async function load() {
  loading.value = true; error.value = '';
  try { items.value = (await getCourtBlocks(range.value)).data.items; }
  catch (e) { error.value = e instanceof Error ? e.message : '维护安排加载失败'; }
  finally { loading.value = false; }
}
async function open() {
  error.value = '';
  try {
    const [c,r] = await Promise.all([getAllCourts(),getReservationRules()]); courts.value = c; rules.value = r.data;
    form.value = { court_id: courts.value[0]?.id || 0, reserve_date: addDays(1), start_time: r.data.business_start_time, end_time: r.data.business_end_time, reason: '' }; visible.value = true;
  } catch (e) { error.value = e instanceof Error ? e.message : '无法打开维护表单'; }
}
async function save() {
  saving.value = true; error.value = '';
  try { await createCourtBlock(form.value); visible.value = false; await load(); }
  catch (e) { error.value = e instanceof Error ? e.message : '保存失败'; }
  finally { saving.value = false; }
}
async function release(row: CourtBlock) {
  if (!await confirmAction(`释放 ${row.court_name} ${row.reserve_date} ${row.start_time}–${row.end_time} 的维护占用？`)) return;
  try { await releaseCourtBlock(row.id); await load(); }
  catch (e) { error.value = e instanceof Error ? e.message : '释放失败'; }
}
onMounted(load);
</script>
<template>
  <section class="operations-section">
    <div class="operations-heading"><div><h2>维护与包场</h2><p>有有效预约的时段不能直接设为维护。</p></div><el-button type="primary" @click="open">新增维护时段</el-button></div>
    <el-alert v-if="error && !visible" :title="error" type="error" :closable="false" show-icon />
    <el-form inline class="element-filter" @submit.prevent="load"><el-form-item label="开始日期"><el-date-picker v-model="range.date_from" value-format="YYYY-MM-DD" :clearable="false" /></el-form-item><el-form-item label="结束日期"><el-date-picker v-model="range.date_to" value-format="YYYY-MM-DD" :clearable="false" /></el-form-item><el-form-item><el-button native-type="submit">查询维护</el-button></el-form-item></el-form>
    <el-table :data="items" v-loading="loading" empty-text="此日期范围暂无维护安排">
      <el-table-column prop="court_name" label="场地" min-width="100" /><el-table-column prop="reserve_date" label="日期" min-width="120" />
      <el-table-column label="时间" min-width="130"><template #default="{ row }">{{ row.start_time }}–{{ row.end_time }}</template></el-table-column>
      <el-table-column prop="reason" label="原因" min-width="180" /><el-table-column label="状态" min-width="90"><template #default="{ row }">{{ row.status === 'active' ? '占用中' : '已释放' }}</template></el-table-column>
      <el-table-column label="操作" width="85" fixed="right"><template #default="{ row }"><el-button link type="primary" :disabled="row.status !== 'active'" @click="release(row)">释放</el-button></template></el-table-column>
    </el-table>
  </section>
  <el-drawer v-model="visible" title="新增维护时段" size="min(520px, 100vw)" class="admin-edit-drawer" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving">
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <el-form v-if="rules" label-position="top" :disabled="saving" @submit.prevent="save">
      <el-form-item label="场地"><el-select v-model="form.court_id"><el-option v-for="court in courts" :key="court.id" :value="court.id" :label="court.court_name" /></el-select></el-form-item>
      <el-form-item label="日期"><el-date-picker v-model="form.reserve_date" value-format="YYYY-MM-DD" :clearable="false" /></el-form-item>
      <el-form-item label="开始时间"><el-time-select v-model="form.start_time" :start="rules.business_start_time" :end="rules.business_end_time" :step="step" :clearable="false" /></el-form-item>
      <el-form-item label="结束时间"><el-time-select v-model="form.end_time" :start="rules.business_start_time" :end="rules.business_end_time" :step="step" :min-time="form.start_time" :clearable="false" /></el-form-item>
      <el-form-item label="原因"><el-input v-model="form.reason" type="textarea" :rows="3" maxlength="255" placeholder="例如：地胶维护，预计完成后恢复预约" /></el-form-item>
      <el-button type="primary" native-type="submit" :loading="saving">保存维护安排</el-button>
    </el-form>
  </el-drawer>
</template>
