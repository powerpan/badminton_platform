<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import { createHandoff, decideHandoff, getHandoff, type Handoff } from '../api/mobileHandoff';
import { terminalHandoff } from '../utils/mobileHandoff';
const visible = defineModel<boolean>({ default: false });
const props = defineProps<{ orderId: number }>();
const handoff = ref<Handoff>(), loading = ref(false), busy = ref(false), error = ref(''), now = ref(Date.now());
let version = 0, polling = false;
const seconds = computed(() => Math.max(0, Math.ceil((handoff.value?.expires_at || 0) - now.value / 1000)));
const expired = computed(() => Boolean(handoff.value && !seconds.value));
const labels = { waiting: '用手机扫码，然后在这里确认登录', claimed: '手机正在申请登录', approved: '已允许，等待手机接收', issuing: '正在为手机登录', consumed: '手机已登录，请在手机保存取货凭证', denied: '已拒绝本次登录', failed: '本次登录未完成，请重新生成二维码' };
async function cancel(value?: Handoff) {
  if (value && !terminalHandoff(value.status)) await decideHandoff(value.id, 'cancel');
}
async function generate() {
  if (loading.value || busy.value) return;
  const current = ++version, old = handoff.value;
  loading.value = true; error.value = '';
  try {
    // Await cancellation before replacing a still-live QR.
    if (old && old.expires_at * 1000 > Date.now()) await cancel(old);
    handoff.value = undefined;
    const result = (await createHandoff(props.orderId)).data;
    if (current !== version || !visible.value) { await cancel(result); return; }
    handoff.value = result; now.value = Date.now();
  } catch (e) { if (current === version) error.value = e instanceof Error ? e.message : '暂时不能生成二维码'; }
  finally { if (current === version) loading.value = false; }
}
async function poll() {
  if (!visible.value || !handoff.value || expired.value || terminalHandoff(handoff.value.status) || loading.value || busy.value || polling) return;
  const current = version, id = handoff.value.id; polling = true;
  try {
    const result = (await getHandoff(id)).data;
    if (current === version && handoff.value?.id === id) { handoff.value = { ...handoff.value, ...result }; error.value = ''; }
  } catch (e) { if (current === version) error.value = e instanceof Error ? e.message : '状态查询失败'; }
  finally { polling = false; }
}
async function decide(decision: 'approve' | 'deny') {
  if (!handoff.value || busy.value) return;
  const current = version, value = handoff.value; busy.value = true; error.value = '';
  try {
    const result = (await decideHandoff(value.id, decision, value.pairing_code)).data;
    if (current === version) handoff.value = { ...value, ...result };
  } catch (e) { if (current === version) error.value = e instanceof Error ? e.message : '操作未确认，请重试'; }
  finally { if (current === version) busy.value = false; }
}
watch(() => [visible.value, props.orderId] as const, ([open]) => {
  if (open) { void generate(); return; }
  version++; loading.value = false; busy.value = false;
  const old = handoff.value; handoff.value = undefined;
  void cancel(old).catch(() => { /* Unreachable server: the 120-second TTL remains the hard boundary. */ });
}, { immediate: true });
let ticks = 0;
const timer = setInterval(() => { now.value = Date.now(); if (++ticks % 2 === 0) void poll(); }, 1000);
onUnmounted(() => { version++; clearInterval(timer); void cancel(handoff.value).catch(() => {}); });
</script>
<template>
  <el-dialog v-model="visible" title="在手机查看取货凭证" width="min(440px, 94vw)" append-to-body :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy">
    <section class="handoff-panel" v-loading="loading" aria-live="polite">
      <el-alert v-if="error" :title="error" type="error" :closable="false" />
      <template v-if="handoff">
        <p class="handoff-account">登录账号 <strong>{{ handoff.username }}</strong></p>
        <template v-if="!expired && handoff.status === 'waiting'">
          <img :src="handoff.qr_data_url" alt="手机扫码登录并查看取货凭证" width="250" height="250" />
          <p>用手机扫描此码，免输入账号密码。</p>
        </template>
        <template v-if="!expired && handoff.status === 'claimed'">
          <p>请核对手机上是否显示相同数字</p>
          <strong class="pairing-code">{{ handoff.pairing_code }}</strong>
          <p>允许后，此手机可登录你的账号并使用余额等账号功能。</p>
          <div class="handoff-actions"><el-button :disabled="busy" @click="decide('deny')">拒绝</el-button><el-button type="primary" :loading="busy" @click="decide('approve')">允许此手机登录</el-button></div>
        </template>
        <p role="status">{{ expired && !terminalHandoff(handoff.status) ? '二维码已过期，请重新生成' : labels[handoff.status] }}</p>
        <small v-if="!expired && !terminalHandoff(handoff.status)">剩余 {{ seconds }} 秒 · 仅允许一台手机</small>
      </template>
      <p v-if="!handoff && !loading && !error">准备手机查看入口</p>
    </section>
    <template #footer><el-button :disabled="loading || busy" @click="visible = false">关闭</el-button><el-button v-if="handoff?.status !== 'consumed'" :loading="loading" :disabled="busy" @click="generate">重新生成二维码</el-button></template>
  </el-dialog>
</template>
<style scoped>
.handoff-panel { display: grid; justify-items: center; gap: 12px; min-height: 150px; text-align: center; line-height: 1.7; }
.handoff-panel p { margin: 0; }.handoff-panel img { max-width: 100%; height: auto; background: white; }.handoff-panel small { color: #68756e; }
.pairing-code { font-size: 36px; letter-spacing: 7px; color: #155b43; font-variant-numeric: tabular-nums; }
.handoff-actions { display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; }.handoff-actions :deep(.el-button) { margin-left: 0; }
</style>
