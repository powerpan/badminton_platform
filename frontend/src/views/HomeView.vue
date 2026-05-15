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

  <el-row :gutter="18" class="element-grid">
    <el-col :xs="24" :lg="12">
      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="card-header-row">
            <strong>服务状态</strong>
            <el-tag v-if="health" type="success" effect="plain">在线</el-tag>
          </div>
        </template>
        <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />
        <el-skeleton v-else-if="!health" :rows="3" animated />
        <div v-else class="status-grid">
          <div class="status-item">
            <span>API</span>
            <el-tag :type="health.api.status === 'ok' ? 'success' : 'danger'">{{ health.api.status }}</el-tag>
          </div>
          <div class="status-item">
            <span>MySQL</span>
            <el-tag :type="health.mysql.status === 'ok' ? 'success' : 'danger'">{{ health.mysql.status }}</el-tag>
          </div>
          <div class="status-item">
            <span>Redis</span>
            <el-tag :type="health.redis.status === 'ok' ? 'success' : 'danger'">{{ health.redis.status }}</el-tag>
          </div>
        </div>
      </el-card>
    </el-col>

    <el-col :xs="24" :lg="12">
      <el-card shadow="never" class="panel-card">
        <template #header>
          <div class="card-header-row">
            <strong>场馆公告</strong>
            <el-tag effect="plain">{{ announcements.length }} 条</el-tag>
          </div>
        </template>
        <el-empty v-if="announcements.length === 0" description="暂无公告" />
        <el-timeline v-else>
          <el-timeline-item v-for="announcement in announcements" :key="announcement.id">
            <strong>{{ announcement.title }}</strong>
            <p class="muted-text">{{ announcement.content }}</p>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </el-col>
  </el-row>
</template>
