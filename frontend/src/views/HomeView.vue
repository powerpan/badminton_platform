<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ArrowRight, Trophy, ChatDotRound } from "@element-plus/icons-vue";
import { getAnnouncements, type Announcement } from "../api/announcement";
import { getVenueInfo } from "../api/court";
import BookingAgenda from "../components/BookingAgenda.vue";

const announcements = ref<Announcement[]>([]);
const businessHours = ref("加载中…");
const loading = ref(true);
const error = ref("");
async function loadAnnouncements() {
  loading.value = true;
  error.value = "";
  try { announcements.value = (await getAnnouncements({ page_size: 3 })).data.items; }
  catch { error.value = "公告暂时无法加载，请稍后重试。"; }
  finally { loading.value = false; }
}
onMounted(() => {
  void loadAnnouncements();
  void getVenueInfo().then(({ data }) => {
    businessHours.value = `${data.business_start_time}–${data.business_end_time}`;
  }).catch(() => { businessHours.value = "暂时无法获取"; });
});
</script>

<template>
  <div class="venue-home">
    <section class="venue-hero">
      <div class="hero-copy">
        <h1>把时间留给<br />下一场好球。</h1>
        <p>选一块场地，约一场尽兴的球。</p>
        <div class="hero-actions">
          <RouterLink to="/courts" class="solid-action">预订场地</RouterLink>
          <RouterLink to="/reservations" class="text-action"><span class="desktop-copy">查看</span>我的预订<ArrowRight /></RouterLink>
        </div>
      </div>
      <figure class="venue-photo">
        <img src="/venue/bf-hall.png" alt="BF 羽毛球馆场地示意：绿色球场与室内球网" fetchpriority="high" width="1659" height="948" />
        <figcaption>场馆示意图</figcaption>
      </figure>
      <dl class="venue-facts">
        <div><dt>营业时间</dt><dd>{{ businessHours }}</dd></div>
        <div><dt>预约方式</dt><dd>在线选时 · 余额支付</dd></div>
      </dl>
    </section>
    <BookingAgenda />
    <div class="home-bottom">
      <section class="home-announcements">
        <div class="home-section-heading"><h2>球馆公告</h2><RouterLink to="/announcements" class="text-action">全部公告<ArrowRight /></RouterLink></div>
        <p v-if="loading" class="quiet-state">正在加载球馆消息…</p>
        <div v-else-if="error" class="quiet-state" role="status">{{ error }}<button class="text-action" @click="loadAnnouncements">重试</button></div>
        <p v-else-if="!announcements.length" class="quiet-state">暂时没有新公告。出发前，可以查看预约帮助。</p>
        <RouterLink v-for="item in announcements" :key="item.id" :to="`/announcements/${item.id}`" class="announcement-line">
          <strong>{{ item.title }}</strong><p>{{ item.content.replace(/\s+/g, ' ') }}</p><time>{{ item.created_at.slice(5, 10).replace('-', '.') }}</time>
        </RouterLink>
      </section>
      <section class="home-discover">
        <h2>场上见</h2>
        <RouterLink to="/events" class="discover-line"><Trophy /><div><strong>活动赛事</strong><p>看看近期活动，找到一起上场的伙伴。</p></div><ArrowRight /></RouterLink>
        <RouterLink to="/community" class="discover-line"><ChatDotRound /><div><strong>球友圈</strong><p>分享打球日常，和球友聊聊这一场。</p></div><ArrowRight /></RouterLink>
      </section>
    </div>
  </div>
</template>
