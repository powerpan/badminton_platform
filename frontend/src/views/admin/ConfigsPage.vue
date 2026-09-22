<script setup lang="ts">
import { onMounted, ref } from "vue";

import { adminGetConfigs, adminUpdateConfig, type ConfigItem } from "../../api/admin";
import { confirmAction, setSuccess, setError } from "./shared";

const loading = ref(false);

const configs = ref<ConfigItem[]>([]);

const editingConfig = ref<ConfigItem | null>(null);

const configForm = ref({ config_value: "" });

async function loadConfigs() {
  const response = await adminGetConfigs();
  configs.value = response.data;
}

function editConfig(config: ConfigItem) {
  editingConfig.value = config;
  configForm.value = { config_value: config.config_value };
}

function resetConfigForm() {
  editingConfig.value = null;
  configForm.value = { config_value: "" };
}

async function submitConfig() {
  if (!editingConfig.value) return;
  const nextValue = configForm.value.config_value.trim();
  if (!nextValue) {
    setError(new Error("配置值不能为空"), "更新规则配置失败");
    return;
  }
  if (!(await confirmAction(`确认保存规则 ${editingConfig.value.config_key} = ${nextValue}？`))) return;
  loading.value = true;
  try {
    await adminUpdateConfig(editingConfig.value.config_key, nextValue);
    resetConfigForm();
    await loadConfigs();
    setSuccess("规则配置已更新");
  } catch (error) {
    setError(error, "更新规则配置失败");
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadConfigs();
  } catch (error) { setError(error, "数据加载失败"); }
  finally { loading.value = false; }
});
</script>

<template>
  <section class="page-header"><h1>规则配置</h1><p>设置预约和会员业务规则。</p></section>
  <el-card shadow="never" class="admin-shell element-admin">
    <section v-loading="loading" class="admin-section">
      <el-table :data="configs" empty-text="暂无规则配置" stripe>
        <el-table-column prop="config_key" label="配置键" min-width="220" />
        <el-table-column prop="config_value" label="配置值" min-width="160" />
        <el-table-column prop="description" label="说明" min-width="260" />
        <el-table-column label="操作" fixed="right" width="100"><template #default="{ row }"><el-button link type="primary" @click="editConfig(row)">编辑</el-button></template></el-table-column>
      </el-table>
    </section>
    <el-drawer :model-value="Boolean(editingConfig)" :title="`编辑规则：${editingConfig?.config_key || ''}`" size="min(600px, 100vw)" @close="resetConfigForm" class="admin-edit-drawer">
      <el-alert :title="editingConfig?.description || '修改后会影响后续业务判断。'" type="info" show-icon :closable="false" />
      <el-form label-position="top" class="element-form" @submit.prevent="submitConfig">
        <el-form-item label="配置值"><el-input v-model="configForm.config_value" /></el-form-item>
        <div class="dialog-actions">
          <el-button @click="resetConfigForm">取消</el-button>
          <el-button type="primary" :loading="loading" native-type="submit">保存规则</el-button>
        </div>
      </el-form>
    </el-drawer>
  </el-card>
</template>
