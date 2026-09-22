<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import {
  cancelEventRegistration,
  getEvent,
  registerEvent,
  type ClubEvent,
} from "../api/event";
import { useAuthStore } from "../stores/auth";
import EventImage from "../components/EventImage.vue";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const event = ref<ClubEvent | null>(null);
const loading = ref(false);
const errorMessage = ref("");

const eventId = computed(() => Number(route.params.id));

function dateText(value: string | undefined) {
  return value ? value.slice(0, 16) : "-";
}

function registrationStateText(item: ClubEvent) {
  if (item.is_registered) return "已报名";
  if (item.registered_count >= item.capacity) return "名额已满";
  if (!item.can_register) return "暂不可报名";
  return "可报名";
}

async function loadEvent() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await getEvent(eventId.value);
    event.value = response.data;
  } catch (error) {
    event.value = null;
    errorMessage.value = error instanceof Error ? error.message : "活动详情加载失败";
  } finally {
    loading.value = false;
  }
}

async function submitRegister() {
  if (!authStore.isLoggedIn) {
    await router.push({ name: "login", query: { redirect: route.fullPath } });
    return;
  }
  loading.value = true;
  try {
    await registerEvent(eventId.value);
    await loadEvent();
    ElMessage.success("报名成功");
  } catch (error) {
    const failure = error instanceof Error ? error.message : "报名失败";
    await loadEvent();
    ElMessage.error(failure);
  } finally {
    loading.value = false;
  }
}

async function submitCancel() {
  loading.value = true;
  try {
    await cancelEventRegistration(eventId.value);
    await loadEvent();
    ElMessage.success("报名已取消");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "取消报名失败");
  } finally {
    loading.value = false;
  }
}

onMounted(loadEvent);
</script>

<template>
  <section class="page-header">
    <h1>{{ event?.title || "活动详情" }}</h1>
    <p>查看活动时间、地点和报名状态。</p>
  </section>

  <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />

  <el-card v-if="event" shadow="never" class="panel-card detail-page-card" v-loading="loading">
    <div class="detail-layout">
      <article class="detail-content">
        <EventImage :title="event.title" detail />
        <el-tag :type="event.is_registered ? 'warning' : 'success'" effect="plain">
          {{ registrationStateText(event) }}
        </el-tag>
        <h2>{{ event.title }}</h2>
        <p>{{ event.content }}</p>
      </article>
      <aside class="detail-side">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="地点">{{ event.location }}</el-descriptions-item>
          <el-descriptions-item label="开始">{{ dateText(event.start_at) }}</el-descriptions-item>
          <el-descriptions-item label="结束">{{ dateText(event.end_at) }}</el-descriptions-item>
          <el-descriptions-item label="报名截止">{{ dateText(event.registration_deadline) }}</el-descriptions-item>
          <el-descriptions-item label="报名人数">{{ event.registered_count }}/{{ event.capacity }}</el-descriptions-item>
        </el-descriptions>
        <el-button
          v-if="!event.is_registered"
          type="primary"
          size="large"
          :disabled="!event.can_register"
          :loading="loading"
          @click="submitRegister"
        >
          报名活动
        </el-button>
        <el-button v-else type="warning" size="large" plain :loading="loading" @click="submitCancel">
          取消报名
        </el-button>
      </aside>
    </div>
  </el-card>
</template>

<style scoped>
.detail-side :deep(.el-descriptions__table) {
  min-width: 0;
  width: 100%;
  table-layout: fixed;
}
.detail-side :deep(.el-descriptions__label) { width: 88px; }
.detail-side :deep(.el-descriptions__cell) {
  white-space: normal;
  overflow-wrap: anywhere;
}
</style>
