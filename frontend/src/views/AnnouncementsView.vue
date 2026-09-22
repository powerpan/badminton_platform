<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getAnnouncements, type Announcement } from "../api/announcement";

const announcements = ref<Announcement[]>([]);
const page = ref({ page: 1, page_size: 8, total: 0 });
const loading = ref(false);
const errorMessage = ref("");

function announcementSummary(content: string) {
  const text = content.replace(/\s+/g, " ").trim();
  return text.length > 120 ? `${text.slice(0, 120)}...` : text;
}

async function loadAnnouncements() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await getAnnouncements({
      page: page.value.page,
      page_size: page.value.page_size,
    });
    announcements.value = response.data.items;
    page.value.total = response.data.total;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "公告加载失败";
  } finally {
    loading.value = false;
  }
}

async function changePage(nextPage: number) {
  page.value.page = nextPage;
  await loadAnnouncements();
}

onMounted(loadAnnouncements);
</script>

<template>
  <section class="page-header">
    <h1>公告中心</h1>
    <p>查看场馆营业调整、活动说明和重要服务提醒。</p>
  </section>

  <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />

  <el-card shadow="never" class="panel-card list-page-card" v-loading="loading">
    <el-empty v-if="announcements.length === 0 && !loading" description="暂无公告" />
    <div v-else class="announcement-list-page">
      <article v-for="announcement in announcements" :key="announcement.id" class="announcement-item">
        <div>
          <span>{{ announcement.created_at }}</span>
          <h2>{{ announcement.title }}</h2>
          <p>{{ announcementSummary(announcement.content) }}</p>
        </div>
        <RouterLink class="inline-action" :to="`/announcements/${announcement.id}`">查看详情</RouterLink>
      </article>
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
