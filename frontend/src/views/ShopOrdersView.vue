<script setup lang="ts">
import ProductImage from "../components/ProductImage.vue";
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  getMyShopOrders,
  getShopOrder,
  requestShopOrderRefund,
  type ShopOrder,
} from "../api/shop";

const orders = ref<ShopOrder[]>([]);
const selectedOrder = ref<ShopOrder | null>(null);
const detailVisible = ref(false);
const filter = ref("");
const page = ref({ page: 1, page_size: 10, total: 0 });
const loading = ref(false);
const errorMessage = ref("");

function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function statusText(status: string) {
  const map: Record<string, string> = {
    paid: "已支付",
    refund_requested: "退款待审核",
    completed: "已完成",
    canceled: "已取消",
  };
  return map[status] || status;
}

function statusTagType(status: string) {
  const map: Record<string, "success" | "primary" | "info" | "warning"> = {
    paid: "success",
    refund_requested: "warning",
    completed: "primary",
    canceled: "info",
  };
  return map[status] || "info";
}

function payMethodText(value: string | null | undefined) {
  return value === "balance" ? "会员余额" : value || "-";
}

async function loadOrders(reset = false) {
  if (reset) page.value.page = 1;
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await getMyShopOrders({
      status: filter.value || undefined,
      page: page.value.page,
      page_size: page.value.page_size,
    });
    orders.value = response.data.items;
    page.value.total = response.data.total;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "订单加载失败";
  } finally {
    loading.value = false;
  }
}

async function openDetail(order: ShopOrder) {
  loading.value = true;
  try {
    const response = await getShopOrder(order.id);
    selectedOrder.value = response.data;
    detailVisible.value = true;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "订单详情加载失败");
  } finally {
    loading.value = false;
  }
}

async function requestRefund(order: ShopOrder) {
  let reason = "用户申请商城订单退款";
  try {
    const result = await ElMessageBox.prompt(`请输入订单 ${order.order_no} 的退款原因`, "申请退款", {
      confirmButtonText: "提交申请",
      cancelButtonText: "取消",
      inputValue: reason,
      inputPattern: /^.{1,255}$/,
      inputErrorMessage: "退款原因需填写且不能超过255个字符",
      type: "warning",
    });
    reason = String(result.value || reason).trim();
  } catch {
    return;
  }
  loading.value = true;
  try {
    await requestShopOrderRefund(order.id, { reason });
    await loadOrders();
    if (selectedOrder.value?.id === order.id) {
      const response = await getShopOrder(order.id);
      selectedOrder.value = response.data;
    }
    ElMessage.success("退款申请已提交，等待管理员审核");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "提交退款申请失败");
  } finally {
    loading.value = false;
  }
}

async function changePage(nextPage: number) {
  page.value.page = nextPage;
  await loadOrders();
}

onMounted(() => loadOrders());
</script>

<template>
  <section class="page-header">
    <h1>我的商城订单</h1>
    <p>查看余额支付订单、领取状态和退款申请记录。</p>
  </section>

  <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />

  <el-card shadow="never" class="panel-card list-page-card" v-loading="loading">
    <div class="list-toolbar">
      <el-radio-group v-model="filter" @change="() => loadOrders(true)">
        <el-radio-button :value="''">全部</el-radio-button>
        <el-radio-button :value="'paid'">已支付</el-radio-button>
        <el-radio-button :value="'refund_requested'">退款待审核</el-radio-button>
        <el-radio-button :value="'completed'">已完成</el-radio-button>
        <el-radio-button :value="'canceled'">已取消</el-radio-button>
      </el-radio-group>
      <RouterLink class="inline-action" to="/shop">继续购物</RouterLink>
    </div>

    <el-empty v-if="orders.length === 0 && !loading" description="暂无商城订单" />
    <div v-else class="order-list">
      <article v-for="order in orders" :key="order.id" class="order-item">
        <div class="order-main">
          <strong>{{ order.order_no }}</strong>
          <span>{{ order.created_at }}</span>
        </div>
        <div>
          <el-tag :type="statusTagType(order.status)" effect="plain">{{ statusText(order.status) }}</el-tag>
          <b>{{ formatMoney(order.total_amount_cents) }}</b>
        </div>
        <div class="order-actions">
          <el-button link type="primary" @click="openDetail(order)">详情</el-button>
          <el-button v-if="order.status === 'paid'" link type="warning" @click="requestRefund(order)">申请退款</el-button>
        </div>
      </article>
    </div>

    <el-pagination
      class="element-pagination"
      :current-page="page.page"
      :page-size="page.page_size"
      :total="page.total"
      layout="prev, pager, next, total"
      @current-change="changePage"
    />
  </el-card>

  <el-dialog v-model="detailVisible" title="订单详情" width="min(680px, 92vw)" class="detail-dialog">
    <div v-if="selectedOrder" class="order-detail">
      <el-descriptions :column="1" border class="compact-descriptions">
        <el-descriptions-item label="订单号">{{ selectedOrder.order_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ statusText(selectedOrder.status) }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ formatMoney(selectedOrder.total_amount_cents) }}</el-descriptions-item>
        <el-descriptions-item label="支付方式">{{ payMethodText(selectedOrder.pay_method) }}</el-descriptions-item>
        <el-descriptions-item label="支付时间">{{ selectedOrder.paid_at || "-" }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ selectedOrder.completed_at || "-" }}</el-descriptions-item>
        <el-descriptions-item label="取消时间">{{ selectedOrder.canceled_at || "-" }}</el-descriptions-item>
        <el-descriptions-item label="取消原因">{{ selectedOrder.cancel_reason || "-" }}</el-descriptions-item>
        <el-descriptions-item label="退款申请时间">{{ selectedOrder.refund_requested_at || "-" }}</el-descriptions-item>
        <el-descriptions-item label="退款申请原因">{{ selectedOrder.refund_request_reason || "-" }}</el-descriptions-item>
        <el-descriptions-item label="退款审核时间">{{ selectedOrder.refund_reviewed_at || "-" }}</el-descriptions-item>
        <el-descriptions-item label="退款驳回原因">{{ selectedOrder.refund_reject_reason || "-" }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ selectedOrder.remark || "-" }}</el-descriptions-item>
      </el-descriptions>
      <div class="cart-list">
        <article v-for="item in selectedOrder.items || []" :key="item.id" class="cart-item">
          <ProductImage :name="item.product_name_snapshot" :src="item.image_url_snapshot" />
          <div>
            <strong>{{ item.product_name_snapshot }}</strong>
            <span>{{ formatMoney(item.price_cents) }} x {{ item.quantity }}</span>
          </div>
          <b>{{ formatMoney(item.subtotal_cents) }}</b>
        </article>
      </div>
      <div class="dialog-actions">
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="selectedOrder.status === 'paid'" type="warning" @click="requestRefund(selectedOrder)">
          申请退款
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>
