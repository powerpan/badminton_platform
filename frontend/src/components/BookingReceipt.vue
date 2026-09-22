<script setup lang="ts">
defineProps<{
  courtLabel: string;
  dateLabel: string;
  timeLabel: string;
  durationLabel: string;
  fee: string;
  discountLabel: string;
  discount: string;
  total: string;
  availableBalance: string;
  pendingBalance: string;
  hasSelection: boolean;
  canConfirm: boolean;
  submitting: boolean;
}>();
const remark = defineModel<string>({ default: '' });
defineEmits<{ clear: []; confirm: [] }>();
</script>

<template>
  <form class="booking-receipt" @submit.prevent="$emit('confirm')">
    <div class="booking-receipt__heading">
      <h2>本次预约</h2>
      <button type="button" :disabled="submitting || !hasSelection" @click="$emit('clear')">清空</button>
    </div>
    <div class="booking-receipt__session">
      <h3>{{ courtLabel || '请选择场地' }}</h3>
      <p>{{ dateLabel }}</p>
      <strong v-if="hasSelection">{{ timeLabel }}</strong>
      <span v-else class="booking-receipt__empty">点击时段，选好下一场球。</span>
      <span v-if="hasSelection">{{ durationLabel }}</span>
    </div>
    <dl class="booking-receipt__lines">
      <div><dt>场地费</dt><dd>{{ fee }}</dd></div>
      <div><dt>会员折扣</dt><dd>{{ discountLabel }}</dd></div>
      <div><dt>优惠</dt><dd>−{{ discount }}</dd></div>
    </dl>
    <dl class="booking-receipt__lines booking-receipt__balance">
      <div><dt>可用余额</dt><dd>{{ availableBalance }}</dd></div>
      <div><dt>待支付占用</dt><dd>{{ pendingBalance }}</dd></div>
    </dl>
    <div class="booking-receipt__total"><span>合计</span><strong>{{ total }}</strong></div>
    <label class="booking-receipt__remark">
      <span>备注（选填）</span>
      <textarea v-model="remark" maxlength="255" rows="2" :disabled="submitting" aria-label="预约备注" />
    </label>
    <el-button type="primary" native-type="submit" :loading="submitting" :disabled="!canConfirm" class="booking-confirm">确认预约</el-button>
    <p class="booking-receipt__policy">开始前可取消，已支付金额退回会员余额。待支付订单到期自动释放。</p>
  </form>
</template>

<style scoped>
.booking-receipt { color: #202822; font-size: 16px; }
.booking-receipt__heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.booking-receipt__heading h2 { font-size: 17px; font-weight: 650; margin: 0; }
.booking-receipt__heading button { border: 0; background: transparent; color: #176447; cursor: pointer; font: inherit; padding: 8px 0 8px 12px; }
.booking-receipt__heading button:disabled { opacity: .45; cursor: default; }
.booking-receipt__session { padding: 26px 0; display: grid; gap: 10px; }
.booking-receipt__session h3 { margin: 0; font-size: 32px; letter-spacing: -.8px; font-weight: 650; }
.booking-receipt__session p { margin: 0; color: #717973; font-size: 18px; }
.booking-receipt__session > strong { font-size: clamp(24px, 2.4vw, 36px); letter-spacing: -1px; font-variant-numeric: tabular-nums; font-weight: 650; white-space: nowrap; }
.booking-receipt__session > span { font-size: 16px; }
.booking-receipt__session .booking-receipt__empty { color: #717973; font-size: 14px; line-height: 1.8; padding-block: 8px; }
.booking-receipt__lines { display: grid; gap: 14px; border-top: 1px solid #e3e7e4; padding: 24px 0; margin: 0; }
.booking-receipt__lines > div { display: flex; justify-content: space-between; gap: 16px; align-items: baseline; }
.booking-receipt__lines dt { color: #717973; }
.booking-receipt__lines dd { margin: 0; font-variant-numeric: tabular-nums; }
.booking-receipt__balance > div:last-child { font-size: 12px; color: #717973; }
.booking-receipt__total { border-top: 1px solid #e3e7e4; padding: 24px 0; display: flex; justify-content: space-between; align-items: baseline; gap: 12px; font-weight: 650; }
.booking-receipt__total strong { font-size: 28px; letter-spacing: -.6px; font-variant-numeric: tabular-nums; }
.booking-receipt__remark { display: grid; gap: 8px; font-size: 12px; color: #717973; margin-bottom: 18px; }
.booking-receipt__remark textarea { width: 100%; border: 1px solid #d4dbd6; border-radius: 4px; background: #fff; color: #202822; font: inherit; font-size: 14px; padding: 10px 12px; resize: vertical; min-height: 66px; box-shadow: none; }
.booking-receipt__remark textarea:focus { border-color: #176447; outline: 2px solid #176447; outline-offset: -2px; }
.booking-receipt__remark textarea:disabled { background: #f3f5f3; }
.booking-confirm { width: 100%; height: 46px; border-radius: 4px; --el-color-primary: #176447; --el-color-primary-light-3: #397f62; --el-color-primary-light-5: #8cb09f; --el-color-primary-dark-2: #124e37; font-size: 15px; font-weight: 600; }
.booking-receipt__policy { color: #717973; font-size: 12px; line-height: 1.8; margin: 14px 0 0; }
@media (max-width: 720px) {
  .booking-receipt__session { padding: 18px 0; gap: 8px; }
  .booking-receipt__session h3 { font-size: 24px; }
  .booking-receipt__session p { font-size: 16px; }
  .booking-receipt__session > strong { font-size: 28px; }
  .booking-receipt__lines { padding: 18px 0; gap: 12px; }
  .booking-receipt__total { padding: 18px 0; }
}
</style>
