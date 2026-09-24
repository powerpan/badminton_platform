<script setup lang="ts">
import { computed, defineAsyncComponent } from "vue";
import { useRoute } from "vue-router";
const route = useRoute();
const pages = {
  statistics: defineAsyncComponent(() => import("./admin/StatisticsPage.vue")),
  recharges: defineAsyncComponent(() => import("./admin/RechargesPage.vue")),
  transactions: defineAsyncComponent(() => import("./admin/TransactionsPage.vue")),
  users: defineAsyncComponent(() => import("./admin/UsersPage.vue")),
  courts: defineAsyncComponent(() => import("./admin/CourtsPage.vue")),
  reservations: defineAsyncComponent(() => import("./admin/ReservationsPage.vue")),
  announcements: defineAsyncComponent(() => import("./admin/AnnouncementsPage.vue")),
  notifications: defineAsyncComponent(() => import("./admin/NotificationsPage.vue")),
  events: defineAsyncComponent(() => import("./admin/EventsPage.vue")),
  community: defineAsyncComponent(() => import("./admin/CommunityPage.vue")),
  shopProducts: defineAsyncComponent(() => import("./admin/ProductsPage.vue")),
  shopOrders: defineAsyncComponent(() => import("./admin/OrdersPage.vue")),
  configs: defineAsyncComponent(() => import("./admin/ConfigsPage.vue")),
  logs: defineAsyncComponent(() => import("./admin/LogsPage.vue")),
};
const activePage = computed(() => pages[route.meta.adminTab as keyof typeof pages] || pages.statistics);
</script>

<template><component :is="activePage" :key="String(route.meta.adminTab)" /></template>
