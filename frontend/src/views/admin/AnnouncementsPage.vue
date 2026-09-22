<script setup lang="ts">
import { onMounted, ref } from "vue";

import { type Announcement } from "../../api/announcement";
import { adminCreateAnnouncement, adminGetAnnouncements, adminUpdateAnnouncement, adminUpdateAnnouncementStatus } from "../../api/admin";
import { type PageState, confirmAction, setSuccess, setError, resetPage, changePage } from "./shared";

const loading = ref(false);

async function changeAnnouncementPage(page: number) {
  await changePage(announcementPage.value, page, () => refreshAnnouncements());
}

const announcements = ref<Announcement[]>([]);

const announcementPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });

const announcementStatus = ref("");

const announcementForm = ref({ title: "", content: "", status: 1 });

const editingAnnouncementId = ref<number | null>(null);

const editingAnnouncement = ref<Announcement | null>(null);

const announcementEditForm = ref({ title: "", content: "", status: 1 });

async function loadAnnouncements() {
  const response = await adminGetAnnouncements({
    status: announcementStatus.value || undefined,
    page: announcementPage.value.page,
    page_size: announcementPage.value.page_size,
  });
  announcements.value = response.data.items;
  announcementPage.value.total = response.data.total;
}

async function refreshAnnouncements(reset = false) {
  if (reset) resetPage(announcementPage.value);
  loading.value = true;
  try {
    await loadAnnouncements();
  } catch (error) {
    setError(error, "公告列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function submitAnnouncement() {
  const payload = editingAnnouncementId.value ? announcementEditForm.value : announcementForm.value;
  loading.value = true;
  try {
    if (editingAnnouncementId.value) {
      await adminUpdateAnnouncement(editingAnnouncementId.value, payload);
      setSuccess("公告已更新");
    } else {
      await adminCreateAnnouncement(payload);
      createVisible.value = false;
    setSuccess("公告已创建");
    }
    resetAnnouncementForm();
    resetPage(announcementPage.value);
    await loadAnnouncements();
  } catch (error) {
    setError(error, "保存公告失败");
  } finally {
    loading.value = false;
  }
}

function editAnnouncement(announcement: Announcement) {
  editingAnnouncementId.value = announcement.id;
  editingAnnouncement.value = announcement;
  announcementEditForm.value = {
    title: announcement.title,
    content: announcement.content,
    status: announcement.status,
  };
}

function resetAnnouncementForm() {
  editingAnnouncementId.value = null;
  editingAnnouncement.value = null;
  announcementForm.value = { title: "", content: "", status: 1 };
  announcementEditForm.value = { title: "", content: "", status: 1 };
}

async function toggleAnnouncementStatus(announcement: Announcement) {
  const nextStatusLabel = announcement.status === 1 ? "隐藏" : "显示";
  if (!(await confirmAction(`确认${nextStatusLabel}公告《${announcement.title}》？`))) return;
  loading.value = true;
  try {
    await adminUpdateAnnouncementStatus(announcement.id, announcement.status === 1 ? 0 : 1);
    await loadAnnouncements();
    setSuccess("公告状态已更新");
  } catch (error) {
    setError(error, "更新公告状态失败");
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadAnnouncements();
  } catch (error) { setError(error, "数据加载失败"); }
  finally { loading.value = false; }
});
const createVisible = ref(false);
</script>

<template>
  <section class="page-header"><h1>公告管理</h1><p>发布球馆消息和入场须知。</p></section>
  <el-card shadow="never" class="admin-shell element-admin">
    <section v-loading="loading" class="admin-section">
      <div class="admin-create-action"><el-button type="primary" @click="createVisible = true">新增公告</el-button></div>
      <el-drawer v-model="createVisible" title="新增公告" size="min(600px, 100vw)" class="admin-edit-drawer">
        <el-form label-position="top" class="element-form" @submit.prevent="submitAnnouncement">
          <el-form-item label="公告标题"><el-input v-model="announcementForm.title" /></el-form-item>
          <el-form-item label="公告内容"><el-input v-model="announcementForm.content" type="textarea" :rows="4" /></el-form-item>
          <el-form-item label="状态">
            <el-select v-model="announcementForm.status" class="short-select">
              <el-option label="显示" :value="1" />
              <el-option label="隐藏" :value="0" />
            </el-select>
          </el-form-item>
          <el-button type="primary" native-type="submit">新增公告</el-button>
        </el-form>
      </el-drawer>

      <el-form inline class="element-filter">
        <el-form-item label="状态">
          <el-select v-model="announcementStatus" clearable class="short-select" @change="refreshAnnouncements(true)">
            <el-option label="显示" value="1" />
            <el-option label="隐藏" value="0" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table :data="announcements" empty-text="暂无公告数据" stripe>
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'" effect="plain">{{ row.status === 1 ? "显示" : "隐藏" }}</el-tag></template></el-table-column>
        <el-table-column prop="updated_at" label="更新时间" min-width="170" />
        <el-table-column label="操作" fixed="right" width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click="editAnnouncement(row)">编辑</el-button>
            <el-button link type="warning" @click="toggleAnnouncementStatus(row)">{{ row.status === 1 ? "隐藏" : "显示" }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="announcementPage.page" :page-size="announcementPage.page_size" :total="announcementPage.total" layout="prev, pager, next, total" @current-change="changeAnnouncementPage" />
    </section>
    <el-drawer :model-value="Boolean(editingAnnouncementId)" :title="`编辑公告：${editingAnnouncement?.title || ''}`" size="min(600px, 100vw)" @close="resetAnnouncementForm" class="admin-edit-drawer">
      <el-form label-position="top" class="element-form" @submit.prevent="submitAnnouncement">
        <el-form-item label="公告标题"><el-input v-model="announcementEditForm.title" /></el-form-item>
        <el-form-item label="公告内容"><el-input v-model="announcementEditForm.content" type="textarea" :rows="5" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="announcementEditForm.status">
            <el-option label="显示" :value="1" />
            <el-option label="隐藏" :value="0" />
          </el-select>
        </el-form-item>
        <div class="dialog-actions">
          <el-button @click="resetAnnouncementForm">取消</el-button>
          <el-button type="primary" :loading="loading" native-type="submit">保存公告</el-button>
        </div>
      </el-form>
    </el-drawer>
  </el-card>
</template>
