<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Bell, ArrowDown, MoreFilled, House, Calendar, Tickets, User, ArrowRight } from "@element-plus/icons-vue";
import { useAuthStore } from "./stores/auth";
import { useNotificationStore } from "./stores/notification";

const authStore = useAuthStore();
const notificationStore = useNotificationStore();
const route = useRoute();
const router = useRouter();
const moreVisible = ref(false);
const adminMode = computed(() => Boolean(route.meta.requiresAdmin));
const memberName = computed(() => authStore.user?.nickname || authStore.user?.username || "会员中心");
const customerNav = [
  { label: "首页", to: "/" }, { label: "场地预订", to: "/courts" },
  { label: "我的预订", to: "/reservations" }, { label: "活动赛事", to: "/events" },
  { label: "球友圈", to: "/community" }, { label: "商城", to: "/shop" },
];
const customerMobileNav = [
  { label: "首页", to: "/", icon: House }, { label: "预订", to: "/courts", icon: Calendar },
  { label: "订单", to: "/reservations", icon: Tickets }, { label: "我的", to: "/profile", icon: User },
];
const mainNav = computed(() => authStore.isStaff ? [
  { label: authStore.roleLabel, to: authStore.homePath }, { label: "球馆公告", to: "/announcements" },
  { label: "活动赛事", to: "/events" }, { label: "球友圈", to: "/community" }, { label: "商城", to: "/shop" },
] : customerNav);
const mobileNav = computed(() => authStore.isStaff ? [
  { label: "工作台", to: authStore.homePath, icon: Calendar }, { label: "公告", to: "/announcements", icon: House },
  { label: "通知", to: "/notifications", icon: Bell }, { label: "账号", to: "/profile", icon: User },
] : customerMobileNav);
const extraNav = computed(() => [...mainNav.value.slice(authStore.isStaff ? 1 : 3),
  ...(!authStore.isStaff ? [{ label: '商城订单', to: '/shop/orders' }, { label: '球馆公告', to: '/announcements' }] : []),
  { label: '预约帮助', to: '/help' }]);
const adminGroups = [
  { label: "球馆运营", links: [
    { label: "运营总览", to: "/admin/overview" }, { label: "预约管理", to: "/admin/reservations" },
    { label: "场地管理", to: "/admin/courts" }, { label: "用户管理", to: "/admin/users" }, { label: "会员储值", to: "/admin/recharges" }, { label: "交易流水", to: "/admin/transactions" },
  ] },
  { label: "内容与服务", links: [
    { label: "公告管理", to: "/admin/announcements" }, { label: "活动管理", to: "/admin/events" },
    { label: "球友圈管理", to: "/admin/community" }, { label: "商城商品", to: "/admin/shop/products" },
    { label: "商城订单", to: "/admin/shop/orders" }, { label: "通知管理", to: "/admin/notifications" },
  ] },
  { label: "设置", links: [
    { label: "规则配置", to: "/admin/configs" }, { label: "操作日志", to: "/admin/logs" },
  ] },
];
async function logout() {
  try {
    await authStore.logout();
  } finally {
    authStore.clearSession();
    notificationStore.clear();
    moreVisible.value = false;
    await router.push("/login");
  }
}
async function accountCommand(command: string) {
  if (command === "logout") await logout();
  else await router.push(command);
}
async function refreshNotifications() {
  if (!authStore.isLoggedIn) { notificationStore.clear(); return; }
  try { await notificationStore.fetchUnreadCount(); }
  catch { notificationStore.clear(); }
}
onMounted(async () => {
  if (authStore.token) {
    try { await authStore.fetchProfile(); }
    catch { if (!localStorage.getItem("bf_token")) authStore.clearSession(); }
  }
  await refreshNotifications();
});
watch(() => authStore.isLoggedIn, refreshNotifications);
watch(() => route.fullPath, () => { moreVisible.value = false; });
</script>

<template>
  <div class="product-shell" :class="{ 'is-admin': adminMode, 'is-booking': route.name === 'courts' }">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <header class="club-header">
      <RouterLink :to="adminMode ? '/admin/overview' : '/'" class="club-brand" aria-label="BF 羽毛球馆首页">
        <img src="/favicon.svg?v=2" alt="" width="34" height="40" /><strong>BF 羽毛球馆</strong>
      </RouterLink>
      <nav v-if="!adminMode" class="club-nav" aria-label="主导航">
        <RouterLink v-for="item in mainNav" :key="item.to" :to="item.to">{{ item.label }}</RouterLink>
      </nav>
      <span v-else class="admin-header-label">球馆管理</span>
      <div class="club-account">
        <RouterLink v-if="authStore.isLoggedIn" class="notification-button" to="/notifications" aria-label="通知中心">
          <Bell /><span v-if="notificationStore.unreadCount" class="notification-badge">{{ Math.min(notificationStore.unreadCount, 99) }}</span>
        </RouterLink>
        <el-dropdown v-if="authStore.isLoggedIn" trigger="click" @command="accountCommand">
          <button class="account-button" aria-label="账户菜单"><span class="member-avatar">{{ memberName.slice(0, 1) }}</span><span class="account-text">{{ adminMode ? memberName : authStore.isStaff ? authStore.roleLabel : '会员中心' }}</span><ArrowDown /></button>
          <template #dropdown><el-dropdown-menu>
            <el-dropdown-item command="/profile">{{ authStore.isStaff ? "账号资料" : "会员中心" }}</el-dropdown-item>
            <el-dropdown-item v-if="authStore.canConsume" command="/shop/orders">商城订单</el-dropdown-item>
            <el-dropdown-item v-if="authStore.isAdmin" :command="adminMode ? '/' : '/admin/overview'">{{ adminMode ? '返回用户端' : '进入管理端' }}</el-dropdown-item>
            <el-dropdown-item v-if="authStore.canFrontdesk" command="/frontdesk">前台工作台</el-dropdown-item>
            <el-dropdown-item v-if="authStore.canMaintenance" command="/maintenance">维修安排</el-dropdown-item>
            <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu></template>
        </el-dropdown>
        <RouterLink v-else class="guest-login" :to="{ name: 'login', query: { redirect: route.fullPath } }">登录 / 注册</RouterLink>
        <button class="more-button" aria-label="更多导航" :aria-expanded="moreVisible" @click="moreVisible = true"><MoreFilled /></button>
      </div>
    </header>
    <aside v-if="adminMode" class="admin-sidebar">
      <nav aria-label="后台导航">
        <div v-for="group in adminGroups" :key="group.label" class="admin-nav-group"><p>{{ group.label }}</p>
          <RouterLink v-for="item in group.links" :key="item.to" :to="item.to">{{ item.label }}</RouterLink>
        </div>
      </nav>
      <RouterLink to="/" class="admin-back-link">返回用户端<ArrowRight /></RouterLink>
    </aside>
    <main id="main-content" class="club-main" tabindex="-1"><RouterView /></main>
    <footer v-if="!adminMode" class="club-footer"><span>BF 羽毛球馆</span><RouterLink to="/help">预约帮助</RouterLink></footer>
    <nav v-if="!adminMode" class="mobile-bottom-nav" aria-label="手机主导航">
      <RouterLink v-for="item in mobileNav" :key="item.to" :to="item.to"><component :is="item.icon" /><span>{{ item.label }}</span></RouterLink>
    </nav>
    <el-drawer v-model="moreVisible" :with-header="false" size="min(330px, 100vw)" class="navigation-drawer" aria-label="更多导航">
      <div class="drawer-heading"><h2>{{ adminMode ? '球馆管理' : '更多服务' }}</h2><el-button @click="moreVisible = false">关闭</el-button></div>
      <nav v-if="adminMode" class="drawer-navigation"><template v-for="group in adminGroups" :key="group.label"><p>{{ group.label }}</p><RouterLink v-for="item in group.links" :key="item.to" :to="item.to">{{ item.label }}<ArrowRight /></RouterLink></template><RouterLink to="/">返回用户端<ArrowRight /></RouterLink></nav>
      <nav v-else class="drawer-navigation">
        <RouterLink v-for="item in extraNav" :key="item.to" :to="item.to">{{ item.label }}<ArrowRight /></RouterLink>
        <RouterLink v-if="authStore.isAdmin" to="/admin/overview">进入管理端<ArrowRight /></RouterLink>
      </nav>
      <el-button v-if="authStore.isLoggedIn" class="drawer-logout" @click="logout">退出登录</el-button>
    </el-drawer>
  </div>
</template>
