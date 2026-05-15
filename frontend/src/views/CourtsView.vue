<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { getCourtSlots, getCourts, type Court, type SlotItem } from "../api/court";
import { createReservation } from "../api/reservation";

const DEFAULT_COURT_IMAGE_URL = "/courts/default-court.png";

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
  if (!selectedSlot.value) {
    return 0;
  }
  const start = timeToMinutes(selectedSlot.value.start_time);
  const end = timeToMinutes(selectedSlot.value.end_time);
  return Math.max(0, end - start);
});

const selectedDurationLabel = computed(() => {
  if (!selectedDurationMinutes.value) {
    return "0 小时";
  }
  const hours = selectedDurationMinutes.value / 60;
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} 小时`;
});
const selectedFeeCents = computed(() => {
  if (!selectedCourt.value || !selectedDurationMinutes.value) {
    return 0;
  }
  return Math.floor((selectedCourt.value.price_per_hour_cents * selectedDurationMinutes.value) / 60);
});
const discountCents = computed(() => 0);
const payableFeeCents = computed(() => Math.max(0, selectedFeeCents.value - discountCents.value));
const selectedDateLabel = computed(() => formatDisplayDate(selectedDate.value));

const dateOptions = computed(() => {
  const today = new Date();
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() + index);
    return {
      value: formatDateValue(date),
      label: index === 0 ? "今天" : weekdayLabel(date),
      short: `${date.getMonth() + 1}.${date.getDate()}`,
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
  return `￥${((cents || 0) / 100).toFixed(0)}`;
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

function selectCourtFromInput(event: Event) {
  const value = Number((event.target as HTMLSelectElement).value);
  selectedCourtId.value = Number.isFinite(value) && value > 0 ? value : courts.value[0]?.id || null;
  selectedSlot.value = null;
  message.value = "";
}

function chooseDate(value: string) {
  selectedDate.value = value;
}

function chooseSlot(court: Court, slot: SlotItem) {
  if (slot.status !== "available") {
    return;
  }
  selectedCourtId.value = court.id;
  selectedSlot.value = slot;
  message.value = "";
}

async function submitReservation() {
  if (!selectedCourtId.value || !selectedSlot.value) {
    errorMessage.value = "请先选择可预约时间段";
    return;
  }
  submitting.value = true;
  errorMessage.value = "";
  message.value = "";
  try {
    await createReservation({
      court_id: selectedCourtId.value,
      reserve_date: selectedDate.value,
      start_time: selectedSlot.value.start_time,
      end_time: selectedSlot.value.end_time,
      remark: remark.value,
    });
    remark.value = "";
    await loadSlots();
    message.value = "预约成功，已加入我的预约";
  } catch (error) {
    const text = error instanceof Error ? error.message : "预约提交失败";
    errorMessage.value = text.includes("预约") || text.includes("占用")
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
  <section class="booking-screen">
    <div class="booking-main">
      <div class="booking-toolbar">
        <button type="button" class="calendar-square" aria-label="选择日期">
          <span></span>
        </button>
        <div class="date-strip">
          <button
            v-for="item in dateOptions"
            :key="item.value"
            type="button"
            :class="{ active: selectedDate === item.value }"
            @click="chooseDate(item.value)"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.short }}</strong>
          </button>
        </div>
        <select class="venue-select" :value="selectedCourtId || ''" @change="selectCourtFromInput">
          <option value="">全部场馆</option>
          <option v-for="court in courts" :key="court.id" :value="court.id">
            {{ court.court_name }}
          </option>
        </select>
        <button type="button" class="filter-button">
          <span></span>
          筛选
        </button>
      </div>

      <div v-if="loading && courts.length === 0" class="loading-block">正在加载场地...</div>
      <div v-else-if="courts.length === 0" class="empty-state">暂无可预约场地</div>
      <div v-else class="court-gallery">
        <button
          v-for="court in visibleCourts"
          :key="court.id"
          type="button"
          class="court-card"
          :class="{ active: selectedCourtId === court.id }"
          @click="selectCourt(court)"
        >
          <span class="court-status">{{ court.tags?.[0] || "标准场地" }}</span>
          <img :src="courtImage(court)" :alt="court.court_name" />
          <span v-if="selectedCourtId === court.id" class="selected-check"></span>
          <span class="court-card-body">
            <strong>{{ court.court_name }}</strong>
            <small>{{ court.description || courtSummary(court) }}</small>
            <span class="court-tags">
              <i v-for="tag in court.tags" :key="tag">{{ tag }}</i>
              <i>{{ court.capacity }} 人制</i>
            </span>
            <span class="court-price">{{ formatMoney(court.price_per_hour_cents) }} <em>/ 小时</em></span>
          </span>
        </button>
      </div>

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

      <div v-if="loading && courts.length > 0" class="loading-line">正在刷新时间段...</div>
      <div v-if="timelineRows.length === 0 && !loading" class="empty-state">暂无可显示时间段</div>
      <div v-else class="slot-matrix">
        <div class="slot-matrix-head">
          <span></span>
          <strong v-for="court in visibleCourts" :key="court.id">{{ court.court_name }}</strong>
        </div>
        <div v-for="row in timelineRows" :key="`${row.start_time}-${row.end_time}`" class="slot-matrix-row">
          <span class="time-axis">{{ timeLabel(row.start_time) }} - {{ timeLabel(row.end_time) }}</span>
          <button
            v-for="court in visibleCourts"
            :key="court.id"
            type="button"
            class="slot-button"
            :class="[
              getSlot(court.id, row)?.status || 'disabled',
              {
                active:
                  selectedCourtId === court.id &&
                  selectedSlot?.start_time === row.start_time &&
                  selectedSlot?.end_time === row.end_time,
              },
            ]"
            :disabled="getSlot(court.id, row)?.status !== 'available'"
            @click="getSlot(court.id, row) && chooseSlot(court, getSlot(court.id, row) as SlotItem)"
          >
            {{
              getSlot(court.id, row)?.status === "available"
                ? formatMoney(court.price_per_hour_cents)
                : statusText(getSlot(court.id, row)?.status || "disabled")
            }}
          </button>
        </div>
      </div>
    </div>

    <aside class="booking-summary">
      <div class="summary-title">
        <h2>预订清单</h2>
        <button type="button" aria-label="清空选择" @click="selectedSlot = null"></button>
      </div>

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
        <p v-else class="muted-text">请选择场地</p>
      </section>

      <section class="summary-block">
        <div class="summary-row-title">
          <h3>已选时间</h3>
          <button type="button" @click="selectedSlot = null">编辑</button>
        </div>
        <p v-if="selectedSlot" class="summary-time">
          {{ selectedDateLabel }}<br />
          {{ timeLabel(selectedSlot.start_time) }} - {{ timeLabel(selectedSlot.end_time) }}
          <span>{{ selectedDurationLabel }}</span>
        </p>
        <p v-else class="muted-text">请选择可预订时间段</p>
      </section>

      <section class="summary-block coupon-row">
        <h3>优惠券</h3>
        <span>{{ selectedSlot ? "本阶段暂无折扣" : "未使用优惠券" }}</span>
      </section>

      <section class="summary-block">
        <h3>费用明细</h3>
        <div class="fee-row">
          <span>场地费</span>
          <strong>{{ formatMoney(selectedFeeCents) }}</strong>
        </div>
        <div class="fee-row">
          <span>会员折扣</span>
          <strong>-{{ formatMoney(discountCents) }}</strong>
        </div>
        <div class="fee-total">
          <span>合计</span>
          <strong>{{ formatMoney(payableFeeCents) }}</strong>
        </div>
      </section>

      <form class="summary-actions" @submit.prevent="submitReservation">
        <label>
          备注
          <input v-model="remark" maxlength="255" placeholder="可选，如需靠近门口" />
        </label>
        <button class="primary-button" type="submit" :disabled="submitting || !selectedSlot">
          {{ submitting ? "提交中..." : "确认预约" }}
        </button>
        <button type="button" class="secondary-button" @click="selectedSlot = null">继续选场</button>
      </form>

      <p v-if="message" class="success-text">{{ message }}</p>
      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

      <div class="policy-box">
        <strong>取消政策</strong>
        <span>预约前请查看场地使用须知</span>
      </div>
    </aside>
  </section>
</template>
