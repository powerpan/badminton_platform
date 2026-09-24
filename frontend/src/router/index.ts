import { createRouter, createWebHistory } from "vue-router";

const MaintenanceView = () => import("../views/MaintenanceView.vue");
const FrontdeskView = () => import("../views/FrontdeskView.vue");
const AdminDashboard = () => import("../views/AdminDashboard.vue");
const AnnouncementDetailView = () => import("../views/AnnouncementDetailView.vue");
const AnnouncementsView = () => import("../views/AnnouncementsView.vue");
const CommunityView = () => import("../views/CommunityView.vue");
const CourtsView = () => import("../views/CourtsView.vue");
const EventDetailView = () => import("../views/EventDetailView.vue");
const EventsView = () => import("../views/EventsView.vue");
const ForgotPasswordView = () => import("../views/ForgotPasswordView.vue");
const HelpCenterView = () => import("../views/HelpCenterView.vue");
const HomeView = () => import("../views/HomeView.vue");
const LoginView = () => import("../views/LoginView.vue");
const NotificationsView = () => import("../views/NotificationsView.vue");
const ProfileView = () => import("../views/ProfileView.vue");
const ReservationsView = () => import("../views/ReservationsView.vue");
const RegisterView = () => import("../views/RegisterView.vue");
const ShopOrdersView = () => import("../views/ShopOrdersView.vue");
const ShopView = () => import("../views/ShopView.vue");
import { useAuthStore } from "../stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/frontdesk", name: "frontdesk", component: FrontdeskView, meta: { requiresAuth: true, roles: ["frontdesk", "admin"] } },
    { path: "/maintenance", name: "maintenance", component: MaintenanceView, meta: { requiresAuth: true, roles: ["maintenance", "admin"] } },
    { path: "/", name: "home", component: HomeView },
    { path: "/announcements", name: "announcements", component: AnnouncementsView },
    { path: "/announcements/:id", name: "announcement-detail", component: AnnouncementDetailView },
    { path: "/help", name: "help", component: HelpCenterView },
    { path: "/events", name: "events", component: EventsView },
    { path: "/events/:id", name: "event-detail", component: EventDetailView },
    { path: "/community", name: "community", component: CommunityView },
    { path: "/shop", name: "shop", component: ShopView },
    { path: "/shop/orders", name: "shop-orders", component: ShopOrdersView, meta: { requiresAuth: true, roles: ["user", "admin"] } },
    { path: "/login", name: "login", component: LoginView },
    { path: "/register", name: "register", component: RegisterView },
    { path: "/forgot-password", name: "forgot-password", component: ForgotPasswordView },
    { path: "/courts", name: "courts", component: CourtsView, meta: { requiresAuth: true, roles: ["user", "admin"] } },
    {
      path: "/reservations",
      name: "reservations",
      component: ReservationsView,
      meta: { requiresAuth: true, roles: ["user", "admin"] },
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
    { path: "/admin/recharges", name: "admin-recharges", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "recharges", title: "会员储值" } },
    { path: "/admin/transactions", name: "admin-transactions", component: AdminDashboard, meta: { requiresAuth: true, requiresAdmin: true, adminTab: "transactions", title: "交易流水" } },
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

  if (authStore.token && (!authStore.user || to.meta.requiresAuth)) {
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
    return authStore.homePath;
  }

  if (Array.isArray(to.meta.roles) && !to.meta.roles.includes(authStore.user?.role)) {
    return authStore.homePath;
  }

  if ((to.name === "login" || to.name === "register" || to.name === "forgot-password") && authStore.isLoggedIn) {
    return authStore.homePath;
  }

  return true;
});

export default router;
