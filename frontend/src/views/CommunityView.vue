<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import {
  createCommunityPost,
  getCommunityPosts,
  hideCommunityPost,
  type CommunityPost,
} from "../api/community";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
const posts = ref<CommunityPost[]>([]);
const content = ref("");
const page = ref({ page: 1, page_size: 10, total: 0 });
const loading = ref(false);
const errorMessage = ref("");

function authorName(post: CommunityPost) {
  return post.nickname || post.username;
}

function canHide(post: CommunityPost) {
  return authStore.user?.id === post.user_id;
}

async function loadPosts(reset = false) {
  if (reset) page.value.page = 1;
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await getCommunityPosts({ page: page.value.page, page_size: page.value.page_size });
    posts.value = response.data.items;
    page.value.total = response.data.total;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "动态加载失败";
  } finally {
    loading.value = false;
  }
}

async function submitPost() {
  const text = content.value.trim();
  if (!text) {
    ElMessage.error("动态内容不能为空");
    return;
  }
  loading.value = true;
  try {
    await createCommunityPost({ content: text });
    content.value = "";
    await loadPosts(true);
    ElMessage.success("动态已发布");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "发布动态失败");
  } finally {
    loading.value = false;
  }
}

async function hidePost(post: CommunityPost) {
  loading.value = true;
  try {
    await hideCommunityPost(post.id);
    await loadPosts();
    ElMessage.success("动态已隐藏");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "隐藏动态失败");
  } finally {
    loading.value = false;
  }
}

async function changePage(nextPage: number) {
  page.value.page = nextPage;
  await loadPosts();
}

onMounted(() => loadPosts());
</script>

<template>
  <section class="page-header">
    <p class="eyebrow">球友圈</p>
    <h1>球友圈</h1>
    <p>发布约球、训练和场馆交流动态。</p>
  </section>

  <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />

  <el-card v-if="authStore.isLoggedIn" shadow="never" class="panel-card community-compose" v-loading="loading">
    <el-form label-position="top" @submit.prevent="submitPost">
      <el-form-item label="发布动态">
        <el-input v-model="content" type="textarea" :rows="4" maxlength="1000" show-word-limit placeholder="写下今天想约的场次、训练心得或装备体验" />
      </el-form-item>
      <el-button type="primary" native-type="submit" :loading="loading">发布动态</el-button>
    </el-form>
  </el-card>
  <el-alert v-else class="page-alert" title="登录后可以发布球友圈动态。" type="info" show-icon :closable="false" />

  <el-card shadow="never" class="panel-card list-page-card" v-loading="loading">
    <el-empty v-if="posts.length === 0 && !loading" description="暂无动态" />
    <div v-else class="community-list">
      <article v-for="post in posts" :key="post.id" class="community-post">
        <div class="post-avatar">{{ authorName(post).slice(0, 1) }}</div>
        <div class="post-body">
          <div class="post-head">
            <strong>{{ authorName(post) }}</strong>
            <span>{{ post.created_at }}</span>
          </div>
          <p>{{ post.content }}</p>
          <el-button v-if="canHide(post)" link type="warning" @click="hidePost(post)">隐藏</el-button>
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
