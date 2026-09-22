<script setup lang="ts">
import { onMounted, ref } from "vue";

import { adminCreateEvent, adminGetEvents, adminUpdateEvent, adminUpdateEventStatus } from "../../api/admin";
import { type ClubEvent } from "../../api/event";
import { type PageState, addHours, confirmAction, setSuccess, setError, resetPage, changePage } from "./shared";

const loading = ref(false);

async function changeEventPage(page: number) {
  await changePage(eventPage.value, page, () => refreshEvents());
}

const events = ref<ClubEvent[]>([]);

const eventPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });

const eventStatus = ref("");

const emptyEventForm = () => ({
  title: "",
  content: "",
  location: "一号场",
  start_at: addHours(48),
  end_at: addHours(50),
  registration_deadline: addHours(24),
  capacity: 20,
  status: 1,
});

const eventForm = ref(emptyEventForm());

const editingEventId = ref<number | null>(null);

const editingEvent = ref<ClubEvent | null>(null);

const eventEditForm = ref(emptyEventForm());

function eventPayload(form: ReturnType<typeof emptyEventForm>) {
  return {
    title: form.title,
    content: form.content,
    location: form.location,
    start_at: form.start_at,
    end_at: form.end_at,
    registration_deadline: form.registration_deadline,
    capacity: form.capacity,
    status: form.status,
  };
}

async function loadEvents() {
  const response = await adminGetEvents({
    status: eventStatus.value || undefined,
    page: eventPage.value.page,
    page_size: eventPage.value.page_size,
  });
  events.value = response.data.items;
  eventPage.value.total = response.data.total;
}

async function refreshEvents(reset = false) {
  if (reset) resetPage(eventPage.value);
  loading.value = true;
  try {
    await loadEvents();
  } catch (error) {
    setError(error, "活动列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function submitEvent() {
  const payload = editingEventId.value ? eventPayload(eventEditForm.value) : eventPayload(eventForm.value);
  loading.value = true;
  try {
    if (editingEventId.value) {
      await adminUpdateEvent(editingEventId.value, payload);
      setSuccess("活动已更新");
    } else {
      await adminCreateEvent(payload);
      createVisible.value = false;
    setSuccess("活动已创建");
    }
    resetEventForm();
    resetPage(eventPage.value);
    await loadEvents();
  } catch (error) {
    setError(error, "保存活动失败");
  } finally {
    loading.value = false;
  }
}

function editEvent(event: ClubEvent) {
  editingEventId.value = event.id;
  editingEvent.value = event;
  eventEditForm.value = {
    title: event.title,
    content: event.content,
    location: event.location,
    start_at: String(event.start_at).slice(0, 16).replace("T", " "),
    end_at: String(event.end_at).slice(0, 16).replace("T", " "),
    registration_deadline: String(event.registration_deadline).slice(0, 16).replace("T", " "),
    capacity: event.capacity,
    status: event.status,
  };
}

function resetEventForm() {
  editingEventId.value = null;
  editingEvent.value = null;
  eventForm.value = emptyEventForm();
  eventEditForm.value = emptyEventForm();
}

async function toggleEventStatus(event: ClubEvent) {
  const nextStatusLabel = event.status === 1 ? "隐藏" : "显示";
  if (!(await confirmAction(`确认${nextStatusLabel}活动《${event.title}》？`))) return;
  loading.value = true;
  try {
    await adminUpdateEventStatus(event.id, event.status === 1 ? 0 : 1);
    await loadEvents();
    setSuccess("活动状态已更新");
  } catch (error) {
    setError(error, "更新活动状态失败");
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadEvents();
  } catch (error) { setError(error, "数据加载失败"); }
  finally { loading.value = false; }
});
const createVisible = ref(false);
</script>

<template>
  <section class="page-header"><h1>活动管理</h1><p>安排活动、报名名额和时间。</p></section>
  <el-card shadow="never" class="admin-shell element-admin">
    <section v-loading="loading" class="admin-section">
      <div class="admin-create-action"><el-button type="primary" @click="createVisible = true">新增活动</el-button></div>
      <el-drawer v-model="createVisible" title="新增活动" size="min(600px, 100vw)" class="admin-edit-drawer">
        <el-form label-position="top" class="element-form admin-grid-form" @submit.prevent="submitEvent">
          <el-form-item label="活动标题"><el-input v-model="eventForm.title" /></el-form-item>
          <el-form-item label="活动地点"><el-input v-model="eventForm.location" /></el-form-item>
          <el-form-item label="开始时间"><el-date-picker v-model="eventForm.start_at" type="datetime" value-format="YYYY-MM-DD HH:mm" /></el-form-item>
          <el-form-item label="结束时间"><el-date-picker v-model="eventForm.end_at" type="datetime" value-format="YYYY-MM-DD HH:mm" /></el-form-item>
          <el-form-item label="报名截止"><el-date-picker v-model="eventForm.registration_deadline" type="datetime" value-format="YYYY-MM-DD HH:mm" /></el-form-item>
          <el-form-item label="容量"><el-input-number v-model="eventForm.capacity" :min="1" :max="9999" /></el-form-item>
          <el-form-item label="状态">
            <el-select v-model="eventForm.status" class="short-select">
              <el-option label="显示" :value="1" />
              <el-option label="隐藏" :value="0" />
            </el-select>
          </el-form-item>
          <el-form-item label="活动内容" class="form-span-2"><el-input v-model="eventForm.content" type="textarea" :rows="4" /></el-form-item>
          <el-form-item><el-button type="primary" native-type="submit">新增活动</el-button></el-form-item>
        </el-form>
      </el-drawer>

      <el-form inline class="element-filter">
        <el-form-item label="状态">
          <el-select v-model="eventStatus" clearable class="short-select" @change="refreshEvents(true)">
            <el-option label="显示" value="1" />
            <el-option label="隐藏" value="0" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table :data="events" empty-text="暂无活动数据" stripe>
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column prop="location" label="地点" min-width="120" />
        <el-table-column prop="start_at" label="开始时间" min-width="160" />
        <el-table-column label="报名" width="100"><template #default="{ row }">{{ row.registered_count }}/{{ row.capacity }}</template></el-table-column>
        <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'" effect="plain">{{ row.status === 1 ? "显示" : "隐藏" }}</el-tag></template></el-table-column>
        <el-table-column label="操作" fixed="right" width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click="editEvent(row)">编辑</el-button>
            <el-button link type="warning" @click="toggleEventStatus(row)">{{ row.status === 1 ? "隐藏" : "显示" }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="eventPage.page" :page-size="eventPage.page_size" :total="eventPage.total" layout="prev, pager, next, total" @current-change="changeEventPage" />
    </section>
    <el-drawer :model-value="Boolean(editingEventId)" :title="`编辑活动：${editingEvent?.title || ''}`" size="min(600px, 100vw)" @close="resetEventForm" class="admin-edit-drawer">
      <el-alert title="隐藏活动会通知已报名用户；容量不能小于当前已报名人数。" type="info" show-icon :closable="false" />
      <el-form label-position="top" class="element-form dialog-form" @submit.prevent="submitEvent">
        <el-form-item label="活动标题"><el-input v-model="eventEditForm.title" /></el-form-item>
        <el-form-item label="活动地点"><el-input v-model="eventEditForm.location" /></el-form-item>
        <el-form-item label="开始时间"><el-date-picker v-model="eventEditForm.start_at" type="datetime" value-format="YYYY-MM-DD HH:mm" /></el-form-item>
        <el-form-item label="结束时间"><el-date-picker v-model="eventEditForm.end_at" type="datetime" value-format="YYYY-MM-DD HH:mm" /></el-form-item>
        <el-form-item label="报名截止"><el-date-picker v-model="eventEditForm.registration_deadline" type="datetime" value-format="YYYY-MM-DD HH:mm" /></el-form-item>
        <el-form-item label="容量"><el-input-number v-model="eventEditForm.capacity" :min="1" :max="9999" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="eventEditForm.status">
            <el-option label="显示" :value="1" />
            <el-option label="隐藏" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="活动内容"><el-input v-model="eventEditForm.content" type="textarea" :rows="5" /></el-form-item>
        <div class="dialog-actions">
          <el-button @click="resetEventForm">取消</el-button>
          <el-button type="primary" :loading="loading" native-type="submit">保存活动</el-button>
        </div>
      </el-form>
    </el-drawer>
  </el-card>
</template>
