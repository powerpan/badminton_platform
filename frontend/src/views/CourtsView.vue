<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import BookingRecommendations from "../components/BookingRecommendations.vue";
import BookingReceipt from "../components/BookingReceipt.vue";
import PaymentDialog from '../components/PaymentDialog.vue';
import { ApiRequestError } from '../api/http';
import { ArrowRight, Calendar, Check, EditPen, Refresh, Search } from "@element-plus/icons-vue";
import type { Recommendation } from "../api/operations";
import { ElMessage } from "element-plus";

import { getCourtSlots, getCourts, getReservationRules, getBookingBalance, type Court, type SlotItem, type ReservationRules, type BookingBalance } from "../api/court";
import { getProfile } from "../api/auth";
import { createReservation } from "../api/reservation";
import { useAuthStore } from "../stores/auth";

import { selectRange, rangePrice, timeToMinutes, type TimeRange } from "../utils/booking";

const authStore = useAuthStore();

const courts = ref<Court[]>([]);
const selectedCourtId = ref<number | null>(null);
const selectedDate = ref(formatDateValue(new Date()));
const slotMap = ref<Record<number, SlotItem[]>>({});
const selectedSlot = ref<TimeRange | null>(null);
const courtFilter = ref<number | null>(null);
const rules = ref<ReservationRules | null>(null);
const bookingBalance = ref<BookingBalance | null>(null);
let requestVersion = 0;
let refreshing = false;
let refreshTimer: ReturnType<typeof setInterval> | undefined;
let disposed = false;
const remark = ref("");
const loading = ref(false);
const submitting = ref(false);
const message = ref("");
const errorMessage = ref("");
const receiptOpen = ref(false);
const recommendationsOpen = ref(false);
const payMethod = ref<'balance' | 'mock_alipay'>('balance');
const paymentId = ref<number | null>(null), paymentVisible = ref(false);
const pendingRequest = ref<Parameters<typeof createReservation>[0] | null>(null);
const recoveryKey = () => `bf-booking-request:${authStore.user?.id}`;
function clearPendingRequest() { pendingRequest.value = null; sessionStorage.removeItem(recoveryKey()); }
async function afterPayment() {
  message.value = '支付成功，预约已确认';
  await Promise.allSettled([authStore.fetchProfile(), loadSlots()]);
}

const selectedCourt = computed(() => courts.value.find((court) => court.id === selectedCourtId.value) || null);
const currentMember = computed(() => authStore.user?.member || null);
const visibleCourts = computed(() => courtFilter.value
  ? courts.value.filter(court => court.id === courtFilter.value) : courts.value);
const matrixStyle = computed(() => ({ "--court-count": visibleCourts.value.length || 1 }));
const timelineRows = computed(() => {
  const rows = new Map<string, { start_time: string; end_time: string }>();
  Object.values(slotMap.value).forEach((slots) => {
    slots.forEach((slot) => {
      rows.set(`${slot.start_time}-${slot.end_time}`, {
        start_time: slot.start_time,
        end_time: slot.end_time,
      });
    });
  });
  return Array.from(rows.values()).sort((left, right) => left.start_time.localeCompare(right.start_time));
});

const selectedDurationMinutes = computed(() => {
  if (!selectedSlot.value) return 0;
  const start = timeToMinutes(selectedSlot.value.start_time);
  const end = timeToMinutes(selectedSlot.value.end_time);
  return Math.max(0, end - start);
});

const selectedDurationLabel = computed(() => {
  if (!selectedDurationMinutes.value) return "0 小时";
  const hours = selectedDurationMinutes.value / 60;
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} 小时`;
});
const selectedFeeCents = computed(() => {
  if (!selectedCourt.value || !selectedDurationMinutes.value) return 0;
  return rangePrice(selectedCourt.value.price_per_hour_cents, selectedSlot.value!);
});
const selectedDiscountRate = computed(() => {
  const member = currentMember.value;
  if (!member) return 100;
  if (member.expires_at && selectedDate.value > member.expires_at) return 100;
  return member.discount_rate || 100;
});
const discountCents = computed(() => {
  const payable = Math.floor((selectedFeeCents.value * selectedDiscountRate.value) / 100);
  return Math.max(0, selectedFeeCents.value - payable);
});
const payableFeeCents = computed(() => Math.max(0, selectedFeeCents.value - discountCents.value));
const balanceEnough = computed(() => Boolean(bookingBalance.value) && bookingBalance.value!.available_balance_cents >= payableFeeCents.value);
const selectedDateLabel = computed(() => formatDisplayDate(selectedDate.value));
const calendarMonth = computed(() => `${selectedDate.value.slice(0, 4)}年${Number(selectedDate.value.slice(5, 7))}月`);
const mobileSlots = computed(() => selectedCourtId.value ? slotMap.value[selectedCourtId.value] || [] : []);
const receipt = computed(() => ({
  courtLabel: selectedCourt.value ? `${selectedCourt.value.court_no} ${selectedCourt.value.court_name}` : '',
  dateLabel: selectedDateLabel.value,
  timeLabel: selectedSlot.value ? `${selectedSlot.value.start_time}–${selectedSlot.value.end_time}` : '',
  durationLabel: selectedDurationLabel.value,
  fee: formatMoney(selectedFeeCents.value),
  discountLabel: selectedSlot.value ? discountText(selectedDiscountRate.value) : '—',
  discount: formatMoney(discountCents.value), total: formatMoney(payableFeeCents.value),
  availableBalance: bookingBalance.value ? formatMoney(bookingBalance.value.available_balance_cents) : '—',
  pendingBalance: bookingBalance.value ? formatMoney(bookingBalance.value.pending_amount_cents) : '—',
  hasSelection: Boolean(selectedSlot.value), canConfirm: !loading.value && Boolean(selectedSlot.value),
  submitting: submitting.value,
}));

const dateOptions = computed(() => {
  if (!rules.value) return [];
  const first = new Date(`${rules.value.min_date}T00:00:00`);
  const last = new Date(`${rules.value.max_date}T00:00:00`);
  const result = [];
  // Quick choices are bounded; the date picker exposes the full configured range.
  for (let index = 0; index < 7; index += 1) {
    const date = new Date(first);
    date.setDate(first.getDate() + index);
    if (date > last) break;
    result.push({ value: formatDateValue(date), weekday: index === 0 ? "今天" : weekdayLabel(date), day: date.getDate(), label: `${date.getMonth() + 1}月${date.getDate()}日 ${weekdayLabel(date)}` });
  }
  return result;
});

function disabledDate(value: Date) {
  const formatted = formatDateValue(value);
  return !rules.value || formatted < rules.value.min_date || formatted > rules.value.max_date;
}

function formatDateValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function weekdayLabel(date: Date) {
  return ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][date.getDay()];
}

function formatDisplayDate(value: string) {
  const date = new Date(`${value}T00:00:00`);
  return `${date.getMonth() + 1}月${date.getDate()}日 ${weekdayLabel(date)}`;
}

function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function discountText(rate: number) {
  return rate >= 100 ? "普通价" : `${rate / 10} 折`;
}

function slotPrice(cents: number) {
  return `¥${(cents / 100).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}`;
}

function courtSummary(court: Court) {
  return `${court.tags?.join(' · ') || '标准场地'} · 最多 ${court.capacity} 人`;
}

function clearSelection() {
  if (!submitting.value) selectedSlot.value = null;
}

async function confirmFromReceipt() {
  if (submitting.value) return;
  receiptOpen.value = false;
  await submitReservation();
}

async function applyRecommendation(item: Recommendation) {
  if (submitting.value) return;
  courtFilter.value = null;
  await loadSlots();
  const slots = (slotMap.value[item.court_id] || []).filter(slot => slot.start_time >= item.start_time && slot.end_time <= item.end_time);
  if (!slots.length || slots[0].start_time !== item.start_time || slots[slots.length - 1].end_time !== item.end_time || slots.some(slot => slot.status !== 'available')) {
    errorMessage.value = '这个推荐时段刚刚发生变化，请重新查找'; return;
  }
  selectedCourtId.value = item.court_id;
  selectedSlot.value = { start_time: item.start_time, end_time: item.end_time };
  recommendationsOpen.value = false;
  message.value = '已选好推荐场次，请核对金额后确认预订';
}

function statusText(status: SlotItem["status"]) {
  const textMap: Record<SlotItem["status"], string> = {
    available: "可预订",
    reserved: "已预订",
    locked: "锁定中",
    disabled: "不可用",
    maintenance: "维护 / 包场",
  };
  return textMap[status];
}

function getSlot(courtId: number, row: { start_time: string; end_time: string }) {
  return slotMap.value[courtId]?.find(
    (slot) => slot.start_time === row.start_time && slot.end_time === row.end_time,
  );
}

async function loadCourts() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const [response, ruleResponse, balanceResponse] = await Promise.all([
      getCourts({ page_size: 100 }), getReservationRules(), getBookingBalance(),
    ]);
    const all = [...response.data.items];
    for (let page = 2; all.length < response.data.total; page += 1) {
      const more = await getCourts({ page, page_size: 100 });
      if (!more.data.items.length) break;
      all.push(...more.data.items);
    }
    if (disposed) return;
    courts.value = all;
    rules.value = ruleResponse.data;
    bookingBalance.value = balanceResponse.data;
    selectedDate.value = ruleResponse.data.min_date;
    if (!selectedCourtId.value && all.length > 0) selectedCourtId.value = all[0].id;
    await loadSlots();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "场地加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadSlots(keepSelection = false) {
  const version = ++requestVersion;
  const date = selectedDate.value;
  if (!date) return;
  if (!keepSelection) selectedSlot.value = null;
  if (!keepSelection) loading.value = true;
  errorMessage.value = "";
  try {
    const [responses, ruleResponse, balanceResponse, profileResponse] = await Promise.all([
      Promise.all(courts.value.map(async court => {
        const response = await getCourtSlots(court.id, date);
        return response.data;
      })), getReservationRules(), getBookingBalance(), getProfile(),
    ]);
    if (version !== requestVersion) return;
    rules.value = ruleResponse.data;
    bookingBalance.value = balanceResponse.data;
    if (date < rules.value.min_date || date > rules.value.max_date) {
      selectedDate.value = rules.value.min_date;
      return;
    }
    authStore.setProfile(profileResponse.data);
    const freshCourts = new Map(responses.map(response => [response.court_id, response.court]));
    courts.value = courts.value.map(court => freshCourts.get(court.id) || court);
    slotMap.value = Object.fromEntries(responses.map(response => [response.court_id, response.slots])) as Record<number, SlotItem[]>;
    if (selectedSlot.value && selectedCourtId.value) {
      const selected = selectedSlot.value;
      const slots = slotMap.value[selectedCourtId.value] || [];
      const available = slots.filter(slot => slot.start_time >= selected.start_time && slot.end_time <= selected.end_time);
      const minutes = available.reduce((total, slot) => total + timeToMinutes(slot.end_time) - timeToMinutes(slot.start_time), 0);
      if (!available.length || available.some(slot => slot.status !== "available")
        || minutes !== timeToMinutes(selected.end_time) - timeToMinutes(selected.start_time)
        || minutes > rules.value.max_reservation_minutes) {
        selectedSlot.value = null;
        errorMessage.value = "已选时段或预约规则发生变化，请重新选择";
      }
    }
  } catch (error) {
    if (version !== requestVersion) return;
    selectedSlot.value = null;
    slotMap.value = {};
    bookingBalance.value = null;
    errorMessage.value = error instanceof Error ? error.message : "时间段加载失败，请刷新重试";
  } finally {
    if (version === requestVersion) loading.value = false;
  }
}

async function refreshSlots() {
  if (refreshing || submitting.value || loading.value || document.hidden) return;
  refreshing = true;
  try { await loadSlots(true); } finally { refreshing = false; }
}

function isSelected(courtId: number, row: TimeRange) {
  return selectedCourtId.value === courtId && Boolean(selectedSlot.value
    && row.start_time >= selectedSlot.value.start_time && row.end_time <= selectedSlot.value.end_time);
}

function selectCourt(court: Court) {
  if (submitting.value) return;
  if (courtFilter.value && courtFilter.value !== court.id) courtFilter.value = null;
  selectedCourtId.value = court.id;
  selectedSlot.value = null;
  message.value = "";
}

function chooseDateValue(value: string) {
  if (!submitting.value) selectedDate.value = value;
}

function chooseSlot(court: Court, slot: SlotItem) {
  if (submitting.value) return;
  if (!rules.value || slot.status !== "available") return;
  const result = selectRange(slotMap.value[court.id] || [],
    selectedCourtId.value === court.id ? selectedSlot.value : null, slot, rules.value.max_reservation_minutes);
  errorMessage.value = result.error || "";
  if (result.error) return;
  selectedCourtId.value = court.id;
  selectedSlot.value = result.range;
  message.value = "";
}

async function submitReservation() {
  if (submitting.value) return;
  if (!pendingRequest.value && (!selectedCourtId.value || !selectedSlot.value)) {
    errorMessage.value = "请先选择可预约时间段";
    return;
  }
  const displayedAmount = payableFeeCents.value;
  submitting.value = true;
  errorMessage.value = "";
  message.value = "";
  try {
    if (!pendingRequest.value) {
      await loadSlots(true);
      if (!selectedSlot.value || !selectedCourtId.value) {
        if (errorMessage.value) ElMessage.error(errorMessage.value);
        return;
      }
      if (displayedAmount !== payableFeeCents.value) {
        errorMessage.value = '场地价格或会员权益已更新，请核对最新金额后再次确认预约';
        ElMessage.warning(errorMessage.value); return;
      }
      if (payMethod.value === 'balance' && !balanceEnough.value) {
        errorMessage.value = '可用余额不足，可以选择模拟支付宝，或联系前台充值';
        ElMessage.error(errorMessage.value); return;
      }
      pendingRequest.value = { court_id: selectedCourtId.value, reserve_date: selectedDate.value,
        start_time: selectedSlot.value.start_time, end_time: selectedSlot.value.end_time, remark: remark.value,
        expected_amount_cents: payableFeeCents.value, pay_method: payMethod.value, request_key: crypto.randomUUID() };
      sessionStorage.setItem(recoveryKey(), JSON.stringify(pendingRequest.value));
    }
    const response = await createReservation(pendingRequest.value);
    const reservation = response.data;
    clearPendingRequest();
    remark.value = "";
    await loadSlots();
    if (reservation.payment_id) {
      message.value = reservation.status === 'pending' ? '待支付订单已创建，可在“我的预约”中继续支付或取消' : '已恢复原预约，请查看订单状态';
      paymentId.value = reservation.payment_id; paymentVisible.value = true;
      return;
    }
    await authStore.fetchProfile();
    message.value = "预约成功，已加入我的预约";
  } catch (error) {
    if (error instanceof ApiRequestError && error.status && error.status >= 400 && error.status < 500) clearPendingRequest();
    const text = error instanceof Error ? error.message : "预约提交失败";
    const failure = text.includes("时间段") || text.includes("占用") || text.includes("已被预约")
      ? "该时间段已被其他用户抢先预约，请重新选择"
      : text;
    await loadSlots(true);
    errorMessage.value = pendingRequest.value ? `${failure}。结果未确认，已保存原请求，请恢复查询。` : failure;
    ElMessage.error(failure);
  } finally {
    submitting.value = false;
  }
}

watch(selectedDate, async () => {
  if (!rules.value) return;
  message.value = "";
  await loadSlots();
});

onMounted(async () => {
  try { pendingRequest.value = JSON.parse(sessionStorage.getItem(recoveryKey()) || 'null'); } catch { clearPendingRequest(); }
  await loadCourts();
  if (disposed) return;
  refreshTimer = setInterval(refreshSlots, 30_000);
  document.addEventListener("visibilitychange", refreshSlots);
});

watch(courtFilter, () => {
  selectedSlot.value = null;
  if (courtFilter.value) selectedCourtId.value = courtFilter.value;
});

onUnmounted(() => {
  disposed = true;
  requestVersion += 1;
  if (refreshTimer) clearInterval(refreshTimer);
  document.removeEventListener("visibilitychange", refreshSlots);
});
</script>

<template>
  <section class="reservation-planner" :style="matrixStyle">
    <div class="planner-workspace">
      <header class="planner-heading">
        <div><h1>场地预订</h1><p>选好日期，点击连续时段。</p></div>
        <RouterLink to="/reservations" class="planner-orders">我的预订<ArrowRight /></RouterLink>
      </header>

      <div class="planner-date-heading"><strong>{{ calendarMonth }}</strong></div>
      <div class="planner-dates">
        <div class="planner-date-rail" role="group" aria-label="预约日期">
          <button v-for="option in dateOptions" :key="option.value" type="button" :aria-label="option.label" :aria-pressed="selectedDate === option.value" :disabled="submitting" @click="chooseDateValue(option.value)">
            <span>{{ option.weekday }}</span><strong>{{ option.day }}</strong>
          </button>
        </div>
        <el-date-picker v-model="selectedDate" type="date" value-format="YYYY-MM-DD" format="M月D日" :prefix-icon="Calendar" :disabled="submitting" :disabled-date="disabledDate" :clearable="false" aria-label="选择其他日期" class="planner-calendar" />
      </div>

      <div class="planner-toolbar">
        <strong>{{ selectedDateLabel }}</strong>
        <el-select v-model="courtFilter" clearable :disabled="submitting" placeholder="全部场地" aria-label="筛选场地">
          <el-option v-for="court in courts" :key="court.id" :label="court.court_name" :value="court.id" />
        </el-select>
        <button type="button" class="planner-link planner-refresh" :disabled="loading || submitting" @click="loadSlots(true)"><Refresh />刷新</button>
        <button type="button" class="planner-link" :disabled="submitting" :aria-expanded="recommendationsOpen" aria-controls="planner-recommendations" @click="recommendationsOpen = !recommendationsOpen"><Search />找空闲场次</button>
      </div>

      <el-alert v-if="errorMessage" class="planner-alert" :title="errorMessage" type="error" show-icon :closable="false" role="alert" />
      <el-alert v-if="pendingRequest" title="有一笔预约提交尚未确认" type="warning" :closable="false"><p>恢复原请求会查询同一笔预约，不会重复创建。</p><el-button :loading="submitting" @click="submitReservation">恢复预约请求</el-button></el-alert>
      <el-alert v-if="message" class="planner-alert" :title="message" type="success" show-icon :closable="false" role="status" />

      <section class="planner-mobile-courts" aria-label="选择场地">
        <h2>场地</h2>
        <div class="planner-court-tabs">
          <button v-for="court in courts" :key="court.id" type="button" :disabled="submitting" :aria-pressed="selectedCourtId === court.id" @click="selectCourt(court)">{{ court.court_no }} <span>{{ court.court_name }}</span></button>
        </div>
        <p v-if="selectedCourt">{{ slotPrice(selectedCourt.price_per_hour_cents) }} / 小时 · {{ courtSummary(selectedCourt) }}</p>
      </section>
      <div class="planner-mobile-slot-heading"><h2>选择连续时段</h2><button type="button" class="planner-link" :disabled="submitting" :aria-expanded="recommendationsOpen" aria-controls="planner-recommendations" @click="recommendationsOpen = !recommendationsOpen">找空闲场次<ArrowRight /></button></div>
      <BookingRecommendations v-if="rules && courts.length" id="planner-recommendations" v-model="recommendationsOpen" :date="selectedDate" :courts="courts" :rules="rules" :disabled="submitting" @select="applyRecommendation" />

      <div v-loading="loading" class="planner-availability" :aria-busy="loading">
        <p v-if="!loading && !courts.length" class="planner-empty">暂无可预约场地</p>
        <p v-else-if="!loading && !timelineRows.length" class="planner-empty">暂无可显示时间段 <button type="button" class="planner-link" @click="loadSlots(true)">重新加载</button></p>
        <template v-else>
          <div class="planner-timetable" role="region" aria-label="场地时间表" tabindex="0">
            <div class="planner-table-head">
              <span>时间</span>
              <button v-for="court in visibleCourts" :key="court.id" type="button" :disabled="submitting" @click="selectCourt(court)"><strong>{{ court.court_no }} {{ court.court_name }}</strong><small>{{ slotPrice(court.price_per_hour_cents) }}/小时 · {{ courtSummary(court) }}</small></button>
            </div>
            <div v-for="row in timelineRows" :key="row.start_time" class="planner-table-row">
              <span class="planner-time-axis">{{ row.start_time }}–{{ row.end_time }}</span>
              <button v-for="court in visibleCourts" :key="court.id" type="button" class="planner-slot" :class="{ selected: isSelected(court.id, row), unavailable: getSlot(court.id, row)?.status !== 'available' }" :aria-label="`${court.court_name} ${row.start_time} 至 ${row.end_time}`" :aria-pressed="isSelected(court.id, row)" :disabled="submitting || getSlot(court.id, row)?.status !== 'available'" :title="getSlot(court.id, row)?.unavailable_reason || statusText(getSlot(court.id, row)?.status || 'disabled')" @click="getSlot(court.id, row) && chooseSlot(court, getSlot(court.id, row)!)">
                <span>{{ getSlot(court.id, row)?.status === 'available' ? slotPrice(getSlot(court.id, row)?.price_cents ?? rangePrice(court.price_per_hour_cents, row)) : getSlot(court.id, row)?.unavailable_reason || statusText(getSlot(court.id, row)?.status || 'disabled') }}</span><Check v-if="isSelected(court.id, row)" />
              </button>
            </div>
          </div>
          <div class="planner-mobile-slots" role="group" aria-label="当前场地时间段">
            <button v-for="slot in mobileSlots" :key="slot.start_time" type="button" class="planner-slot" :class="{ selected: isSelected(selectedCourtId!, slot), unavailable: slot.status !== 'available' }" :aria-label="`${selectedCourt?.court_name} ${slot.start_time} 至 ${slot.end_time}`" :aria-pressed="isSelected(selectedCourtId!, slot)" :disabled="submitting || slot.status !== 'available'" :title="slot.unavailable_reason || statusText(slot.status)" @click="selectedCourt && chooseSlot(selectedCourt, slot)">
              <strong>{{ slot.start_time }}–{{ slot.end_time }}</strong><span>{{ slot.status === 'available' ? slotPrice(slot.price_cents) : slot.unavailable_reason || statusText(slot.status) }}</span><Check v-if="isSelected(selectedCourtId!, slot)" />
            </button>
          </div>
          <div class="planner-table-footer">
            <div class="planner-legend"><span><i />可选</span><span><i class="is-selected" />已选</span><span><i class="is-unavailable" />不可用</span></div>
            <span v-if="rules">每格 {{ rules.slot_interval_minutes }} 分钟 · 最长 {{ rules.max_reservation_minutes / 60 }} 小时</span>
          </div>
        </template>
      </div>
      <div class="planner-mobile-details">
        <div><span>可用余额 <strong>{{ receipt.availableBalance }}</strong></span><button type="button" class="planner-link" @click="receiptOpen = true">费用明细<ArrowRight /></button></div>
        <button type="button" class="planner-remark-link" @click="receiptOpen = true"><EditPen />{{ remark ? '编辑备注' : '添加备注（选填）' }}<ArrowRight /></button>
        <button type="button" class="planner-link planner-mobile-refresh" :disabled="loading || submitting" @click="loadSlots(true)"><Refresh />刷新时间段</button>
      </div>
    </div>
    <aside class="planner-receipt-rail" aria-label="预订清单">
      <BookingReceipt v-model="remark" v-model:pay-method="payMethod" v-bind="receipt" @clear="clearSelection" @confirm="confirmFromReceipt" />
    </aside>
    <div class="planner-mobile-action">
      <div><strong>{{ receipt.total }}</strong><small>{{ selectedSlot ? `${selectedCourt?.court_no} · ${receipt.timeLabel} · ${selectedDurationLabel}` : '请选择连续时段' }}</small></div>
      <el-button type="primary" :loading="submitting" :disabled="!receipt.canConfirm" @click="receiptOpen = true">确认预约</el-button>
    </div>
    <el-drawer v-model="receiptOpen" title="费用明细" direction="btt" size="min(86dvh, 760px)" class="planner-receipt-drawer" :close-on-click-modal="!submitting" :close-on-press-escape="!submitting" :show-close="!submitting" destroy-on-close>
      <BookingReceipt v-model="remark" v-model:pay-method="payMethod" v-bind="receipt" @clear="clearSelection" @confirm="confirmFromReceipt" />
    </el-drawer>
  </section>
  <PaymentDialog v-model="paymentVisible" :payment-id="paymentId" @paid="afterPayment" @updated="loadSlots()" />
</template>
