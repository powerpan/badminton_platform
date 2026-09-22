<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { Calendar, ArrowRight } from "@element-plus/icons-vue";
import { getReservationSummary, type Reservation, type ReservationSummary } from "../api/reservation";
import { useAuthStore } from "../stores/auth";

const props = defineProps<{ detailActions?: boolean }>();
const emit = defineEmits<{ open: [reservation: Reservation] }>();
const auth = useAuthStore();
const summary = ref<ReservationSummary | null>(null);
const loading = ref(false);
const error = ref("");
let version = 0;
let timer: ReturnType<typeof setInterval> | undefined;

async function refresh() {
  if (!auth.isLoggedIn) return;
  const request = ++version;
  loading.value = true;
  try {
    const response = await getReservationSummary();
    if (request !== version) return;
    summary.value = response.data;
    error.value = "";
  } catch {
    if (request === version) error.value = "预约信息暂时无法加载";
  } finally {
    if (request === version) loading.value = false;
  }
}
function refreshVisible() { if (!document.hidden) void refresh(); }
onMounted(() => {
  void refresh();
  timer = setInterval(refreshVisible, 30000);
  document.addEventListener("visibilitychange", refreshVisible);
});
onUnmounted(() => {
  version++;
  clearInterval(timer);
  document.removeEventListener("visibilitychange", refreshVisible);
});
defineExpose({ refresh });
</script>

<template>
  <section class="booking-agenda" aria-label="接下来的预约" :aria-busy="loading">
    <div v-if="summary?.pending" class="agenda-pending">
      <div><strong>{{ summary.pending_count }} 笔预约待支付</strong><span>请在截止前完成支付，超时将释放场地。</span></div>
      <el-button v-if="props.detailActions" type="warning" @click="emit('open', summary.pending)">查看待支付预约</el-button>
      <RouterLink v-else to="/reservations?status=pending" class="text-action">去支付 <ArrowRight /></RouterLink>
    </div>
    <div class="agenda-next">
      <div class="agenda-label"><Calendar /><h2>下一场预约</h2></div>
      <div v-if="!auth.isLoggedIn" class="agenda-info"><strong>登录后，查看你的球场安排</strong><span>预约记录和会员权益随时可查。</span></div>
      <div v-else-if="error" class="agenda-info" role="status"><strong>{{ error }}</strong><button class="text-action" @click="refresh">重新加载</button></div>
      <div v-else-if="loading && !summary" class="agenda-info"><span>正在查看你的安排…</span></div>
      <div v-else-if="summary?.upcoming" class="agenda-info">
        <strong>{{ summary.upcoming.court_name }}</strong>
        <span>{{ summary.upcoming.reserve_date }} · {{ summary.upcoming.start_time }}–{{ summary.upcoming.end_time }}</span>
      </div>
      <div v-else class="agenda-info agenda-empty"><strong>还没有接下来的安排</strong><span>先选好时间，再约上球友。</span></div>
      <el-button v-if="summary?.upcoming && props.detailActions" type="primary" @click="emit('open', summary.upcoming)">查看预约</el-button>
      <RouterLink v-else :to="summary?.upcoming ? '/reservations?status=confirmed' : '/courts'" class="solid-action agenda-action">
        {{ summary?.upcoming ? "查看预约" : "去选场" }}<ArrowRight />
      </RouterLink>
    </div>
  </section>
</template>
