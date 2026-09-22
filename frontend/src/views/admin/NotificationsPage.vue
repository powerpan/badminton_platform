<script setup lang="ts">
import { ref } from "vue";
import { adminBroadcastNotification } from "../../api/admin";
import { confirmAction, setSuccess, setError } from "./shared";

const loading = ref(false);

const broadcastForm = ref({
  title: "",
  content: "",
});

async function submitBroadcast() {
  const title = broadcastForm.value.title.trim();
  const content = broadcastForm.value.content.trim();
  if (!title || !content) {
    setError(new Error("通知标题和内容不能为空"), "发送通知失败");
    return;
  }
  if (!(await confirmAction("确认向全部启用账号发送这条站内通知？"))) return;
  loading.value = true;
  try {
    const response = await adminBroadcastNotification({ title, content });
    broadcastForm.value = { title: "", content: "" };
    setSuccess(`通知已发送给 ${response.data.sent_count} 个账号`);
  } catch (error) {
    setError(error, "发送通知失败");
  } finally {
    loading.value = false;
  }
}

</script>

<template>
  <section class="page-header"><h1>通知管理</h1><p>向启用账号发送站内通知。</p></section>
  <el-card shadow="never" class="admin-shell element-admin">
    <section v-loading="loading" class="admin-section">
      <el-card shadow="never" class="panel-card">
        <template #header><strong>全员通知</strong></template>
        <el-alert title="此处发送给全部启用账号。预约、取消、会员调整和公告发布会由系统自动发送通知。" type="info" show-icon :closable="false" />
        <el-form label-position="top" class="element-form dialog-form" @submit.prevent="submitBroadcast">
          <el-form-item label="通知标题">
            <el-input v-model="broadcastForm.title" maxlength="100" show-word-limit />
          </el-form-item>
          <el-form-item label="通知内容">
            <el-input v-model="broadcastForm.content" type="textarea" :rows="6" maxlength="2000" show-word-limit />
          </el-form-item>
          <el-button type="primary" :loading="loading" native-type="submit">发送通知</el-button>
        </el-form>
      </el-card>
    </section>

  </el-card>
</template>
