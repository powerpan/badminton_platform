<script setup lang="ts">
import ReservationHistory from "../../components/ReservationHistory.vue";
import { recordAttendance } from "../../api/operations";
import { onMounted, ref } from "vue";
import { formatDeadline } from "../../utils/booking";

import { adminCancelReservation, adminGetCourts, adminGetReservation, adminGetReservations } from "../../api/admin";
import { type Court } from "../../api/court";
import { type Reservation } from "../../api/reservation";
import { type PageState, formatMoney, discountText, statusTagType, reservationStatusText, payMethodText, confirmAction, setSuccess, setError, resetPage, changePage } from "./shared";

const loading = ref(false);
const memberLevelText = (value: string) => ({ normal: '普通会员', silver: '白银会员', gold: '黄金会员', diamond: '钻石会员' }[value] || value || '-');
const orderStatusText = (value: string | null | undefined) => ({ pending: '待支付', paid: '已支付', canceled: '已取消', expired: '已过期' }[value || ''] || value || '-');

async function changeReservationPage(page: number) {
  await changePage(reservationPage.value, page, () => refreshReservations());
}

const courtOptions = ref<Court[]>([]);

const reservations = ref<Reservation[]>([]);

const selectedReservation = ref<Reservation | null>(null);

const reservationDetailVisible = ref(false);

const reservationPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });

const reservationFilters = ref({
  status: "",
  username: "",
  court_id: "",
  date_from: "",
  date_to: "",
});

async function loadCourtOptions() {
  if (courtOptions.value.length > 0) return;
  const response = await adminGetCourts({ page_size: 100 });
  courtOptions.value = response.data.items;
}

async function loadReservations() {
  const response = await adminGetReservations({
    status: reservationFilters.value.status || undefined,
    username: reservationFilters.value.username || undefined,
    court_id: reservationFilters.value.court_id ? Number(reservationFilters.value.court_id) : undefined,
    date_from: reservationFilters.value.date_from || undefined,
    date_to: reservationFilters.value.date_to || undefined,
    page: reservationPage.value.page,
    page_size: reservationPage.value.page_size,
  });
  reservations.value = response.data.items;
  reservationPage.value.total = response.data.total;
}

async function refreshReservations(reset = false) {
  if (reset) resetPage(reservationPage.value);
  loading.value = true;
  try {
    await loadReservations();
  } catch (error) {
    setError(error, "预约列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function openReservationDetail(reservation: Reservation) {
  loading.value = true;
  try {
    const response = await adminGetReservation(reservation.id);
    selectedReservation.value = response.data;
    reservationDetailVisible.value = true;
  } catch (error) {
    setError(error, "预约详情加载失败");
  } finally {
    loading.value = false;
  }
}

async function cancelAdminReservation(reservation: Reservation) {
  const tip = reservation.status === "pending"
    ? `确认取消待支付预约 ${reservation.reservation_no}？取消后会释放场地占用。`
    : `确认取消预约 ${reservation.reservation_no}？`;
  if (!(await confirmAction(tip))) return;
  loading.value = true;
  try {
    const response = await adminCancelReservation(reservation.id);
    if (selectedReservation.value?.id === reservation.id) {
      selectedReservation.value = response.data;
    }
    await loadReservations();
    setSuccess("预约已取消");
  } catch (error) {
    setError(error, "取消预约失败");
  } finally {
    loading.value = false;
  }
}

function attendanceText(row: Reservation) { return row.attendance_outcome === 'checked_in' ? '已核销' : row.attendance_outcome === 'no_show' ? '未到场' : '未记录'; }
function attendanceAllowed(row: Reservation, outcome: 'checked_in' | 'no_show') {
  if (row.attendance_outcome || !['confirmed','completed'].includes(row.status)) return false;
  const now = Date.now(), start = new Date(`${row.reserve_date}T${row.start_time}`).getTime(), end = new Date(`${row.reserve_date}T${row.end_time}`).getTime();
  return outcome === 'checked_in' ? now >= start - 30 * 60000 && now < end : now >= end;
}
async function saveAttendance(row: Reservation, outcome: 'checked_in' | 'no_show') {
  if (!await confirmAction(`${outcome === 'checked_in' ? '确认该用户已经到场' : '确认该用户没有到场'}？记录后不会自动覆盖。`)) return;
  loading.value = true;
  try { selectedReservation.value = (await recordAttendance(row.id,outcome)).data; await loadReservations(); setSuccess('到场情况已记录'); }
  catch(e) { setError(e,'到场记录失败'); } finally { loading.value = false; }
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadCourtOptions();
    await loadReservations();
  } catch (error) { setError(error, "数据加载失败"); }
  finally { loading.value = false; }
});
</script>

<template>
  <section class="page-header"><h1>预约管理</h1><p>查询场次安排，处理预约与取消。</p></section>
  <el-card shadow="never" class="admin-shell element-admin">
    <section v-loading="loading" class="admin-section">
      <el-form inline class="element-filter">
        <el-form-item label="状态">
          <el-select v-model="reservationFilters.status" clearable class="short-select" @change="refreshReservations(true)">
            <el-option label="已确认" value="confirmed" />
            <el-option label="已取消" value="canceled" />
            <el-option label="待支付" value="pending" />
            <el-option label="已结束" value="completed" />
            <el-option label="已过期" value="expired" />
          </el-select>
        </el-form-item>
        <el-form-item label="用户"><el-input v-model="reservationFilters.username" placeholder="用户名或昵称" @keyup.enter="refreshReservations(true)" /></el-form-item>
        <el-form-item label="场地">
          <el-select v-model="reservationFilters.court_id" clearable filterable class="medium-select" @change="refreshReservations(true)">
            <el-option v-for="court in courtOptions" :key="court.id" :label="`${court.court_no} ${court.court_name}`" :value="String(court.id)" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="reservationFilters.date_from" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="reservationFilters.date_to" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item><el-button type="primary" @click="refreshReservations(true)">查询预约</el-button></el-form-item>
      </el-form>

      <el-table :data="reservations" empty-text="暂无预约数据" stripe>
        <el-table-column prop="reservation_no" label="预约号" min-width="150" />
        <el-table-column label="用户" min-width="120"><template #default="{ row }">{{ row.nickname || row.username }}</template></el-table-column>
        <el-table-column prop="court_name" label="场地" min-width="110" />
        <el-table-column prop="reserve_date" label="日期" min-width="115" />
        <el-table-column label="时间" min-width="120"><template #default="{ row }">{{ row.start_time }}-{{ row.end_time }}</template></el-table-column>
        <el-table-column label="应付金额" min-width="120"><template #default="{ row }">{{ formatMoney(row.payable_amount_cents) }}</template></el-table-column>
        <el-table-column label="状态" min-width="100"><template #default="{ row }"><el-tag :type="statusTagType(row.status)" effect="plain">{{ reservationStatusText(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="到场" min-width="90"><template #default="{ row }">{{ attendanceText(row) }}</template></el-table-column>
        <el-table-column label="操作" fixed="right" width="132">
          <template #default="{ row }">
            <el-button link type="primary" @click="openReservationDetail(row)">详情</el-button>
            <el-button link type="danger" :disabled="Boolean(row.attendance_outcome) || !['pending', 'confirmed'].includes(row.status)" @click="cancelAdminReservation(row)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="element-pagination" :current-page="reservationPage.page" :page-size="reservationPage.page_size" :total="reservationPage.total" layout="prev, pager, next, total" @current-change="changeReservationPage" />
    </section>
    <el-drawer v-model="reservationDetailVisible" title="预约详情" size="min(600px, 100vw)" class="admin-edit-drawer">
      <div v-if="selectedReservation" class="record-detail">
        <el-descriptions :column="1" border class="compact-descriptions">
          <el-descriptions-item label="预约号">{{ selectedReservation.reservation_no }}</el-descriptions-item>
          <el-descriptions-item label="用户">{{ selectedReservation.nickname || selectedReservation.username }}</el-descriptions-item>
          <el-descriptions-item label="场地">{{ selectedReservation.court_no }} {{ selectedReservation.court_name }}</el-descriptions-item>
          <el-descriptions-item label="日期时间">
            {{ selectedReservation.reserve_date }} {{ selectedReservation.start_time }}-{{ selectedReservation.end_time }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(selectedReservation.status)" effect="plain">{{ reservationStatusText(selectedReservation.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="会员折扣">
            {{ memberLevelText(selectedReservation.member_level_snapshot) }} / {{ discountText(selectedReservation.discount_rate) }}
          </el-descriptions-item>
          <el-descriptions-item label="场地费">{{ formatMoney(selectedReservation.original_amount_cents) }}</el-descriptions-item>
          <el-descriptions-item label="优惠金额">-{{ formatMoney(selectedReservation.discount_amount_cents) }}</el-descriptions-item>
          <el-descriptions-item label="应付金额">{{ formatMoney(selectedReservation.payable_amount_cents) }}</el-descriptions-item>
          <el-descriptions-item label="积分">+{{ selectedReservation.points_awarded || 0 }}</el-descriptions-item>
          <el-descriptions-item label="订单号">{{ selectedReservation.order_no || "-" }}</el-descriptions-item>
          <el-descriptions-item label="订单状态">{{ orderStatusText(selectedReservation.order_status) }}</el-descriptions-item>
          <el-descriptions-item label="支付方式">{{ payMethodText(selectedReservation.order_pay_method) }}</el-descriptions-item>
          <el-descriptions-item label="支付截止">{{ formatDeadline(selectedReservation.order_expires_at) }}</el-descriptions-item>
          <el-descriptions-item label="支付时间">{{ selectedReservation.order_paid_at || "-" }}</el-descriptions-item>
          <el-descriptions-item label="取消时间">{{ selectedReservation.canceled_at || selectedReservation.order_canceled_at || "-" }}</el-descriptions-item>
          <el-descriptions-item label="到场情况">{{ attendanceText(selectedReservation) }} · {{ selectedReservation.attendance_recorded_at || '尚无记录' }}<span v-if="selectedReservation.attendance_recorded_by"> · 操作人 #{{ selectedReservation.attendance_recorded_by }}</span></el-descriptions-item>
          <el-descriptions-item label="备注">{{ selectedReservation.remark || "-" }}</el-descriptions-item>
        </el-descriptions>
        <ReservationHistory v-if="reservationDetailVisible" :reservation-id="selectedReservation.id" />
        <div class="dialog-actions">
          <el-button v-if="attendanceAllowed(selectedReservation,'checked_in')" type="primary" :loading="loading" @click="saveAttendance(selectedReservation,'checked_in')">到场核销</el-button>
          <el-button v-if="attendanceAllowed(selectedReservation,'no_show')" :loading="loading" @click="saveAttendance(selectedReservation,'no_show')">确认未到场</el-button>
          <el-button @click="reservationDetailVisible = false">关闭</el-button>
          <el-button
            v-if="!selectedReservation.attendance_outcome && ['pending', 'confirmed'].includes(selectedReservation.status)"
            type="danger"
            plain
            :loading="loading"
            @click="cancelAdminReservation(selectedReservation)"
            >
            取消预约
          </el-button>
        </div>
      </div>
    </el-drawer>
  </el-card>
</template>
