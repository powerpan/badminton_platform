<script setup lang="ts">
import { onMounted, ref } from "vue";

import { getHealth, type HealthResponse } from "../api/health";

const health = ref<HealthResponse | null>(null);
const errorMessage = ref("");

onMounted(async () => {
  try {
    const response = await getHealth();
    health.value = response.data;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "健康检查失败";
  }
});
</script>

<template>
  <section class="page-header">
    <p class="eyebrow">开发框架</p>
    <h1>BF羽毛球馆管理平台</h1>
    <p>当前先完成前后端基础骨架，后续按“认证、场地、预约、后台管理”的顺序接入业务。</p>
  </section>

  <section class="panel">
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
  </section>
</template>
