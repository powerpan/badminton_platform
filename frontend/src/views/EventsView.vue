<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getEvents, type ClubEvent } from "../api/event";
import EventImage from "../components/EventImage.vue";

const events = ref<ClubEvent[]>([]);
const page = ref({ page: 1, page_size: 9, total: 0 });
const loading = ref(false);
const errorMessage = ref("");

function dateText(value: string) {
  return value ? value.slice(0, 16) : "-";
}

function capacityText(event: ClubEvent) {
  return `${event.registered_count}/${event.capacity}`;
}

async function loadEvents(reset = false) {
  if (reset) page.value.page = 1;
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await getEvents({ page: page.value.page, page_size: page.value.page_size });
    events.value = response.data.items;
    page.value.total = response.data.total;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "活动加载失败";
  } finally {
    loading.value = false;
  }
}

async function changePage(nextPage: number) {
  page.value.page = nextPage;
  await loadEvents();
}

onMounted(() => loadEvents());
</script>

<template>
  <section class="page-header">
    <h1>活动赛事</h1>
    <p>查看场馆活动、训练赛和报名名额。</p>
  </section>

  <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />

  <el-card shadow="never" class="panel-card list-page-card" v-loading="loading">
    <el-empty v-if="events.length === 0 && !loading" description="暂无活动" />
    <div v-else class="feature-grid event-grid">
      <RouterLink v-for="event in events" :key="event.id" class="feature-card event-card" :to="`/events/${event.id}`">
        <EventImage :title="event.title" />
        <div class="feature-card-head">
          <el-tag type="success" effect="plain">报名 {{ capacityText(event) }}</el-tag>
          <el-tag v-if="event.is_registered" type="warning" effect="plain">已报名</el-tag>
        </div>
        <h2>{{ event.title }}</h2>
        <p>{{ event.content }}</p>
        <dl class="compact-meta">
          <div><dt>地点</dt><dd>{{ event.location }}</dd></div>
          <div><dt>开始</dt><dd>{{ dateText(event.start_at) }}</dd></div>
          <div><dt>截止</dt><dd>{{ dateText(event.registration_deadline) }}</dd></div>
        </dl>
      </RouterLink>
    </div>

    <el-pagination
      class="element-pagination"
      :current-page="page.page"
      :page-size="page.page_size"
      :total="page.total"
      layout="prev, pager, next, total"
      @current-change="changePage"
    />
  </el-card>
</template>

<style scoped>
.event-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; }
.event-card { display: flex; flex-direction: column; gap: 12px; }
.event-card h2 { line-height: 1.5; }
.event-card .compact-meta { margin-top: auto; padding-top: 4px; }
@media (max-width: 1100px) { .event-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .event-grid { grid-template-columns: minmax(0, 1fr); } }
</style>
