<script setup lang="ts">
import OperationsDashboard from "../../components/OperationsDashboard.vue";
import { useRoute, useRouter } from "vue-router";
import ServiceHealth from "../../components/ServiceHealth.vue";
import { onMounted, computed, ref } from "vue";

import { adminGetCourtStatistics, adminGetStatisticsOverview, adminGetTimeSlotStatistics, adminGetUserStatistics, type CourtStatistic, type StatisticsOverview, type TimeSlotStatistic, type UserStatistic } from "../../api/admin";
import { addDays, setSuccess, setError } from "./shared";

const loading = ref(false);

const route = useRoute(), router = useRouter();
const statsRange = ref({ date_from: String(route.query.date_from || addDays(-6)), date_to: String(route.query.date_to || addDays(0)) });
const appliedRange = ref({ ...statsRange.value });
const refreshKey = ref(0);

const statisticsOverview = ref<StatisticsOverview | null>(null);

const courtStatistics = ref<CourtStatistic[]>([]);

const timeSlotStatistics = ref<TimeSlotStatistic[]>([]);

const userStatistics = ref<UserStatistic[]>([]);

const usageTable = computed(() =>
  courtStatistics.value.map((item) => ({
    ...item,
    progress: Math.min(100, Math.max(0, Number(item.usage_rate || 0))),
  })),
);

async function loadStatistics() {
  const params = { date_from: statsRange.value.date_from, date_to: statsRange.value.date_to };
  const [overview, courtsResult, slotsResult, usersResult] = await Promise.all([
    adminGetStatisticsOverview(params),
    adminGetCourtStatistics(params),
    adminGetTimeSlotStatistics({ ...params, limit: 12 }),
    adminGetUserStatistics({ ...params, limit: 10 }),
  ]);
  statisticsOverview.value = overview.data;
  courtStatistics.value = courtsResult.data.items;
  timeSlotStatistics.value = slotsResult.data.items;
  userStatistics.value = usersResult.data.items;
}

async function refreshStatistics() {
  loading.value = true;
  try {
    await loadStatistics();
    appliedRange.value = { ...statsRange.value }; refreshKey.value++;
    await router.replace({ query: { date_from: appliedRange.value.date_from, date_to: appliedRange.value.date_to } });
    setSuccess("统计已刷新");
  } catch (error) {
    setError(error, "统计数据加载失败");
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadStatistics();
  } catch (error) { setError(error, "数据加载失败"); }
  finally { loading.value = false; }
});
</script>

<template>
  <section class="page-header"><h1>运营总览</h1><p>查看预约、场地和用户活跃情况。</p></section>
  <el-card shadow="never" class="admin-shell element-admin">
    <section v-loading="loading" class="admin-section">
      <el-form inline class="element-filter">
        <el-form-item label="开始日期">
          <el-date-picker v-model="statsRange.date_from" type="date" value-format="YYYY-MM-DD" :clearable="false" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="statsRange.date_to" type="date" value-format="YYYY-MM-DD" :clearable="false" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="refreshStatistics">刷新统计</el-button>
        </el-form-item>
      </el-form>

      <OperationsDashboard :date-from="appliedRange.date_from" :date-to="appliedRange.date_to" :refresh-key="refreshKey" />
      <p class="muted-text">预订率按已预约时长 / 可预约时长计算，包含待支付占用；容量按当前启用场地和营业规则计算，扣除当前有效维护时长，不代表实际到场率。</p>
      <el-row v-if="statisticsOverview" :gutter="14" class="element-grid">
        <el-col :xs="24" :sm="12" :lg="4">
          <el-statistic title="预约总量" :value="statisticsOverview.reservation_total" />
        </el-col>
        <el-col :xs="24" :sm="12" :lg="4">
          <el-statistic title="今日预约" :value="statisticsOverview.today_reservations" />
        </el-col>
        <el-col :xs="24" :sm="12" :lg="4">
          <el-statistic title="活跃用户" :value="statisticsOverview.active_users" />
        </el-col>
        <el-col :xs="24" :sm="12" :lg="4">
          <el-statistic title="场地预订率" :value="statisticsOverview.utilization_rate" suffix="%" />
        </el-col>
        <el-col :xs="24" :sm="12" :lg="4">
          <el-statistic title="启用场地" :value="statisticsOverview.enabled_courts" />
        </el-col>
        <el-col :xs="24" :sm="12" :lg="4">
          <el-statistic title="已结束预约" :value="statisticsOverview.completed_reservations" />
        </el-col>
      </el-row>

      <el-row :gutter="16" class="element-grid">
        <el-col :xs="24" :lg="12">
          <el-card shadow="never" class="panel-card">
            <template #header><strong>场地预订率</strong></template>
            <el-table :data="usageTable" empty-text="暂无场地统计数据">
              <el-table-column label="场地" min-width="150">
                <template #default="{ row }">{{ row.court_no }} {{ row.court_name }}</template>
              </el-table-column>
              <el-table-column prop="active_count" label="有效预约" width="100" />
              <el-table-column label="预订率" min-width="180">
                <template #default="{ row }">
                  <el-progress :percentage="row.progress" />
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="12">
          <el-card shadow="never" class="panel-card">
            <template #header><strong>热门时间段</strong></template>
            <el-table :data="timeSlotStatistics" empty-text="暂无时间段统计数据">
              <el-table-column prop="time_slot" label="时间段" />
              <el-table-column prop="reservation_count" label="预约次数" width="120" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" class="panel-card">
        <template #header><strong>用户活跃度</strong></template>
        <el-table :data="userStatistics" empty-text="暂无用户统计数据" stripe>
          <el-table-column label="用户" min-width="130">
            <template #default="{ row }">{{ row.nickname || row.username }}</template>
          </el-table-column>
          <el-table-column prop="reservation_count" label="预约总数" />
          <el-table-column prop="confirmed_count" label="已确认" />
          <el-table-column prop="completed_count" label="已结束" />
          <el-table-column prop="canceled_count" label="已取消" />
          <el-table-column prop="last_reserve_date" label="最近预约日期" min-width="130" />
        </el-table>
      </el-card>
    </section>

  </el-card>
  <ServiceHealth />
</template>
