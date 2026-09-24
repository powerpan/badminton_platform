<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { getNotifications, type NotificationItem } from "../api/notification";
import { useNotificationStore } from "../stores/notification";

const notificationStore = useNotificationStore();
const notifications = ref<NotificationItem[]>([]);
const page = ref({ page: 1, page_size: 10, total: 0 });
const filter = ref("");
const loading = ref(false);
const errorMessage = ref("");

function categoryLabel(category: string) {
  const map: Record<string, string> = {
    system: "系统",
    reservation: "预约",
    member: "会员",
    announcement: "公告",
    shop: "商城",
    event: "活动",
    community: "球友圈",
  };
  return map[category] || "系统";
}

function categoryTagType(category: string) {
  const map: Record<string, "primary" | "success" | "info" | "warning"> = {
    system: "info",
    reservation: "success",
    member: "warning",
    announcement: "primary",
    shop: "success",
    event: "primary",
    community: "info",
  };
  return map[category] || "info";
}

function sourceLink(notification: NotificationItem) {
  if (notification.source_type === "announcement" && notification.source_id) return `/announcements/${notification.source_id}`;
  if (notification.source_type === "event" && notification.source_id) return `/events/${notification.source_id}`;
  if (notification.source_type === "shop_order") return "/shop/orders";
  if (notification.source_type === "reservation") return "/reservations";
  if (["member", "recharge"].includes(notification.source_type || "")) return "/profile";
  return "";
}

async function loadNotifications(reset = false) {
  if (reset) page.value.page = 1;
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await getNotifications({
      is_read: filter.value || undefined,
      page: page.value.page,
      page_size: page.value.page_size,
    });
    notifications.value = response.data.items;
    page.value.total = response.data.total;
    await notificationStore.fetchUnreadCount();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "通知加载失败";
  } finally {
    loading.value = false;
  }
}

async function changePage(nextPage: number) {
  page.value.page = nextPage;
  await loadNotifications();
}

async function markRead(notification: NotificationItem) {
  if (notification.is_read) return;
  loading.value = true;
  try {
    await notificationStore.markRead(notification.id);
    await loadNotifications();
    ElMessage.success("通知已标记为已读");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "标记已读失败");
  } finally {
    loading.value = false;
  }
}

async function markAllRead() {
  loading.value = true;
  try {
    const result = await notificationStore.markAllRead();
    await loadNotifications();
    ElMessage.success(`已标记 ${result.updated_count} 条通知`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "全部已读失败");
  } finally {
    loading.value = false;
  }
}

onMounted(() => loadNotifications());
</script>

<template>
  <section class="page-header">
    <h1>通知中心</h1>
    <p>查看预约、会员、公告和系统消息。</p>
  </section>

  <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />

  <el-card shadow="never" class="panel-card list-page-card" v-loading="loading">
    <div class="list-toolbar">
      <el-radio-group v-model="filter" @change="() => loadNotifications(true)">
        <el-radio-button :value="''">全部</el-radio-button>
        <el-radio-button :value="'0'">未读</el-radio-button>
        <el-radio-button :value="'1'">已读</el-radio-button>
      </el-radio-group>
      <el-button type="primary" plain :disabled="notificationStore.unreadCount === 0" @click="markAllRead">
        全部已读
      </el-button>
    </div>

    <el-empty v-if="notifications.length === 0 && !loading" description="暂无通知" />
    <div v-else class="notification-list">
      <article
        v-for="notification in notifications"
        :key="notification.id"
        class="notification-item"
        :class="{ unread: !notification.is_read }"
      >
        <div class="notification-main">
          <div class="notification-title">
            <el-tag :type="categoryTagType(notification.category)" effect="plain">
              {{ categoryLabel(notification.category) }}
            </el-tag>
            <h2>{{ notification.title }}</h2>
            <el-tag v-if="!notification.is_read" type="danger" effect="plain">未读</el-tag>
          </div>
          <p>{{ notification.content }}</p>
          <span>{{ notification.created_at }}</span>
        </div>
        <div class="notification-actions">
          <RouterLink v-if="sourceLink(notification)" class="inline-action" :to="sourceLink(notification)">
            查看关联
          </RouterLink>
          <el-button v-if="!notification.is_read" link type="primary" @click="markRead(notification)">标记已读</el-button>
        </div>
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
