<script setup lang="ts">
import { onMounted, ref } from "vue";

import { adminGetCommunityPosts, adminHideCommunityPost } from "../../api/admin";
import { type CommunityPost } from "../../api/community";
import { type PageState, confirmAction, setSuccess, setError, resetPage, changePage } from "./shared";

const loading = ref(false);

async function changeCommunityPage(page: number) {
  await changePage(communityPage.value, page, () => refreshCommunityPosts());
}

const communityPosts = ref<CommunityPost[]>([]);

const communityPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });

const communityStatus = ref("");

async function loadCommunityPosts() {
  const response = await adminGetCommunityPosts({
    status: communityStatus.value || undefined,
    page: communityPage.value.page,
    page_size: communityPage.value.page_size,
  });
  communityPosts.value = response.data.items;
  communityPage.value.total = response.data.total;
}

async function refreshCommunityPosts(reset = false) {
  if (reset) resetPage(communityPage.value);
  loading.value = true;
  try {
    await loadCommunityPosts();
  } catch (error) {
    setError(error, "球友圈动态加载失败");
  } finally {
    loading.value = false;
  }
}

async function hideAdminCommunityPost(post: CommunityPost) {
  if (!(await confirmAction(`确认隐藏 ${post.nickname || post.username} 的动态？`))) return;
  loading.value = true;
  try {
    await adminHideCommunityPost(post.id);
    await loadCommunityPosts();
    setSuccess("动态已隐藏");
  } catch (error) {
    setError(error, "隐藏动态失败");
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadCommunityPosts();
  } catch (error) { setError(error, "数据加载失败"); }
  finally { loading.value = false; }
});
</script>

<template>
  <section class="page-header"><h1>球友圈管理</h1><p>查看球友动态，处理不合适的内容。</p></section>
  <el-card shadow="never" class="admin-shell element-admin">
    <section v-loading="loading" class="admin-section">
      <el-form inline class="element-filter">
        <el-form-item label="状态">
          <el-select v-model="communityStatus" clearable class="short-select" @change="refreshCommunityPosts(true)">
            <el-option label="显示" value="1" />
            <el-option label="隐藏" value="0" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-table :data="communityPosts" empty-text="暂无动态数据" stripe>
        <el-table-column label="用户" min-width="120"><template #default="{ row }">{{ row.nickname || row.username }}</template></el-table-column>
        <el-table-column prop="content" label="内容" min-width="280" />
        <el-table-column prop="created_at" label="发布时间" min-width="170" />
        <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'" effect="plain">{{ row.status === 1 ? "显示" : "隐藏" }}</el-tag></template></el-table-column>
        <el-table-column label="操作" fixed="right" width="100"><template #default="{ row }"><el-button link type="warning" :disabled="row.status !== 1" @click="hideAdminCommunityPost(row)">隐藏</el-button></template></el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="communityPage.page" :page-size="communityPage.page_size" :total="communityPage.total" layout="prev, pager, next, total" @current-change="changeCommunityPage" />
    </section>

  </el-card>
</template>
