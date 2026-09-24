<script setup lang="ts">
import type { AdminBookingDetail } from '../api/admin';
import ReservationHistory from './ReservationHistory.vue';
import { formatDeadline } from '../utils/booking';
import { formatMoney, payMethodText } from '../views/admin/shared';
defineProps<{ booking: AdminBookingDetail }>();
const paymentStatus = (value: string) => ({ pending: '待付款', succeeded: '付款成功', refunded: '已全额退款', canceled: '已撤销', expired: '已过期' }[value] || value);
</script>

<template>
  <section class="booking-evidence" aria-label="收退款凭据">
    <h3>收款记录</h3>
    <p v-if="!booking.payments.length" class="evidence-note">暂无统一支付单。历史金额请结合下方原账户流水核查，不能仅凭预约状态认定收款。</p>
    <article v-for="payment in booking.payments" :key="payment.id">
      <div class="evidence-title"><strong>{{ payment.purpose === 'reschedule' ? '改期补差' : '订场收款' }} · {{ formatMoney(payment.amount_cents) }}</strong><span>{{ paymentStatus(payment.status) }}</span></div>
      <p>{{ payMethodText(payment.pay_method) }} · 已退 {{ formatMoney(payment.refunded_cents) }}</p>
      <p class="evidence-number">支付 #{{ payment.id }} · {{ payment.payment_no }}</p>
      <dl><dt>开单</dt><dd>{{ payment.operator_name_snapshot }} · {{ formatDeadline(payment.created_at) }}</dd>
        <dt>收款</dt><dd>{{ payment.paid_at ? formatDeadline(payment.paid_at) : '尚无成功收款' }}<template v-if="payment.paid_at"> · {{ payment.collector_username || (payment.collected_by ? `经办 #${payment.collected_by}` : '经办凭据缺失') }}</template></dd>
        <dt>截止</dt><dd>{{ formatDeadline(payment.expires_at) }}</dd>
      </dl>
    </article>
    <h3>原渠道退款</h3>
    <p v-if="!booking.refunds.length" class="evidence-note">暂无统一退款记录；历史余额退回请查下方账户流水。</p>
    <article v-for="refund in booking.refunds" :key="refund.id">
      <div class="evidence-title"><strong>{{ refund.purpose === 'reschedule' ? '改期退差' : '取消退款' }} · {{ formatMoney(refund.amount_cents) }}</strong><span>{{ refund.status === 'succeeded' ? '已退款' : refund.status }}</span></div>
      <p>{{ payMethodText(refund.pay_method) }} · {{ refund.operator_name_snapshot }} · {{ formatDeadline(refund.refunded_at) }}</p>
      <p class="evidence-number">退款 #{{ refund.id }} · {{ refund.refund_no }}</p>
      <p class="evidence-number">原支付 #{{ refund.payment_order_id }} · {{ refund.payment_no }}</p>
      <p>{{ refund.reason }}</p>
    </article>
    <h3>账户变动</h3>
    <p v-if="!booking.account_transactions.length" class="evidence-note">本场暂无账户变动。模拟渠道收退款不增减储值本金。</p>
    <article v-for="entry in booking.account_transactions" :key="entry.id">
      <div class="evidence-title"><strong>{{ entry.balance_change_cents > 0 ? '+' : '' }}{{ formatMoney(entry.balance_change_cents) }}</strong><span>流水 #{{ entry.id }}</span></div>
      <p>{{ entry.reason }}</p>
      <p>余额 {{ formatMoney(entry.balance_before_cents) }} → {{ formatMoney(entry.balance_after_cents) }} · 积分 {{ entry.points_change > 0 ? '+' : '' }}{{ entry.points_change }}</p>
      <p>{{ formatDeadline(entry.created_at) }} · {{ entry.operator_username || '历史经办未记录' }}</p>
      <p v-if="entry.payment_order_id || entry.payment_refund_id" class="evidence-number"><span v-if="entry.payment_order_id">支付 #{{ entry.payment_order_id }}</span><span v-if="entry.payment_refund_id"> · 退款 #{{ entry.payment_refund_id }}</span></p>
    </article>
    <ReservationHistory :reservation-id="booking.id" :items="booking.changes" />
  </section>
</template>

<style scoped>
.booking-evidence { margin-top: 1.5rem; }
h3 { margin: 1.5rem 0 .65rem; font-size: 1rem; }
article { padding: 1rem 0; border-bottom: 1px solid var(--el-border-color-lighter); }
article p { margin: .4rem 0; line-height: 1.6; font-size: .85rem; overflow-wrap: anywhere; }
.evidence-title { display: flex; justify-content: space-between; gap: .7rem; flex-wrap: wrap; }
.evidence-title span, .evidence-note, dt { color: var(--el-text-color-secondary); font-size: .85rem; }
.evidence-note { line-height: 1.7; }
.evidence-number { font-variant-numeric: tabular-nums; }
dl { display: grid; grid-template-columns: 2rem minmax(0,1fr); gap: .4rem .6rem; font-size: .85rem; }
dd { margin: 0; overflow-wrap: anywhere; }
</style>
