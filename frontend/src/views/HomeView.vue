<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getAnnouncements, type Announcement } from "../api/announcement";
import { getHealth, type HealthResponse } from "../api/health";

const health = ref<HealthResponse | null>(null);
const announcements = ref<Announcement[]>([]);
const errorMessage = ref("");

onMounted(async () => {
  try {
    const [healthResponse, announcementResponse] = await Promise.all([
      getHealth(),
      getAnnouncements({ page_size: 5 }),
    ]);
    health.value = healthResponse.data;
    announcements.value = announcementResponse.data.items;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "首页数据加载失败";
  }
});
</script>

<template>
  <section class="page-header">
    <p class="eyebrow">业务版本</p>
    <h1>BF羽毛球馆管理平台</h1>
    <p>当前已接入用户认证、场地时间段、预约闭环和后台基础管理。</p>
  </section>

  <section class="workspace-grid">
    <div class="panel">
    <h2>服务状态</h2>
    <div v-if="health" class="status-grid">
      <div class="status-item">
        <span>API</span>
        <strong>{{ health.api.status }}</strong>
      </div>
      <div class="status-item">
        <span>MySQL</span>
        <strong>{{ health.mysql.status }}</strong>
      </div>
      <div class="status-item">
        <span>Redis</span>
        <strong>{{ health.redis.status }}</strong>
      </div>
    </div>
    <p v-else-if="errorMessage" class="error-text">{{ errorMessage }}</p>
    <p v-else>正在检查后端服务...</p>
    </div>

    <div class="panel">
      <h2>场馆公告</h2>
      <div v-if="announcements.length" class="announcement-list">
        <article v-for="announcement in announcements" :key="announcement.id">
          <strong>{{ announcement.title }}</strong>
          <p>{{ announcement.content }}</p>
        </article>
      </div>
      <p v-else>暂无公告</p>
    </div>
  </section>
</template>
