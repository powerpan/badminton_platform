<script setup lang="ts">
import { onMounted, ref } from "vue";
import ProductImage from "../../components/ProductImage.vue";

import { ElMessageBox } from "element-plus";
import { adminCancelShopOrder, adminCompleteShopOrder, adminGetShopOrder, adminGetShopOrders, adminRejectShopOrderRefund } from "../../api/admin";
import { type ShopOrder } from "../../api/shop";
import { type PageState, formatMoney, payMethodText, confirmAction, setSuccess, setError, resetPage, changePage } from "./shared";

const loading = ref(false);

async function changeShopOrderPage(page: number) {
  await changePage(shopOrderPage.value, page, () => refreshShopOrders());
}

const shopOrders = ref<ShopOrder[]>([]);

const selectedShopOrder = ref<ShopOrder | null>(null);

const shopOrderDetailVisible = ref(false);

const shopOrderPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });

const shopOrderFilters = ref({ status: "", username: "" });

function shopOrderStatusType(status: string) {
  const map: Record<string, "success" | "primary" | "info" | "warning"> = {
    paid: "success",
    refund_requested: "warning",
    completed: "primary",
    canceled: "info",
  };
  return map[status] || "info";
}

function shopOrderStatusText(status: string) {
  const map: Record<string, string> = {
    paid: "已支付",
    refund_requested: "退款待审核",
    completed: "已完成",
    canceled: "已取消",
  };
  return map[status] || status;
}

async function loadShopOrders() {
  const response = await adminGetShopOrders({
    status: shopOrderFilters.value.status || undefined,
    username: shopOrderFilters.value.username || undefined,
    page: shopOrderPage.value.page,
    page_size: shopOrderPage.value.page_size,
  });
  shopOrders.value = response.data.items;
  shopOrderPage.value.total = response.data.total;
}

async function refreshShopOrders(reset = false) {
  if (reset) resetPage(shopOrderPage.value);
  loading.value = true;
  try {
    await loadShopOrders();
  } catch (error) {
    setError(error, "商城订单加载失败");
  } finally {
    loading.value = false;
  }
}

async function openShopOrderDetail(order: ShopOrder) {
  loading.value = true;
  try {
    const response = await adminGetShopOrder(order.id);
    selectedShopOrder.value = response.data;
    shopOrderDetailVisible.value = true;
  } catch (error) {
    setError(error, "商城订单详情加载失败");
  } finally {
    loading.value = false;
  }
}

async function completeShopOrder(order: ShopOrder) {
  if (!(await confirmAction(`确认完成订单 ${order.order_no}？完成后不能再退款。`))) return;
  loading.value = true;
  try {
    const response = await adminCompleteShopOrder(order.id);
    if (selectedShopOrder.value?.id === order.id) {
      selectedShopOrder.value = response.data;
    }
    await loadShopOrders();
    setSuccess("订单已完成");
  } catch (error) {
    setError(error, "完成订单失败");
  } finally {
    loading.value = false;
  }
}

async function cancelAdminShopOrder(order: ShopOrder) {
  const actionText = order.status === "refund_requested" ? "通过退款申请" : "取消订单并退回会员余额";
  if (!(await confirmAction(`确认${actionText} ${order.order_no}？`))) return;
  loading.value = true;
  try {
    const response = await adminCancelShopOrder(order.id);
    if (selectedShopOrder.value?.id === order.id) {
      selectedShopOrder.value = response.data;
    }
    await loadShopOrders();
    setSuccess("订单已取消并退款");
  } catch (error) {
    setError(error, "取消商城订单失败");
  } finally {
    loading.value = false;
  }
}

async function rejectRefund(order: ShopOrder) {
  let reason = "管理员驳回商城订单退款申请";
  try {
    const result = await ElMessageBox.prompt(`请输入驳回订单 ${order.order_no} 退款申请的原因`, "驳回退款申请", {
      confirmButtonText: "确认驳回",
      cancelButtonText: "取消",
      inputValue: reason,
      inputPattern: /^.{1,255}$/,
      inputErrorMessage: "驳回原因需填写且不能超过255个字符",
      type: "warning",
    });
    reason = String(result.value || reason).trim();
  } catch {
    return;
  }
  loading.value = true;
  try {
    const response = await adminRejectShopOrderRefund(order.id, { reason });
    if (selectedShopOrder.value?.id === order.id) {
      selectedShopOrder.value = response.data;
    }
    await loadShopOrders();
    setSuccess("退款申请已驳回");
  } catch (error) {
    setError(error, "驳回退款申请失败");
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadShopOrders();
  } catch (error) { setError(error, "数据加载失败"); }
  finally { loading.value = false; }
});
</script>

<template>
  <section class="page-header"><h1>商城订单</h1><p>处理商品领取、订单完成与退款。</p></section>
  <el-card shadow="never" class="admin-shell element-admin">
    <section v-loading="loading" class="admin-section">
      <el-card shadow="never" class="panel-card">
        <template #header><strong>订单管理</strong></template>
        <el-form inline class="element-filter">
          <el-form-item label="状态">
            <el-select v-model="shopOrderFilters.status" clearable class="short-select" @change="refreshShopOrders(true)">
              <el-option label="已支付" value="paid" />
              <el-option label="退款待审核" value="refund_requested" />
              <el-option label="已完成" value="completed" />
              <el-option label="已取消" value="canceled" />
            </el-select>
          </el-form-item>
          <el-form-item label="用户"><el-input v-model="shopOrderFilters.username" placeholder="用户名或昵称" @keyup.enter="refreshShopOrders(true)" /></el-form-item>
          <el-form-item><el-button type="primary" @click="refreshShopOrders(true)">查询订单</el-button></el-form-item>
        </el-form>
        <el-table :data="shopOrders" empty-text="暂无商城订单" stripe>
          <el-table-column prop="order_no" label="订单号" min-width="150" />
          <el-table-column label="用户" min-width="120"><template #default="{ row }">{{ row.nickname || row.username }}</template></el-table-column>
          <el-table-column label="金额" width="120"><template #default="{ row }">{{ formatMoney(row.total_amount_cents) }}</template></el-table-column>
          <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="shopOrderStatusType(row.status)" effect="plain">{{ shopOrderStatusText(row.status) }}</el-tag></template></el-table-column>
          <el-table-column label="操作" fixed="right" width="260">
            <template #default="{ row }">
              <el-button link type="primary" @click="openShopOrderDetail(row)">详情</el-button>
              <el-button link type="primary" :disabled="row.status !== 'paid'" @click="completeShopOrder(row)">完成</el-button>
              <el-button
                link
                type="warning"
                :disabled="!['paid', 'refund_requested'].includes(row.status)"
                @click="cancelAdminShopOrder(row)"
                >
                {{ row.status === "refund_requested" ? "通过退款" : "管理员退款" }}
              </el-button>
              <el-button
                v-if="row.status === 'refund_requested'"
                link
                type="danger"
                @click="rejectRefund(row)"
                >
                驳回申请
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination class="element-pagination" :current-page="shopOrderPage.page" :page-size="shopOrderPage.page_size" :total="shopOrderPage.total" layout="prev, pager, next, total" @current-change="changeShopOrderPage" />
      </el-card>
    </section>
    <el-drawer v-model="shopOrderDetailVisible" title="商城订单详情" size="min(600px, 100vw)" class="admin-edit-drawer">
      <div v-if="selectedShopOrder" class="order-detail">
        <el-descriptions :column="1" border class="compact-descriptions">
          <el-descriptions-item label="订单号">{{ selectedShopOrder.order_no }}</el-descriptions-item>
          <el-descriptions-item label="用户">{{ selectedShopOrder.nickname || selectedShopOrder.username }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ shopOrderStatusText(selectedShopOrder.status) }}</el-descriptions-item>
          <el-descriptions-item label="金额">{{ formatMoney(selectedShopOrder.total_amount_cents) }}</el-descriptions-item>
          <el-descriptions-item label="支付方式">{{ payMethodText(selectedShopOrder.pay_method) }}</el-descriptions-item>
          <el-descriptions-item label="支付时间">{{ selectedShopOrder.paid_at || "-" }}</el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ selectedShopOrder.completed_at || "-" }}</el-descriptions-item>
          <el-descriptions-item label="取消时间">{{ selectedShopOrder.canceled_at || "-" }}</el-descriptions-item>
          <el-descriptions-item label="取消原因">{{ selectedShopOrder.cancel_reason || "-" }}</el-descriptions-item>
          <el-descriptions-item label="退款申请时间">{{ selectedShopOrder.refund_requested_at || "-" }}</el-descriptions-item>
          <el-descriptions-item label="退款申请原因">{{ selectedShopOrder.refund_request_reason || "-" }}</el-descriptions-item>
          <el-descriptions-item label="退款审核时间">{{ selectedShopOrder.refund_reviewed_at || "-" }}</el-descriptions-item>
          <el-descriptions-item label="退款驳回原因">{{ selectedShopOrder.refund_reject_reason || "-" }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ selectedShopOrder.remark || "-" }}</el-descriptions-item>
        </el-descriptions>
        <div class="cart-list detail-items">
          <article v-for="item in selectedShopOrder.items || []" :key="item.id" class="cart-item">
            <ProductImage :name="item.product_name_snapshot" :src="item.image_url_snapshot" />
            <div>
              <strong>{{ item.product_name_snapshot }}</strong>
              <span>{{ formatMoney(item.price_cents) }} x {{ item.quantity }}</span>
            </div>
            <b>{{ formatMoney(item.subtotal_cents) }}</b>
          </article>
        </div>
        <div class="dialog-actions">
          <el-button @click="shopOrderDetailVisible = false">关闭</el-button>
          <el-button v-if="selectedShopOrder.status === 'paid'" type="primary" :loading="loading" @click="completeShopOrder(selectedShopOrder)">完成订单</el-button>
          <el-button
            v-if="['paid', 'refund_requested'].includes(selectedShopOrder.status)"
            type="warning"
            :loading="loading"
            @click="cancelAdminShopOrder(selectedShopOrder)"
            >
            {{ selectedShopOrder.status === "refund_requested" ? "通过退款" : "管理员退款" }}
          </el-button>
          <el-button
            v-if="selectedShopOrder.status === 'refund_requested'"
            type="danger"
            plain
            :loading="loading"
            @click="rejectRefund(selectedShopOrder)"
            >
            驳回申请
          </el-button>
        </div>
      </div>
    </el-drawer>
  </el-card>
</template>
