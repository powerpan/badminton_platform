<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  cancelShopOrder,
  getMyShopOrders,
  getShopOrder,
  type ShopOrder,
} from "../api/shop";
import { useAuthStore } from "../stores/auth";

const authStore = useAuthStore();
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
    completed: "已完成",
    canceled: "已取消",
  };
  return map[status] || status;
}

function statusTagType(status: string) {
  const map: Record<string, "success" | "primary" | "info"> = {
    paid: "success",
    completed: "primary",
    canceled: "info",
  };
  return map[status] || "info";
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

async function cancelOrder(order: ShopOrder) {
  try {
    await ElMessageBox.confirm(`确认取消订单 ${order.order_no} 并退回余额？`, "取消订单", {
      confirmButtonText: "确认取消",
      cancelButtonText: "关闭",
      type: "warning",
    });
  } catch {
    return;
  }
  loading.value = true;
  try {
    await cancelShopOrder(order.id);
    await authStore.fetchProfile();
    await loadOrders();
    if (selectedOrder.value?.id === order.id) {
      const response = await getShopOrder(order.id);
      selectedOrder.value = response.data;
    }
    ElMessage.success("订单已取消并退款");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "取消订单失败");
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
    <p class="eyebrow">商城订单</p>
    <h1>我的商城订单</h1>
    <p>查看余额支付订单、领取状态和退款记录。</p>
  </section>

  <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />

  <el-card shadow="never" class="panel-card list-page-card" v-loading="loading">
    <div class="list-toolbar">
      <el-radio-group v-model="filter" @change="() => loadOrders(true)">
        <el-radio-button :value="''">全部</el-radio-button>
        <el-radio-button :value="'paid'">已支付</el-radio-button>
        <el-radio-button :value="'completed'">已完成</el-radio-button>
        <el-radio-button :value="'canceled'">已取消</el-radio-button>
      </el-radio-group>
      <RouterLink class="inline-action" to="/shop">继续购物</RouterLink>
    </div>

    <el-empty v-if="orders.length === 0 && !loading" description="暂无商城订单" />
    <div v-else class="order-list">
      <article v-for="order in orders" :key="order.id" class="order-item">
        <div>
          <strong>{{ order.order_no }}</strong>
          <span>{{ order.created_at }}</span>
        </div>
        <div>
          <el-tag :type="statusTagType(order.status)" effect="plain">{{ statusText(order.status) }}</el-tag>
          <b>{{ formatMoney(order.total_amount_cents) }}</b>
        </div>
        <div class="order-actions">
          <el-button link type="primary" @click="openDetail(order)">详情</el-button>
          <el-button v-if="order.status === 'paid'" link type="warning" @click="cancelOrder(order)">取消退款</el-button>
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

  <el-dialog v-model="detailVisible" title="订单详情" width="680px">
    <div v-if="selectedOrder" class="order-detail">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="订单号">{{ selectedOrder.order_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ statusText(selectedOrder.status) }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ formatMoney(selectedOrder.total_amount_cents) }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ selectedOrder.remark || "-" }}</el-descriptions-item>
      </el-descriptions>
      <div class="cart-list">
        <article v-for="item in selectedOrder.items || []" :key="item.id" class="cart-item">
          <img :src="item.image_url_snapshot || '/courts/default-court.png'" :alt="item.product_name_snapshot" />
          <div>
            <strong>{{ item.product_name_snapshot }}</strong>
            <span>{{ formatMoney(item.price_cents) }} x {{ item.quantity }}</span>
          </div>
          <b>{{ formatMoney(item.subtotal_cents) }}</b>
        </article>
      </div>
      <div class="dialog-actions">
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button v-if="selectedOrder.status === 'paid'" type="warning" @click="cancelOrder(selectedOrder)">
          取消退款
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>
