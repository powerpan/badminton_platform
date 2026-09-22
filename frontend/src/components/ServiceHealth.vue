<script setup lang="ts">
import { onMounted, ref } from "vue";
import { getHealth, type HealthResponse } from "../api/health";
const health = ref<HealthResponse | null>(null);
const loading = ref(false);
const error = ref("");
async function refresh() {
  loading.value = true;
  error.value = "";
  try { health.value = (await getHealth()).data; }
  catch { error.value = "服务检查失败，请稍后重试。"; }
  finally { loading.value = false; }
}
onMounted(refresh);
</script>
<template>
  <section class="service-health" aria-label="服务状态">
    <strong>服务状态</strong>
    <span v-if="error" role="status">{{ error }}</span>
    <template v-else-if="health">
      <el-tag v-for="key in (['api', 'mysql', 'redis'] as const)" :key="key" :type="health[key].status === 'ok' ? 'success' : 'danger'" effect="plain">{{ key.toUpperCase() }} · {{ health[key].status === 'ok' ? '正常' : '异常' }}</el-tag>
    </template>
    <el-button link type="primary" :loading="loading" @click="refresh">重新检查</el-button>
  </section>
</template>
<style scoped>
.service-health { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--line); font-size: 13px; }
.service-health strong { margin-right: 6px; }
</style>
