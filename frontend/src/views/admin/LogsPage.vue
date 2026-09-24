<script setup lang="ts">
import { onMounted, ref } from "vue";

import { adminGetOperationLogs, type OperationLog } from "../../api/admin";
import { type PageState, operationDetail, setError, resetPage, changePage } from "./shared";

const loading = ref(false);

async function changeLogPage(page: number) {
  await changePage(logPage.value, page, () => refreshOperationLogs());
}

const operationLogs = ref<OperationLog[]>([]);

const logPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });

const logFilters = ref({
  module: "",
  action: "",
  username: "",
  date_from: "",
  date_to: "",
});

async function loadOperationLogs() {
  const response = await adminGetOperationLogs({
    module: logFilters.value.module || undefined,
    action: logFilters.value.action || undefined,
    username: logFilters.value.username || undefined,
    date_from: logFilters.value.date_from || undefined,
    date_to: logFilters.value.date_to || undefined,
    page: logPage.value.page,
    page_size: logPage.value.page_size,
  });
  operationLogs.value = response.data.items;
  logPage.value.total = response.data.total;
}

async function refreshOperationLogs(reset = false) {
  if (reset) resetPage(logPage.value);
  loading.value = true;
  try {
    await loadOperationLogs();
  } catch (error) {
    setError(error, "日志加载失败");
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadOperationLogs();
  } catch (error) { setError(error, "数据加载失败"); }
  finally { loading.value = false; }
});
</script>

<template>
  <section class="page-header"><h1>操作日志</h1><p>查看后台关键操作记录。</p></section>
  <el-card shadow="never" class="admin-shell element-admin">
    <section v-loading="loading" class="admin-section">
      <el-form inline class="element-filter">
        <el-form-item label="模块">
          <el-select v-model="logFilters.module" clearable class="short-select" @change="refreshOperationLogs(true)">
            <el-option label="用户" value="user" />
            <el-option label="场地" value="court" />
            <el-option label="预约" value="reservation" />
            <el-option label="支付" value="payment" /><el-option label="储值" value="recharge" />
            <el-option label="公告" value="announcement" />
            <el-option label="通知" value="notification" />
            <el-option label="活动" value="event" />
            <el-option label="球友圈" value="community" />
            <el-option label="商城" value="shop" />
            <el-option label="规则" value="config" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作">
          <el-select v-model="logFilters.action" clearable class="short-select" @change="refreshOperationLogs(true)">
            <el-option label="维护占用" value="block" /><el-option label="安排分类" value="classify_block" /><el-option label="释放维护" value="release" /><el-option label="到场记录" value="attendance" /><el-option label="预约改期" value="reschedule" />
            <el-option label="新增" value="create" />
            <el-option label="散客开单" value="walk_in_create" /><el-option label="模拟收款成功" value="mock_confirm" /><el-option label="模拟失败尝试" value="mock_fail" /><el-option label="退款" value="refund" /><el-option label="超时释放" value="expire" />
            <el-option label="修改" value="update" />
            <el-option label="状态调整" value="status" />
            <el-option label="角色调整" value="role" />
            <el-option label="会员调整" value="member" />
            <el-option label="取消" value="cancel" />
            <el-option label="隐藏" value="hide" />
            <el-option label="公告通知" value="broadcast" />
            <el-option label="完成" value="complete" />
            <el-option label="refund_reject" value="refund_reject" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作人"><el-input v-model="logFilters.username" placeholder="用户名" @keyup.enter="refreshOperationLogs(true)" /></el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="logFilters.date_from" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="logFilters.date_to" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item><el-button type="primary" @click="refreshOperationLogs(true)">查询日志</el-button></el-form-item>
      </el-form>

      <el-table :data="operationLogs" empty-text="暂无操作日志" stripe>
        <el-table-column prop="created_at" label="时间" min-width="170" />
        <el-table-column label="操作人" min-width="120"><template #default="{ row }">{{ row.username || "-" }}</template></el-table-column>
        <el-table-column prop="module" label="模块" width="110" />
        <el-table-column prop="action" label="操作" width="110" />
        <el-table-column label="目标" min-width="130"><template #default="{ row }">{{ row.target_type || "-" }} #{{ row.target_id || "-" }}</template></el-table-column>
        <el-table-column label="详情" min-width="260"><template #default="{ row }">{{ operationDetail(row.detail) }}</template></el-table-column>
        <el-table-column label="IP" min-width="130"><template #default="{ row }">{{ row.ip || "-" }}</template></el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="logPage.page" :page-size="logPage.page_size" :total="logPage.total" layout="prev, pager, next, total" @current-change="changeLogPage" />
    </section>

  </el-card>
</template>
