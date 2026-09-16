import { createRouter, createWebHistory } from "vue-router";

import AdminDashboard from "../views/AdminDashboard.vue";
import AnnouncementDetailView from "../views/AnnouncementDetailView.vue";
import AnnouncementsView from "../views/AnnouncementsView.vue";
import CommunityView from "../views/CommunityView.vue";
import CourtsView from "../views/CourtsView.vue";
import EventDetailView from "../views/EventDetailView.vue";
import EventsView from "../views/EventsView.vue";
import HelpCenterView from "../views/HelpCenterView.vue";
import HomeView from "../views/HomeView.vue";
import LoginView from "../views/LoginView.vue";
import NotificationsView from "../views/NotificationsView.vue";
import ProfileView from "../views/ProfileView.vue";
import ReservationsView from "../views/ReservationsView.vue";
import RegisterView from "../views/RegisterView.vue";
import ShopOrdersView from "../views/ShopOrdersView.vue";
import ShopView from "../views/ShopView.vue";
import { useAuthStore } from "../stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: HomeView },
    { path: "/announcements", name: "announcements", component: AnnouncementsView },
    { path: "/announcements/:id", name: "announcement-detail", component: AnnouncementDetailView },
    { path: "/help", name: "help", component: HelpCenterView },
    { path: "/events", name: "events", component: EventsView },
    { path: "/events/:id", name: "event-detail", component: EventDetailView },
    { path: "/community", name: "community", component: CommunityView },
    { path: "/shop", name: "shop", component: ShopView },
    { path: "/shop/orders", name: "shop-orders", component: ShopOrdersView, meta: { requiresAuth: true } },
    { path: "/login", name: "login", component: LoginView },
    { path: "/register", name: "register", component: RegisterView },
    { path: "/courts", name: "courts", component: CourtsView, meta: { requiresAuth: true } },
    {
      path: "/reservations",
      name: "reservations",
      component: ReservationsView,
      meta: { requiresAuth: true },
    },
    { path: "/profile", name: "profile", component: ProfileView, meta: { requiresAuth: true } },
    { path: "/notifications", name: "notifications", component: NotificationsView, meta: { requiresAuth: true } },
    {
      path: "/admin",
      redirect: "/admin/overview",
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: "/admin/overview",
      name: "admin-overview",
      component: AdminDashboard,
      meta: { requiresAuth: true, requiresAdmin: true, adminTab: "statistics", title: "运营总览" },
    },
    { path: "/admin/users", name: "admin-users", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "users", title: "用户管理" } },
    { path: "/admin/courts", name: "admin-courts", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "courts", title: "场地管理" } },
    { path: "/admin/reservations", name: "admin-reservations", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "reservations", title: "预约管理" } },
    { path: "/admin/announcements", name: "admin-announcements", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "announcements", title: "公告管理" } },
    { path: "/admin/notifications", name: "admin-notifications", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "notifications", title: "通知管理" } },
    { path: "/admin/events", name: "admin-events", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "events", title: "活动管理" } },
    { path: "/admin/community", name: "admin-community", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "community", title: "球友圈管理" } },
    { path: "/admin/shop/products", name: "admin-shop-products", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "shopProducts", title: "商城商品" } },
    { path: "/admin/shop/orders", name: "admin-shop-orders", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "shopOrders", title: "商城订单" } },
    { path: "/admin/configs", name: "admin-configs", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "configs", title: "规则配置" } },
    { path: "/admin/logs", name: "admin-logs", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "logs", title: "操作日志" } },
  ],
});

router.beforeEach(async (to) => {
  const authStore = useAuthStore();

  if (authStore.token && !authStore.user) {
    try {
      await authStore.fetchProfile();
    } catch {
      authStore.clearSession();
    }
  }

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    return { name: "login", query: { redirect: to.fullPath } };
  }

  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return { name: "home" };
  }

  if ((to.name === "login" || to.name === "register") && authStore.isLoggedIn) {
    return { name: authStore.isAdmin ? "admin-overview" : "home" };
  }

  return true;
});

export default router;
