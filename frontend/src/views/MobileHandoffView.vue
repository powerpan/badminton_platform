<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { claimHandoff, exchangeHandoff, type Handoff } from '../api/mobileHandoff';
import { createDeviceSecret, currentBrowserAccount, pickupPath } from '../utils/mobileHandoff';
import { useAuthStore } from '../stores/auth';
import { ApiRequestError } from '../api/http';
const route = useRoute(), router = useRouter(), auth = useAuthStore();
const handoff = ref<Handoff>(), error = ref(''), loading = ref(false), exchanging = ref(false), consent = ref(false), now = ref(Date.now());
const existingAccount = ref<number | null>(null);
const ended = ref(false);
const needsSwitch = computed(() => Boolean(handoff.value && existingAccount.value !== null && existingAccount.value !== handoff.value.user_id));
let version = 0, requestId = '', device = '', ticket = '', timer: ReturnType<typeof setTimeout> | undefined, consentAccount: number | null = null;
const seconds = computed(() => Math.max(0, Math.ceil((handoff.value?.expires_at || 0) - now.value / 1000)));
function schedule() { clearTimeout(timer); timer = setTimeout(() => void exchange(), 2000); }
async function exchange() {
  if (!handoff.value || !consent.value || exchanging.value || !seconds.value || ended.value) return;
  // Another tab may have changed the browser account while approval was pending.
  if (currentBrowserAccount() !== consentAccount) {
    existingAccount.value = currentBrowserAccount(); consent.value = false;
    error.value = '当前浏览器账号已变化，请确认后继续'; return;
  }
  const current = version; exchanging.value = true;
  try {
    const result = await exchangeHandoff(requestId, device);
    if (current !== version) return;
    handoff.value = result; error.value = '';
    if (result.login) {
      if (currentBrowserAccount() !== consentAccount) { consent.value = false; existingAccount.value = currentBrowserAccount(); error.value = '当前浏览器账号已变化，请确认后继续'; return; }
      auth.setSession(result.login.access_token, result.login.refresh_token, result.login.user);
      sessionStorage.removeItem(`bf-mobile-handoff:${requestId}`);
      await router.replace(pickupPath(result.order_id));
    } else schedule();
  } catch (e) {
    if (current === version) {
      error.value = e instanceof Error ? e.message : '登录未完成，请重试';
      ended.value = e instanceof ApiRequestError && [403, 404, 409, 410].includes(e.status || 0);
    }
  }
  finally { if (current === version) exchanging.value = false; }
}
function continueLogin() { existingAccount.value = currentBrowserAccount(); consentAccount = existingAccount.value; consent.value = true; error.value = ''; void exchange(); }
async function initialize() {
  const current = ++version; clearTimeout(timer); loading.value = true; handoff.value = undefined; error.value = ''; consent.value = false; exchanging.value = false; ended.value = false;
  requestId = String(route.params.id || '');
  try {
    if (!/^[a-f0-9]{32}$/.test(requestId)) throw new Error('扫码链接无效，请在电脑重新生成');
    const key = `bf-mobile-handoff:${requestId}`;
    const incoming = new URLSearchParams(route.hash.slice(1)).get('ticket');
    const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
    ticket = incoming || saved?.ticket || ''; device = saved?.device || createDeviceSecret();
    if (!/^[A-Za-z0-9_-]{43,64}$/.test(ticket)) throw new Error('请扫描电脑上新生成的二维码');
    sessionStorage.setItem(key, JSON.stringify({ ticket, device }));
    if (route.hash) await router.replace({ name: 'mobile-handoff', params: { id: requestId } });
    if (current !== version) return;
    const result = await claimHandoff(requestId, ticket, device);
    if (current !== version) return;
    handoff.value = result; now.value = Date.now(); existingAccount.value = currentBrowserAccount();
    if (!needsSwitch.value) continueLogin();
  } catch (e) { if (current === version) error.value = e instanceof Error ? e.message : '扫码申请失败，请重试'; }
  finally { if (current === version) loading.value = false; }
}
watch(() => route.params.id, () => void initialize(), { immediate: true });
const clock = setInterval(() => { now.value = Date.now(); }, 1000);
onUnmounted(() => { version++; clearTimeout(timer); clearInterval(clock); });
</script>
<template>
  <section class="mobile-receive" v-loading="loading">
    <p class="eyebrow">BF · 手机取货</p><h1>在手机接收取货凭证</h1>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="handoff">
      <p>准备登录账号 <strong>{{ handoff.username }}</strong></p>
      <template v-if="seconds > 0 && !ended">
        <p>请在电脑核对这组数字，并允许此手机登录</p>
        <strong class="pairing-code">{{ handoff.pairing_code }}</strong>
        <p v-if="needsSwitch && !consent">此浏览器已登录其他账号。继续后将切换到 {{ handoff.username }}，原账号的数据不会被删除。</p>
        <el-button v-if="!consent" type="primary" @click="continueLogin">{{ needsSwitch ? '确认切换账号并继续' : '继续登录' }}</el-button>
        <p v-else role="status">{{ handoff.status === 'claimed' ? '等待电脑允许登录…' : '正在接收登录授权…' }}</p>
        <small>剩余 {{ seconds }} 秒</small>
      </template>
      <p v-else>本次授权已结束，请在电脑重新生成二维码。</p>
      <p class="hint">允许后，将在此浏览器登录该账号并打开取货凭证。请仅接收自己电脑发起的登录。</p>
    </template>
    <div class="receive-actions"><el-button v-if="error && !ended" :loading="loading || exchanging" @click="handoff && consent ? exchange() : initialize()">重试</el-button><el-button @click="router.replace('/')">取消并返回首页</el-button></div>
  </section>
</template>
<style scoped>
.mobile-receive { max-width: 460px; margin: 32px auto; padding: 28px 24px; background: #fff; border: 1px solid #dce5df; border-radius: 8px; text-align: center; line-height: 1.8; overflow-wrap: anywhere; }
.mobile-receive h1 { font-size: 24px; margin: 12px 0 24px; }.eyebrow { font-size: 13px; color: #62796a; }.pairing-code { display: block; font-size: 38px; letter-spacing: 7px; color: #155b43; font-variant-numeric: tabular-nums; }
.hint, small { color: #6c766d; font-size: 13px; }.receive-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; margin-top: 24px; }.receive-actions :deep(.el-button) { margin-left: 0; }
@media(max-width:600px) { .mobile-receive { margin: 12px auto; padding: 22px 16px; }.mobile-receive h1 { font-size: 22px; } }
</style>
