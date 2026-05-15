import { createRouter, createWebHistory } from "vue-router";

import AdminDashboard from "../views/AdminDashboard.vue";
import AnnouncementDetailView from "../views/AnnouncementDetailView.vue";
import AnnouncementsView from "../views/AnnouncementsView.vue";
import CourtsView from "../views/CourtsView.vue";
import ForgotPasswordView from "../views/ForgotPasswordView.vue";
import HelpCenterView from "../views/HelpCenterView.vue";
import HomeView from "../views/HomeView.vue";
import LoginView from "../views/LoginView.vue";
import NotificationsView from "../views/NotificationsView.vue";
import ProfileView from "../views/ProfileView.vue";
import ReservationsView from "../views/ReservationsView.vue";
import RegisterView from "../views/RegisterView.vue";
import { useAuthStore } from "../stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: HomeView },
    { path: "/announcements", name: "announcements", component: AnnouncementsView },
    { path: "/announcements/:id", name: "announcement-detail", component: AnnouncementDetailView },
    { path: "/help", name: "help", component: HelpCenterView },
    { path: "/login", name: "login", component: LoginView },
    { path: "/register", name: "register", component: RegisterView },
    { path: "/forgot-password", name: "forgot-password", component: ForgotPasswordView },
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
      name: "admin",
      component: AdminDashboard,
      meta: { requiresAuth: true, requiresAdmin: true },
    },
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

  if ((to.name === "login" || to.name === "register" || to.name === "forgot-password") && authStore.isLoggedIn) {
    return { name: "home" };
  }

  return true;
});

export default router;
