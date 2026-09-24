<script setup lang="ts">
import BookingFinancialRecords from "../../components/BookingFinancialRecords.vue";
import { recordAttendance } from "../../api/operations";
import { onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from 'vue-router';
import { formatDeadline } from "../../utils/booking";

import { adminCancelReservation, adminGetCourts, adminGetReservation, adminGetReservations, type AdminBookingDetail } from "../../api/admin";
import { type Court } from "../../api/court";
import { type Reservation } from "../../api/reservation";
import { type PageState, formatMoney, discountText, statusTagType, reservationStatusText, payMethodText, confirmAction, setSuccess, setError, resetPage, changePage } from "./shared";

const loading = ref(false);
const route = useRoute();
const memberLevelText = (value: string) => ({ normal: '普通会员', silver: '白银会员', gold: '黄金会员', diamond: '钻石会员' }[value] || value || '-');
const orderStatusText = (value: string | null | undefined) => ({ pending: '待支付', paid: '已支付', canceled: '已取消', expired: '已过期' }[value || ''] || value || '-');

async function changeReservationPage(page: number) {
  await changePage(reservationPage.value, page, () => refreshReservations());
}

const courtOptions = ref<Court[]>([]);

const reservations = ref<Reservation[]>([]);

const selectedReservation = ref<AdminBookingDetail | null>(null);
let listVersion = 0, detailVersion = 0;
const detailLoading = ref(false), mutating = ref(false), serverOffset = ref<number | null>(null), clock = ref(Date.now());
let clockTimer: ReturnType<typeof setInterval> | undefined;

const reservationDetailVisible = ref(false);

const reservationPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });

const reservationFilters = ref({
  status: "",
  username: "",
  court_id: "",
  date_from: "",
  date_to: "",
  source: "",
  pay_method: "",
  operator: "",
  order_no: "",
});

async function loadCourtOptions() {
  if (courtOptions.value.length > 0) return;
  const response = await adminGetCourts({ page_size: 100 });
  courtOptions.value = response.data.items;
}

async function loadReservations() {
  const request = ++listVersion;
  loading.value = true;
  try {
    const response = await adminGetReservations({
      ...Object.fromEntries(Object.entries(reservationFilters.value).map(([key,value]) => [key,value || undefined])),
      court_id: reservationFilters.value.court_id ? Number(reservationFilters.value.court_id) : undefined,
      page: reservationPage.value.page,
      page_size: reservationPage.value.page_size,
    });
    if (request !== listVersion) return;
    reservations.value = response.data.items;
    reservationPage.value.total = response.data.total;
    serverOffset.value = Date.parse(response.data.server_now) - Date.now();
    clock.value = Date.now();
  } catch (error) { if (request === listVersion) { reservations.value = []; reservationPage.value.total = 0; setError(error, "预约列表加载失败"); } }
  finally { if (request === listVersion) loading.value = false; }
}

async function refreshReservations(reset = false) {
  if (reset) resetPage(reservationPage.value);
  await loadReservations();
}

async function openReservationDetail(reservation: Pick<Reservation, 'id'>) {
  reservationDetailVisible.value = true;
  selectedReservation.value = null;
  await reloadDetail(reservation.id);
}

async function reloadDetail(id: number) {
  const request = ++detailVersion;
  detailLoading.value = true;
  try {
    const response = await adminGetReservation(id);
    if (request !== detailVersion || !reservationDetailVisible.value) return;
    selectedReservation.value = response.data;
    serverOffset.value = Date.parse(response.data.server_now) - Date.now();
    clock.value = Date.now();
  } catch (error) { if (request === detailVersion) setError(error, "预约详情加载失败"); }
  finally { if (request === detailVersion) detailLoading.value = false; }
}

watch(reservationDetailVisible, visible => { if (!visible) { detailVersion++; detailLoading.value = false; } });

async function cancelAdminReservation(reservation: Reservation) {
  const tip = reservation.status === "pending"
    ? `确认取消待支付预约 ${reservation.reservation_no}？取消后会释放场地占用。`
    : `确认取消预约 ${reservation.reservation_no}？`;
  if (!(await confirmAction(tip))) return;
  mutating.value = true;
  try {
    await adminCancelReservation(reservation.id);
    if (selectedReservation.value?.id === reservation.id) {
      await reloadDetail(reservation.id);
    }
    await loadReservations();
    setSuccess("预约已取消");
  } catch (error) {
    setError(error, "取消预约失败");
  } finally {
    mutating.value = false;
  }
}

function attendanceText(row: Reservation) { return row.attendance_outcome === 'checked_in' ? '已核销' : row.attendance_outcome === 'no_show' ? '未到场' : '未记录'; }
function attendanceAllowed(row: Reservation, outcome: 'checked_in' | 'no_show') {
  if (serverOffset.value === null || row.attendance_outcome || !['confirmed','completed'].includes(row.status)) return false;
  const now = clock.value + serverOffset.value, start = Date.parse(`${row.reserve_date}T${row.start_time}:00+08:00`), end = Date.parse(`${row.reserve_date}T${row.end_time}:00+08:00`);
  return outcome === 'checked_in' ? now >= start - 30 * 60000 && now < end : now >= end;
}
async function saveAttendance(row: Reservation, outcome: 'checked_in' | 'no_show') {
  if (!await confirmAction(`${outcome === 'checked_in' ? '确认该用户已经到场' : '确认该用户没有到场'}？记录后不会自动覆盖。`)) return;
  mutating.value = true;
  try { await recordAttendance(row.id,outcome); if (selectedReservation.value?.id === row.id) await reloadDetail(row.id); await loadReservations(); setSuccess('到场情况已记录'); }
  catch(e) { setError(e,'到场记录失败'); } finally { mutating.value = false; }
}

onUnmounted(() => { listVersion++; detailVersion++; if (clockTimer) clearInterval(clockTimer); });

onMounted(async () => {
  clockTimer = setInterval(() => { clock.value = Date.now(); }, 15000);
  loading.value = true;
  try {
    await loadCourtOptions();
    await loadReservations();
  } catch (error) { setError(error, "数据加载失败"); }
  finally { loading.value = false; }
  const linkedId = String(route.query.reservation_id || '');
  if (/^[1-9][0-9]*$/.test(linkedId) && Number.isSafeInteger(Number(linkedId))) await openReservationDetail({id:Number(linkedId)});
});
</script>

<template>
  <section class="page-header"><h1>预约管理</h1><p>查询线上预约、到店开场与续场，追溯对应的收退款和账户变动。</p></section>
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
        <el-form-item label="客户"><el-input v-model="reservationFilters.username" maxlength="50" placeholder="账号、姓名或联系方式" @keyup.enter="refreshReservations(true)" /></el-form-item>
        <el-form-item label="场地">
          <el-select v-model="reservationFilters.court_id" clearable filterable class="medium-select" @change="refreshReservations(true)">
            <el-option v-for="court in courtOptions" :key="court.id" :label="`${court.court_no} ${court.court_name}`" :value="String(court.id)" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源"><el-select v-model="reservationFilters.source" clearable class="short-select" @change="refreshReservations(true)"><el-option label="线上预约" value="online" /><el-option label="到店开场" value="walk_in" /><el-option label="到店续场" value="walk_in_extension" /></el-select></el-form-item>
        <el-form-item label="支付渠道"><el-select v-model="reservationFilters.pay_method" clearable class="medium-select" @change="refreshReservations(true)"><el-option label="储值余额" value="balance" /><el-option label="模拟支付宝" value="mock_alipay" /></el-select></el-form-item>
        <el-form-item label="开单经办"><el-input v-model="reservationFilters.operator" maxlength="50" placeholder="经办用户名或昵称" @keyup.enter="refreshReservations(true)" /></el-form-item>
        <el-form-item label="完整单号"><el-input v-model="reservationFilters.order_no" maxlength="64" placeholder="预约、订单、支付或退款号" @keyup.enter="refreshReservations(true)" /></el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="reservationFilters.date_from" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="reservationFilters.date_to" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item><el-button type="primary" @click="refreshReservations(true)">查询预约</el-button></el-form-item>
      </el-form>

      <p class="filter-description">日期按场次日期筛选；开单经办是创建人员，实际收款与退款经办请查看详情。</p>
      <el-table :data="reservations" empty-text="暂无预约数据" stripe class="booking-list-table">
        <el-table-column prop="reservation_no" label="预约号" min-width="150" />
        <el-table-column label="客户" min-width="120"><template #default="{ row }">{{ row.guest_name || row.nickname || row.username || '散客' }}</template></el-table-column>
        <el-table-column label="来源 / 经办" min-width="160"><template #default="{ row }">{{ row.source==='walk_in' ? '到店开场' : row.source==='walk_in_extension' ? '到店续场' : '线上预约' }}<br />{{ row.operator_name_snapshot || '—' }}</template></el-table-column>
        <el-table-column prop="court_name" label="场地" min-width="110" />
        <el-table-column prop="reserve_date" label="日期" min-width="115" />
        <el-table-column label="时间" min-width="120"><template #default="{ row }">{{ row.start_time }}-{{ row.end_time }}</template></el-table-column>
        <el-table-column label="应付金额" min-width="120"><template #default="{ row }">{{ formatMoney(row.payable_amount_cents) }}</template></el-table-column>
        <el-table-column label="支付渠道" min-width="125"><template #default="{ row }">{{ payMethodText(row.order_pay_method) }}</template></el-table-column>
        <el-table-column label="状态" min-width="100"><template #default="{ row }"><el-tag :type="statusTagType(row.status)" effect="plain">{{ reservationStatusText(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="到场" min-width="90"><template #default="{ row }">{{ attendanceText(row) }}</template></el-table-column>
        <el-table-column label="操作" fixed="right" width="132">
          <template #default="{ row }">
            <el-button link type="primary" @click="openReservationDetail(row)">详情</el-button>
            <el-button link type="danger" :disabled="mutating || Boolean(row.attendance_outcome) || !['pending', 'confirmed'].includes(row.status)" @click="cancelAdminReservation(row)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="booking-list-cards" aria-label="订场记录">
        <p v-if="!reservations.length" class="quiet-state">暂无符合条件的订场</p>
        <article v-for="row in reservations" :key="row.id">
          <div class="booking-card-title"><strong>{{ row.guest_name || row.nickname || row.username || '散客' }}</strong><span>{{ reservationStatusText(row.status) }}</span></div>
          <p>{{ row.court_name }} · {{ row.reserve_date }}<br />{{ row.start_time }}–{{ row.end_time }}</p>
          <p>{{ row.source === 'walk_in' ? '到店开场' : row.source === 'walk_in_extension' ? '到店续场' : '线上预约' }} · {{ row.operator_name_snapshot || '历史经办未记录' }}</p>
          <p>{{ payMethodText(row.order_pay_method) }} · {{ formatMoney(row.payable_amount_cents) }} · {{ attendanceText(row) }}</p>
          <small>{{ row.reservation_no }}</small>
          <div><el-button link type="primary" @click="openReservationDetail(row)">查看详情</el-button><el-button link type="danger" :disabled="mutating || Boolean(row.attendance_outcome) || !['pending','confirmed'].includes(row.status)" @click="cancelAdminReservation(row)">取消预约</el-button></div>
        </article>
      </div>
      <el-pagination class="element-pagination" :current-page="reservationPage.page" :page-size="reservationPage.page_size" :total="reservationPage.total" layout="prev, pager, next, total" @current-change="changeReservationPage" />
    </section>
    <el-drawer v-model="reservationDetailVisible" title="预约详情" size="min(600px, 100vw)" class="admin-edit-drawer">
      <div v-if="detailLoading" class="quiet-state" role="status">正在读取预约与收退款凭据…</div>
      <div v-else-if="selectedReservation" class="record-detail">
        <el-descriptions :column="1" border class="compact-descriptions">
          <el-descriptions-item label="预约号">{{ selectedReservation.reservation_no }}</el-descriptions-item>
          <el-descriptions-item label="客户">{{ selectedReservation.guest_name || selectedReservation.nickname || selectedReservation.username || '散客' }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ selectedReservation.source==='walk_in' ? '到店开场' : selectedReservation.source==='walk_in_extension' ? '到店续场' : '线上预约' }}</el-descriptions-item>
          <el-descriptions-item label="经办人">{{ selectedReservation.operator_name_snapshot || '—' }}</el-descriptions-item>
          <el-descriptions-item v-if="selectedReservation.guest_contact || selectedReservation.customer_contact" label="联系方式">{{ selectedReservation.guest_contact || selectedReservation.customer_contact }}</el-descriptions-item>
          <el-descriptions-item v-if="selectedReservation.parent_reservation_id" label="原订场">#{{ selectedReservation.parent_reservation_id }}</el-descriptions-item>
          <el-descriptions-item label="场地">{{ selectedReservation.court_no }} {{ selectedReservation.court_name }}</el-descriptions-item>
          <el-descriptions-item label="日期时间">
            {{ selectedReservation.reserve_date }} {{ selectedReservation.start_time }}-{{ selectedReservation.end_time }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(selectedReservation.status)" effect="plain">{{ reservationStatusText(selectedReservation.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="会员折扣">
            <template v-if="selectedReservation.source && selectedReservation.source!=='online'">散客原价，不享受会员折扣</template>
            <template v-else>{{ memberLevelText(selectedReservation.member_level_snapshot) }} / {{ discountText(selectedReservation.discount_rate) }}</template>
          </el-descriptions-item>
          <el-descriptions-item v-if="selectedReservation.opened_at" label="到店开场时间">{{ selectedReservation.opened_at }}</el-descriptions-item>
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
        <section v-if="selectedReservation.chain.length > 1" class="booking-chain" aria-label="关联场次">
          <h3>开场与续场</h3>
          <article v-for="item in selectedReservation.chain" :key="item.id">
            <strong>{{ item.source === 'walk_in_extension' ? '续场' : '原场次' }} · {{ item.start_time }}–{{ item.end_time }}</strong>
            <p>{{ item.reserve_date }} · {{ item.court_name }} · {{ reservationStatusText(item.status) }} · {{ formatMoney(item.payable_amount_cents) }}</p>
            <el-button link type="primary" :disabled="item.id === selectedReservation.id || mutating" @click="openReservationDetail(item)">{{ item.id === selectedReservation.id ? '当前场次' : '查看该场次' }} · {{ item.reservation_no }}</el-button>
          </article>
        </section>
        <BookingFinancialRecords :booking="selectedReservation" />
      </div>
      <p v-else class="quiet-state">详情未能加载，请关闭后从列表重试。</p>
      <template #footer>
        <div v-if="selectedReservation && !detailLoading" class="booking-detail-actions">
          <el-button v-if="attendanceAllowed(selectedReservation,'checked_in')" type="primary" :loading="mutating" @click="saveAttendance(selectedReservation,'checked_in')">到场核销</el-button>
          <el-button v-if="attendanceAllowed(selectedReservation,'no_show')" :loading="mutating" @click="saveAttendance(selectedReservation,'no_show')">确认未到场</el-button>
          <el-button @click="reservationDetailVisible = false">关闭</el-button>
          <el-button
            v-if="!selectedReservation.attendance_outcome && ['pending', 'confirmed'].includes(selectedReservation.status)"
            type="danger"
            plain
            :loading="mutating"
            @click="cancelAdminReservation(selectedReservation)"
            >
            取消预约
          </el-button>
        </div>
      </template>
    </el-drawer>
  </el-card>
</template>

<style scoped>
.filter-description { color: var(--el-text-color-secondary); font-size: .85rem; line-height: 1.6; }
.booking-chain { margin-top: 1.5rem; }
.booking-chain article { padding: .85rem 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.booking-chain p { font-size: .85rem; line-height: 1.6; margin: .35rem 0; }
.booking-chain .el-button { height: auto; white-space: normal; text-align: left; overflow-wrap: anywhere; }
.booking-list-cards { display: none; }
.booking-detail-actions { display: flex; justify-content: flex-end; gap: .5rem; flex-wrap: wrap; }
.booking-detail-actions .el-button { margin: 0; }
@media (max-width: 640px) {
  .booking-list-table { display: none; }
  .booking-list-cards { display: block; }
  .booking-list-cards article { padding: 1rem 0; border-bottom: 1px solid var(--el-border-color-lighter); }
  .booking-list-cards p { margin: .4rem 0; font-size: .85rem; line-height: 1.7; }
  .booking-list-cards small { display: block; overflow-wrap: anywhere; color: var(--el-text-color-secondary); margin-bottom: .6rem; }
  .booking-card-title { display: flex; justify-content: space-between; gap: .5rem; }
  .booking-card-title span { color: var(--el-text-color-secondary); font-size: .85rem; }
  .element-filter { display: grid; grid-template-columns: minmax(0,1fr); gap: .7rem; }
  .element-filter :deep(.el-form-item) { display: flex; margin: 0; }
  .element-filter :deep(.el-form-item__label) { width: 76px; justify-content: flex-start; }
  .element-filter :deep(.el-form-item__content) { min-width: 0; flex: 1; }
  .element-filter :deep(.el-input), .element-filter :deep(.el-select) { width: 100% !important; min-width: 0; }
}
</style>
