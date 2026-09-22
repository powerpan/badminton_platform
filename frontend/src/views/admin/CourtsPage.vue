<script setup lang="ts">
import CourtBlockManager from "../../components/CourtBlockManager.vue";
import { onMounted, ref } from "vue";

import { adminCreateCourt, adminGetCourts, adminUpdateCourt, adminUpdateCourtStatus } from "../../api/admin";
import { type Court } from "../../api/court";
import { type PageState, formatMoney, centsToYuanInput, yuanInputToCents, tagTextToArray, confirmAction, setSuccess, setError, resetPage, changePage } from "./shared";

const loading = ref(false);

async function changeCourtPage(page: number) {
  await changePage(courtPage.value, page, () => refreshCourts());
}

const courts = ref<Court[]>([]);

const courtOptions = ref<Court[]>([]);

const courtPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });

const courtStatus = ref("");

const emptyCourtForm = () => ({
  court_no: "",
  court_name: "",
  description: "",
  price_per_hour_yuan: "120",
  image_url: "/courts/default-court.png",
  tags_text: "空调开放,标准场地",
  capacity: 6,
  status: 1,
});

const courtForm = ref(emptyCourtForm());

const editingCourtId = ref<number | null>(null);

const editingCourt = ref<Court | null>(null);

const courtEditForm = ref(emptyCourtForm());

function courtPayload(form: ReturnType<typeof emptyCourtForm>) {
  return {
    court_no: form.court_no,
    court_name: form.court_name,
    description: form.description,
    status: form.status,
    price_per_hour_cents: yuanInputToCents(form.price_per_hour_yuan),
    image_url: form.image_url,
    tags: tagTextToArray(form.tags_text),
    capacity: form.capacity,
  };
}

async function loadCourts() {
  const response = await adminGetCourts({
    status: courtStatus.value || undefined,
    page: courtPage.value.page,
    page_size: courtPage.value.page_size,
  });
  courts.value = response.data.items;
  courtPage.value.total = response.data.total;
}

async function refreshCourts(reset = false) {
  if (reset) resetPage(courtPage.value);
  loading.value = true;
  try {
    await loadCourts();
  } catch (error) {
    setError(error, "场地列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function submitCourt() {
  const isEdit = Boolean(editingCourtId.value);
  const form = isEdit ? courtEditForm.value : courtForm.value;
  if (isEdit && form.status === 0 && !(await confirmAction("确认停用该场地？如存在未来预约，后端会拒绝停用。"))) return;
  loading.value = true;
  try {
    const payload = courtPayload(form);
    if (editingCourtId.value) {
      await adminUpdateCourt(editingCourtId.value, payload);
      setSuccess("场地已更新");
    } else {
      await adminCreateCourt(payload);
      createVisible.value = false;
    setSuccess("场地已创建");
    }
    resetCourtForm();
    resetPage(courtPage.value);
    courtOptions.value = [];
    await loadCourts();
  } catch (error) {
    setError(error, "保存场地失败");
  } finally {
    loading.value = false;
  }
}

function editCourt(court: Court) {
  editingCourtId.value = court.id;
  editingCourt.value = court;
  courtEditForm.value = {
    court_no: court.court_no,
    court_name: court.court_name,
    description: court.description || "",
    price_per_hour_yuan: centsToYuanInput(court.price_per_hour_cents),
    image_url: court.image_url || "/courts/default-court.png",
    tags_text: court.tags?.join(",") || "",
    capacity: court.capacity || 6,
    status: court.status,
  };
}

function resetCourtForm() {
  editingCourtId.value = null;
  editingCourt.value = null;
  courtForm.value = emptyCourtForm();
  courtEditForm.value = emptyCourtForm();
}

async function toggleCourtStatus(court: Court) {
  const nextStatusLabel = court.status === 1 ? "停用" : "启用";
  if (!(await confirmAction(`确认${nextStatusLabel}场地 ${court.court_no} ${court.court_name}？`))) return;
  loading.value = true;
  try {
    await adminUpdateCourtStatus(court.id, court.status === 1 ? 0 : 1);
    courtOptions.value = [];
    await loadCourts();
    setSuccess("场地状态已更新");
  } catch (error) {
    setError(error, "更新场地状态失败");
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadCourts();
  } catch (error) { setError(error, "数据加载失败"); }
  finally { loading.value = false; }
});
const createVisible = ref(false);
</script>

<template>
  <section class="page-header"><h1>场地管理</h1><p>设置场地资料、价格和开放状态。</p></section>
  <el-card shadow="never" class="admin-shell element-admin">
    <section v-loading="loading" class="admin-section">
      <div class="admin-create-action"><el-button type="primary" @click="createVisible = true">新增场地</el-button></div>
      <el-drawer v-model="createVisible" title="新增场地" size="min(600px, 100vw)" class="admin-edit-drawer">
        <el-form label-position="top" class="element-form" @submit.prevent="submitCourt">
          <el-form-item label="编号"><el-input v-model="courtForm.court_no" /></el-form-item>
          <el-form-item label="名称"><el-input v-model="courtForm.court_name" /></el-form-item>
          <el-form-item label="说明"><el-input v-model="courtForm.description" /></el-form-item>
          <el-form-item label="价格"><el-input v-model="courtForm.price_per_hour_yuan" /></el-form-item>
          <el-form-item label="图片"><el-input v-model="courtForm.image_url" /></el-form-item>
          <el-form-item label="标签"><el-input v-model="courtForm.tags_text" /></el-form-item>
          <el-form-item label="人数"><el-input-number v-model="courtForm.capacity" :min="1" :max="50" /></el-form-item>
          <el-form-item label="状态">
            <el-select v-model="courtForm.status" class="short-select">
              <el-option label="启用" :value="1" />
              <el-option label="停用" :value="0" />
            </el-select>
          </el-form-item>
          <el-form-item><el-button type="primary" native-type="submit">新增场地</el-button></el-form-item>
        </el-form>
      </el-drawer>

      <el-form inline class="element-filter">
        <el-form-item label="状态">
          <el-select v-model="courtStatus" clearable class="short-select" @change="refreshCourts(true)">
            <el-option label="启用" value="1" />
            <el-option label="停用" value="0" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table :data="courts" empty-text="暂无场地数据" stripe>
        <el-table-column prop="court_no" label="编号" width="90" />
        <el-table-column prop="court_name" label="名称" min-width="120" />
        <el-table-column prop="description" label="说明" min-width="180" />
        <el-table-column label="价格" width="120"><template #default="{ row }">{{ formatMoney(row.price_per_hour_cents) }}/小时</template></el-table-column>
        <el-table-column label="标签" min-width="170"><template #default="{ row }">{{ row.tags?.join("，") || "-" }}</template></el-table-column>
        <el-table-column prop="capacity" label="人数" width="80" />
        <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'" effect="plain">{{ row.status === 1 ? "启用" : "停用" }}</el-tag></template></el-table-column>
        <el-table-column label="操作" fixed="right" width="140">
          <template #default="{ row }">
            <el-button link type="primary" @click="editCourt(row)">编辑</el-button>
            <el-button link type="warning" @click="toggleCourtStatus(row)">{{ row.status === 1 ? "停用" : "启用" }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="courtPage.page" :page-size="courtPage.page_size" :total="courtPage.total" layout="prev, pager, next, total" @current-change="changeCourtPage" />
    </section>
    <el-drawer :model-value="Boolean(editingCourtId)" :title="`编辑场地：${editingCourt?.court_name || ''}`" size="min(600px, 100vw)" @close="resetCourtForm" class="admin-edit-drawer">
      <el-alert title="修改场地资料会影响后续展示和新预约价格；历史预约保留创建时的金额快照。" type="info" show-icon :closable="false" />
      <el-form label-position="top" class="element-form dialog-form" @submit.prevent="submitCourt">
        <el-form-item label="场地编号"><el-input v-model="courtEditForm.court_no" /></el-form-item>
        <el-form-item label="场地名称"><el-input v-model="courtEditForm.court_name" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="courtEditForm.description" /></el-form-item>
        <el-form-item label="每小时价格（元）"><el-input v-model="courtEditForm.price_per_hour_yuan" /></el-form-item>
        <el-form-item label="图片路径"><el-input v-model="courtEditForm.image_url" /></el-form-item>
        <el-form-item label="标签"><el-input v-model="courtEditForm.tags_text" /></el-form-item>
        <el-form-item label="容纳人数"><el-input-number v-model="courtEditForm.capacity" :min="1" :max="50" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="courtEditForm.status">
            <el-option label="启用" :value="1" />
            <el-option label="停用" :value="0" />
          </el-select>
        </el-form-item>
        <div class="dialog-actions">
          <el-button @click="resetCourtForm">取消</el-button>
          <el-button type="primary" :loading="loading" native-type="submit">保存场地</el-button>
        </div>
      </el-form>
    </el-drawer>
  </el-card>
  <CourtBlockManager />
</template>
