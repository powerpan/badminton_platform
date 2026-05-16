<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessageBox } from "element-plus";

import { getCourtSlots, getCourts, type Court, type SlotItem } from "../api/court";
import { createReservation, payReservationOrder } from "../api/reservation";
import { useAuthStore } from "../stores/auth";

const DEFAULT_COURT_IMAGE_URL = "/courts/default-court.png";
const authStore = useAuthStore();

const courts = ref<Court[]>([]);
const selectedCourtId = ref<number | null>(null);
const selectedDate = ref(formatDateValue(new Date()));
const slotMap = ref<Record<number, SlotItem[]>>({});
const selectedSlot = ref<SlotItem | null>(null);
const remark = ref("");
const loading = ref(false);
const submitting = ref(false);
const message = ref("");
const errorMessage = ref("");

const selectedCourt = computed(() => courts.value.find((court) => court.id === selectedCourtId.value) || null);
const currentMember = computed(() => authStore.user?.member || null);
const visibleCourts = computed(() => courts.value.slice(0, 4));
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
  return Math.floor((selectedCourt.value.price_per_hour_cents * selectedDurationMinutes.value) / 60);
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
const balanceEnough = computed(() => !currentMember.value || currentMember.value.balance_cents >= payableFeeCents.value);
const selectedDateLabel = computed(() => formatDisplayDate(selectedDate.value));

const dateOptions = computed(() => {
  const today = new Date();
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() + index);
    return {
      value: formatDateValue(date),
      label: `${index === 0 ? "今天" : weekdayLabel(date)} ${date.getMonth() + 1}.${date.getDate()}`,
    };
  });
});

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
  return `${value} ${weekdayLabel(date)}`;
}

function timeLabel(value: string) {
  return value.slice(0, 5);
}

function timeToMinutes(value: string) {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatOrderExpiry(value: string | null | undefined) {
  return value || "系统设定时间";
}

function discountText(rate: number) {
  return rate >= 100 ? "普通价" : `${rate / 10} 折`;
}

function courtImage(court: Court | null) {
  return court?.image_url || DEFAULT_COURT_IMAGE_URL;
}

function courtSummary(court: Court) {
  const tags = court.tags?.length ? court.tags.join(" · ") : "标准场地";
  return `${tags} · ${court.capacity} 人制`;
}

function statusText(status: SlotItem["status"]) {
  const textMap: Record<SlotItem["status"], string> = {
    available: "可预订",
    reserved: "已预订",
    locked: "锁定中",
    disabled: "不可用",
  };
  return textMap[status];
}

function slotButtonType(status: SlotItem["status"] | undefined) {
  if (status === "available") return "success";
  if (status === "reserved") return "info";
  if (status === "locked") return "warning";
  return "";
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
    const response = await getCourts({ page_size: 100 });
    courts.value = response.data.items;
    if (!selectedCourtId.value && courts.value.length > 0) {
      selectedCourtId.value = courts.value[0].id;
    }
    await loadSlots();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "场地加载失败";
  } finally {
    loading.value = false;
  }
}

async function loadSlots() {
  if (courts.value.length === 0) {
    slotMap.value = {};
    return;
  }
  loading.value = true;
  errorMessage.value = "";
  selectedSlot.value = null;
  try {
    const responses = await Promise.all(
      courts.value.map(async (court) => {
        const response = await getCourtSlots(court.id, selectedDate.value);
        return [court.id, response.data.slots] as const;
      }),
    );
    slotMap.value = Object.fromEntries(responses) as Record<number, SlotItem[]>;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "时间段加载失败";
  } finally {
    loading.value = false;
  }
}

function selectCourt(court: Court) {
  selectedCourtId.value = court.id;
  selectedSlot.value = null;
  message.value = "";
}

function chooseDate(value: string) {
  selectedDate.value = value;
}

function chooseDateValue(value: string | number) {
  selectedDate.value = String(value);
}

function chooseSlot(court: Court, slot: SlotItem) {
  if (slot.status !== "available") return;
  selectedCourtId.value = court.id;
  selectedSlot.value = slot;
  message.value = "";
}

async function submitReservation() {
  if (!selectedCourtId.value || !selectedSlot.value) {
    errorMessage.value = "请先选择可预约时间段";
    return;
  }
  if (!balanceEnough.value) {
    errorMessage.value = "会员余额不足，请联系管理员充值或调整余额";
    return;
  }
  submitting.value = true;
  errorMessage.value = "";
  message.value = "";
  try {
    const response = await createReservation({
      court_id: selectedCourtId.value,
      reserve_date: selectedDate.value,
      start_time: selectedSlot.value.start_time,
      end_time: selectedSlot.value.end_time,
      remark: remark.value,
    });
    const reservation = response.data;
    remark.value = "";
    await loadSlots();
    if (reservation.order_id && reservation.status === "pending") {
      message.value = "待支付订单已创建，请在超时前完成余额支付";
      try {
        await ElMessageBox.confirm(
          `待支付订单 ${reservation.order_no || ""} 已创建，需支付 ${formatMoney(reservation.order_amount_cents ?? reservation.payable_amount_cents)}。请在 ${formatOrderExpiry(reservation.order_expires_at)} 前完成支付，否则场地占用会自动释放。`,
          "余额支付确认",
          {
            confirmButtonText: "立即支付",
            cancelButtonText: "稍后支付",
            type: "warning",
          },
        );
      } catch {
        message.value = "待支付订单已创建，可在“我的预约”中继续支付或取消";
        return;
      }
      const paid = await payReservationOrder(reservation.order_id);
      await authStore.fetchProfile();
      await loadSlots();
      message.value = `支付成功，预约 ${paid.data.reservation_no} 已确认`;
      return;
    }
    await authStore.fetchProfile();
    message.value = "预约成功，已加入我的预约";
  } catch (error) {
    const text = error instanceof Error ? error.message : "预约提交失败";
    errorMessage.value = text.includes("时间段") || text.includes("占用") || text.includes("已被预约")
      ? "该时间段已被其他用户抢先预约，请重新选择"
      : text;
    await loadSlots();
  } finally {
    submitting.value = false;
  }
}

watch(selectedDate, async () => {
  message.value = "";
  await loadSlots();
});

onMounted(async () => {
  await loadCourts();
});
</script>

<template>
  <section class="booking-screen element-booking">
    <div class="booking-main">
      <el-card shadow="never" class="panel-card booking-toolbar-card">
        <div class="booking-toolbar element-toolbar">
          <el-segmented
            :model-value="selectedDate"
            :options="dateOptions"
            @change="chooseDateValue"
          />
          <el-select v-model="selectedCourtId" placeholder="全部场馆" filterable clearable @change="selectedSlot = null">
            <el-option v-for="court in courts" :key="court.id" :label="court.court_name" :value="court.id" />
          </el-select>
          <el-button :loading="loading" @click="loadSlots">刷新时间段</el-button>
        </div>
      </el-card>

      <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />
      <el-alert v-if="message" class="page-alert" :title="message" type="success" show-icon :closable="false" />

      <el-empty v-if="!loading && courts.length === 0" description="暂无可预约场地" />
      <div v-else class="court-gallery" v-loading="loading && courts.length === 0">
        <button
          v-for="court in visibleCourts"
          :key="court.id"
          type="button"
          class="court-card"
          :class="{ active: selectedCourtId === court.id }"
          @click="selectCourt(court)"
        >
          <el-tag class="court-status" type="success" effect="dark">{{ court.tags?.[0] || "标准场地" }}</el-tag>
          <img :src="courtImage(court)" :alt="court.court_name" />
          <span v-if="selectedCourtId === court.id" class="selected-check"></span>
          <span class="court-card-body">
            <strong>{{ court.court_name }}</strong>
            <small>{{ court.description || courtSummary(court) }}</small>
            <span class="court-tags">
              <el-tag v-for="tag in court.tags" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
              <el-tag size="small" effect="plain">{{ court.capacity }} 人制</el-tag>
            </span>
            <span class="court-price">{{ formatMoney(court.price_per_hour_cents) }} <em>/ 小时</em></span>
          </span>
        </button>
      </div>

      <el-card shadow="never" class="panel-card">
        <div class="slot-header">
          <div>
            <h2>选择时间段</h2>
            <p>{{ selectedDateLabel }}，系统按后台规则实时生成状态。</p>
          </div>
          <div class="legend">
            <span><i class="legend-available"></i>可预订</span>
            <span><i class="legend-reserved"></i>已预订</span>
            <span><i class="legend-disabled"></i>不可用</span>
          </div>
        </div>

        <el-empty v-if="timelineRows.length === 0 && !loading" description="暂无可显示时间段" />
        <div v-else class="slot-matrix" v-loading="loading && courts.length > 0">
          <div class="slot-matrix-head">
            <span></span>
            <strong v-for="court in visibleCourts" :key="court.id">{{ court.court_name }}</strong>
          </div>
          <div v-for="row in timelineRows" :key="`${row.start_time}-${row.end_time}`" class="slot-matrix-row">
            <span class="time-axis">{{ timeLabel(row.start_time) }} - {{ timeLabel(row.end_time) }}</span>
            <el-button
              v-for="court in visibleCourts"
              :key="court.id"
              class="slot-button element-slot-button"
              :type="slotButtonType(getSlot(court.id, row)?.status)"
              :plain="selectedCourtId !== court.id || selectedSlot?.start_time !== row.start_time || selectedSlot?.end_time !== row.end_time"
              :disabled="getSlot(court.id, row)?.status !== 'available'"
              @click="getSlot(court.id, row) && chooseSlot(court, getSlot(court.id, row) as SlotItem)"
            >
              {{
                getSlot(court.id, row)?.status === "available"
                  ? formatMoney(court.price_per_hour_cents)
                  : statusText(getSlot(court.id, row)?.status || "disabled")
              }}
            </el-button>
          </div>
        </div>
      </el-card>
    </div>

    <el-card shadow="never" class="booking-summary element-summary">
      <template #header>
        <div class="summary-title">
          <h2>预订清单</h2>
          <el-button link type="info" @click="selectedSlot = null">清空</el-button>
        </div>
      </template>

      <section class="summary-block">
        <h3>已选场地</h3>
        <div v-if="selectedCourt" class="summary-court">
          <img :src="courtImage(selectedCourt)" :alt="selectedCourt.court_name" />
          <div>
            <strong>{{ selectedCourt.court_name }}</strong>
            <span>{{ selectedCourt.description || courtSummary(selectedCourt) }}</span>
            <b>{{ formatMoney(selectedCourt.price_per_hour_cents) }} <em>/ 小时</em></b>
          </div>
        </div>
        <el-empty v-else description="请选择场地" :image-size="80" />
      </section>

      <section class="summary-block">
        <div class="summary-row-title">
          <h3>已选时间</h3>
          <el-button link @click="selectedSlot = null">编辑</el-button>
        </div>
        <p v-if="selectedSlot" class="summary-time">
          {{ selectedDateLabel }}<br />
          {{ timeLabel(selectedSlot.start_time) }} - {{ timeLabel(selectedSlot.end_time) }}
          <span>{{ selectedDurationLabel }}</span>
        </p>
        <p v-else class="muted-text">请选择可预订时间段</p>
      </section>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="会员折扣">{{ selectedSlot ? discountText(selectedDiscountRate) : "请选择时间段" }}</el-descriptions-item>
        <el-descriptions-item label="场地费">{{ formatMoney(selectedFeeCents) }}</el-descriptions-item>
        <el-descriptions-item label="优惠金额">-{{ formatMoney(discountCents) }}</el-descriptions-item>
        <el-descriptions-item label="当前余额">{{ formatMoney(currentMember?.balance_cents) }}</el-descriptions-item>
        <el-descriptions-item label="合计">{{ formatMoney(payableFeeCents) }}</el-descriptions-item>
      </el-descriptions>

      <el-alert v-if="selectedSlot && !balanceEnough" class="page-alert" title="余额不足，无法提交预约" type="error" show-icon :closable="false" />

      <el-form label-position="top" class="summary-actions element-form" @submit.prevent="submitReservation">
        <el-form-item label="备注">
          <el-input v-model="remark" maxlength="255" placeholder="可选，如需靠近门口" />
        </el-form-item>
        <el-button type="primary" size="large" :loading="submitting" :disabled="!selectedSlot || !balanceEnough" native-type="submit">
          确认预约
        </el-button>
        <el-button size="large" @click="selectedSlot = null">继续选场</el-button>
      </el-form>

      <div class="policy-box">
        <strong>取消政策</strong>
        <span>预约前请查看场地使用须知</span>
      </div>
    </el-card>
  </section>
</template>
