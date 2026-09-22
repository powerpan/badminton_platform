<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { getAnnouncement, type Announcement } from "../api/announcement";

const route = useRoute();
const announcement = ref<Announcement | null>(null);
const loading = ref(false);
const errorMessage = ref("");

async function loadAnnouncement() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const announcementId = Number(route.params.id);
    if (!Number.isFinite(announcementId)) throw new Error("公告ID不合法");
    const response = await getAnnouncement(announcementId);
    announcement.value = response.data;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "公告详情加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(loadAnnouncement);
</script>

<template>
  <section class="page-header">
    <h1>{{ announcement?.title || "公告详情" }}</h1>
    <p v-if="announcement">发布时间：{{ announcement.created_at }}</p>
  </section>

  <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />

  <el-card shadow="never" class="panel-card detail-page-card" v-loading="loading">
    <template v-if="announcement">
      <div class="detail-meta">
        <el-tag type="success" effect="plain">场馆公告</el-tag>
        <span>更新于 {{ announcement.updated_at }}</span>
      </div>
      <article class="rich-content">{{ announcement.content }}</article>
      <RouterLink class="inline-action" to="/announcements">返回公告中心</RouterLink>
    </template>
    <el-empty v-else-if="!loading && !errorMessage" description="公告不存在" />
  </el-card>
</template>
