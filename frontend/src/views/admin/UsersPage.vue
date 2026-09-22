<script setup lang="ts">
import { onMounted, ref } from "vue";

import { adminCreateUser, adminGetUsers, adminResetUserPassword, adminUpdateUserMember, adminUpdateUserRole, adminUpdateUserStatus } from "../../api/admin";
import { type UserInfo } from "../../api/auth";
import { useAuthStore } from "../../stores/auth";
import { type PageState, formatMoney, yuanDeltaToCents, discountText, memberValidity, confirmAction, setSuccess, setError, resetPage, changePage } from "./shared";

const authStore = useAuthStore();

const loading = ref(false);

async function changeUserPage(page: number) {
  await changePage(userPage.value, page, () => refreshUsers());
}

const users = ref<UserInfo[]>([]);

const userPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });

const userFilters = ref({ role: "", status: "" });

const memberLevelOptions = [
  { value: "normal", label: "普通会员" },
  { value: "silver", label: "银卡会员" },
  { value: "gold", label: "金卡会员" },
  { value: "diamond", label: "钻石会员" },
];

const userForm = ref({
  username: "",
  password: "",
  nickname: "",
  contact: "",
  role: "user",
  status: 1,
});

const editingMemberUser = ref<UserInfo | null>(null);

const memberForm = ref({
  member_level: "normal",
  expires_at: "",
  balance_change_yuan: "0",
  points_change: 0,
  reason: "",
});

const resetUser = ref<UserInfo | null>(null);

const resetPasswordForm = ref({ password: "" });

async function loadUsers() {
  const response = await adminGetUsers({
    role: userFilters.value.role || undefined,
    status: userFilters.value.status || undefined,
    page: userPage.value.page,
    page_size: userPage.value.page_size,
  });
  users.value = response.data.items;
  userPage.value.total = response.data.total;
}

async function refreshUsers(reset = false) {
  if (reset) resetPage(userPage.value);
  loading.value = true;
  try {
    await loadUsers();
  } catch (error) {
    setError(error, "用户列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function submitUser() {
  loading.value = true;
  try {
    await adminCreateUser(userForm.value);
    userForm.value = { username: "", password: "", nickname: "", contact: "", role: "user", status: 1 };
    resetPage(userPage.value);
    await loadUsers();
    createVisible.value = false;
    setSuccess("用户已创建");
  } catch (error) {
    setError(error, "创建用户失败");
  } finally {
    loading.value = false;
  }
}

async function toggleUserStatus(user: UserInfo) {
  const nextStatusLabel = user.status === 1 ? "禁用" : "启用";
  if (!(await confirmAction(`确认${nextStatusLabel}用户 ${user.username}？`))) return;
  loading.value = true;
  try {
    await adminUpdateUserStatus(user.id, user.status === 1 ? 0 : 1);
    await loadUsers();
    setSuccess("用户状态已更新");
  } catch (error) {
    setError(error, "更新用户状态失败");
  } finally {
    loading.value = false;
  }
}

async function changeUserRoleValue(user: UserInfo, roleValue: string | number | boolean) {
  const role = String(roleValue);
  if (role !== user.role && !(await confirmAction(`确认将用户 ${user.username} 的角色修改为 ${role}？`))) return;
  loading.value = true;
  try {
    await adminUpdateUserRole(user.id, role);
    await loadUsers();
    setSuccess("用户角色已更新");
  } catch (error) {
    setError(error, "更新用户角色失败");
    await loadUsers();
  } finally {
    loading.value = false;
  }
}

function editUserMember(user: UserInfo) {
  editingMemberUser.value = user;
  memberForm.value = {
    member_level: user.member.level,
    expires_at: user.member.expires_at || "",
    balance_change_yuan: "0",
    points_change: 0,
    reason: "",
  };
}

function resetMemberForm() {
  editingMemberUser.value = null;
  memberForm.value = { member_level: "normal", expires_at: "", balance_change_yuan: "0", points_change: 0, reason: "" };
}

async function submitMember() {
  if (!editingMemberUser.value) return;
  try {
    const targetUserId = editingMemberUser.value.id;
    const balanceChangeCents = yuanDeltaToCents(memberForm.value.balance_change_yuan);
    const pointsChange = Number(memberForm.value.points_change || 0);
    if (!Number.isFinite(pointsChange)) throw new Error("积分调整格式错误");
    const levelLabel = memberLevelOptions.find((item) => item.value === memberForm.value.member_level)?.label || memberForm.value.member_level;
    const expiresText = memberForm.value.expires_at || "长期有效";
    const balanceText = `${balanceChangeCents >= 0 ? "+" : ""}${(balanceChangeCents / 100).toFixed(2)} 元`;
    const pointsText = `${pointsChange >= 0 ? "+" : ""}${pointsChange} 分`;
    if (!(await confirmAction(`确认调整 ${editingMemberUser.value.username} 的会员账户？\n等级：${levelLabel}\n有效期：${expiresText}\n余额变动：${balanceText}\n积分变动：${pointsText}`))) return;
    loading.value = true;
    await adminUpdateUserMember(targetUserId, {
      member_level: memberForm.value.member_level,
      expires_at: memberForm.value.expires_at || null,
      balance_change_cents: balanceChangeCents,
      points_change: pointsChange,
      reason: memberForm.value.reason.trim() || "后台调整会员账户",
    });
    resetMemberForm();
    await loadUsers();
    if (targetUserId === authStore.user?.id) await authStore.fetchProfile();
    setSuccess("会员账户已更新");
  } catch (error) {
    setError(error, "更新会员账户失败");
  } finally {
    loading.value = false;
  }
}

function resetUserPassword(user: UserInfo) {
  resetUser.value = user;
  resetPasswordForm.value = { password: "" };
}

function resetPasswordDialog() {
  resetUser.value = null;
  resetPasswordForm.value = { password: "" };
}

async function submitResetPassword() {
  if (!resetUser.value || !resetPasswordForm.value.password) return;
  const user = resetUser.value;
  if (!(await confirmAction(`确认重置用户 ${user.username} 的密码？该用户旧登录态会失效。`))) return;
  loading.value = true;
  try {
    await adminResetUserPassword(user.id, resetPasswordForm.value.password);
    resetPasswordDialog();
    setSuccess("用户密码已重置");
  } catch (error) {
    setError(error, "重置密码失败");
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadUsers();
  } catch (error) { setError(error, "数据加载失败"); }
  finally { loading.value = false; }
});
const createVisible = ref(false);
</script>

<template>
  <section class="page-header"><h1>用户管理</h1><p>管理会员资料、余额和账号状态。</p></section>
  <el-card shadow="never" class="admin-shell element-admin">
    <section v-loading="loading" class="admin-section">
      <div class="admin-create-action"><el-button type="primary" @click="createVisible = true">新增用户</el-button></div>
      <el-drawer v-model="createVisible" title="新增用户" size="min(600px, 100vw)" class="admin-edit-drawer">
        <el-form label-position="top" class="element-form" @submit.prevent="submitUser">
          <el-form-item label="用户名"><el-input v-model="userForm.username" /></el-form-item>
          <el-form-item label="密码"><el-input v-model="userForm.password" type="password" show-password /></el-form-item>
          <el-form-item label="昵称"><el-input v-model="userForm.nickname" /></el-form-item>
          <el-form-item label="联系方式"><el-input v-model="userForm.contact" /></el-form-item>
          <el-form-item label="角色">
            <el-select v-model="userForm.role" class="short-select">
              <el-option label="普通用户" value="user" />
              <el-option label="管理员" value="admin" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="userForm.status" class="short-select">
              <el-option label="启用" :value="1" />
              <el-option label="禁用" :value="0" />
            </el-select>
          </el-form-item>
          <el-form-item><el-button type="primary" native-type="submit">新增用户</el-button></el-form-item>
        </el-form>
      </el-drawer>

      <el-form inline class="element-filter">
        <el-form-item label="角色">
          <el-select v-model="userFilters.role" clearable class="short-select" @change="refreshUsers(true)">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="userFilters.status" clearable class="short-select" @change="refreshUsers(true)">
            <el-option label="启用" value="1" />
            <el-option label="禁用" value="0" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table :data="users" empty-text="暂无用户数据" stripe>
        <el-table-column prop="username" label="用户名" min-width="110" />
        <el-table-column prop="nickname" label="昵称" min-width="110" />
        <el-table-column prop="contact" label="联系方式" min-width="130" />
        <el-table-column label="角色" min-width="120">
          <template #default="{ row }">
            <el-select :model-value="row.role" size="small" @change="changeUserRoleValue(row, $event)">
              <el-option label="普通用户" value="user" />
              <el-option label="管理员" value="admin" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="会员" min-width="170">
          <template #default="{ row }">
            <el-tag effect="plain">{{ row.member.level_label }}</el-tag>
            <div class="table-subtext">{{ memberValidity(row.member.expires_at) }} / {{ discountText(row.member.effective_discount_rate) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="余额" min-width="110">
          <template #default="{ row }">{{ formatMoney(row.member.balance_cents) }}</template>
        </el-table-column>
        <el-table-column label="积分" min-width="90">
          <template #default="{ row }">{{ row.member.points }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" effect="plain">{{ row.status === 1 ? "启用" : "禁用" }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="230">
          <template #default="{ row }">
            <el-button link type="warning" @click="toggleUserStatus(row)">{{ row.status === 1 ? "禁用" : "启用" }}</el-button>
            <el-button link type="primary" @click="editUserMember(row)">会员</el-button>
            <el-button link type="danger" @click="resetUserPassword(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="userPage.page" :page-size="userPage.page_size" :total="userPage.total" layout="prev, pager, next, total" @current-change="changeUserPage" />
    </section>
    <el-drawer :model-value="Boolean(editingMemberUser)" title="调整会员" size="min(600px, 100vw)" @close="resetMemberForm" class="admin-edit-drawer">
      <el-alert title="余额和积分填写本次增减值，正数为增加，负数为扣减，不是账户最终值。" type="info" show-icon :closable="false" />
      <el-form label-position="top" class="element-form dialog-form" @submit.prevent="submitMember">
        <el-form-item label="会员等级">
          <el-select v-model="memberForm.member_level">
            <el-option v-for="level in memberLevelOptions" :key="level.value" :label="level.label" :value="level.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="有效期">
          <el-date-picker v-model="memberForm.expires_at" type="date" value-format="YYYY-MM-DD" placeholder="不填表示长期有效" />
        </el-form-item>
        <el-form-item label="余额增减（元）"><el-input v-model="memberForm.balance_change_yuan" placeholder="如 50 或 -20" /></el-form-item>
        <el-form-item label="积分增减"><el-input-number v-model="memberForm.points_change" /></el-form-item>
        <el-form-item label="调整原因"><el-input v-model="memberForm.reason" placeholder="默认：后台调整会员账户" /></el-form-item>
        <div class="dialog-actions">
          <el-button @click="resetMemberForm">取消</el-button>
          <el-button type="primary" :loading="loading" native-type="submit">保存会员</el-button>
        </div>
      </el-form>
    </el-drawer>
    <el-drawer :model-value="Boolean(resetUser)" title="重置密码" size="min(600px, 100vw)" @close="resetPasswordDialog" class="admin-edit-drawer">
      <el-form label-position="top" class="element-form" @submit.prevent="submitResetPassword">
        <el-alert title="新密码至少 6 位。保存后该用户旧登录态会失效。" type="warning" show-icon :closable="false" />
        <el-form-item label="新密码"><el-input v-model="resetPasswordForm.password" type="password" show-password /></el-form-item>
        <div class="dialog-actions">
          <el-button @click="resetPasswordDialog">取消</el-button>
          <el-button type="primary" :loading="loading" native-type="submit">重置密码</el-button>
        </div>
      </el-form>
    </el-drawer>
  </el-card>
</template>
