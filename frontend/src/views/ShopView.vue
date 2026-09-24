<script setup lang="ts">
import ProductImage from "../components/ProductImage.vue";
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { createShopOrder, getShopProducts, quoteShopOrder, type ShopQuote, type ShopProduct } from "../api/shop";
import { useAuthStore } from "../stores/auth";
import PaymentDialog from '../components/PaymentDialog.vue';
import type { PaymentMethod } from '../api/payment';
import { ApiRequestError } from '../api/http';

interface CartLine {
  product: ShopProduct;
  quantity: number;
}

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();
const products = ref<ShopProduct[]>([]);
const quantities = ref<Record<number, number>>({});
const cart = ref<Record<number, CartLine>>({});
const keyword = ref("");
const remark = ref("");
const drawerVisible = ref(false);
const page = ref({ page: 1, page_size: 12, total: 0 });
const loading = ref(false);
const paying = ref(false);
const errorMessage = ref("");
const checkoutError = ref("");
const cartNotice = ref("");
const checkoutBalance = ref<ShopQuote>();
const payMethod = ref<PaymentMethod>('balance');
const paymentId = ref<number | null>(null), paymentVisible = ref(false);
const pendingRequest = ref<Parameters<typeof createShopOrder>[0] | null>(null);
const recoveryKey = () => `bf-shop-request:${authStore.user?.id}`;
function clearPendingRequest() { pendingRequest.value = null; sessionStorage.removeItem(recoveryKey()); }
const availableStock = (product: ShopProduct) => product.available_stock ?? product.stock;
let productVersion = 0;

const cartItems = computed(() => Object.values(cart.value));
const cartTotalCents = computed(() =>
  cartItems.value.reduce((sum, item) => sum + item.product.price_cents * item.quantity, 0),
);
const balanceCents = computed(() => checkoutBalance.value?.balance_cents ?? authStore.user?.member.balance_cents ?? 0);
const availableBalanceCents = computed(() => checkoutBalance.value?.available_balance_cents ?? balanceCents.value);

function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}


function stockTagType(product: ShopProduct) {
  if (availableStock(product) <= 0) return "danger";
  if (availableStock(product) <= 5) return "warning";
  return "success";
}

function normalizeQuantity(product: ShopProduct, value: number | undefined) {
  return Math.min(99, Math.max(1, Math.floor(Number(value || 1))));
}

async function loadProducts(reset = false) {
  const version = ++productVersion;
  if (reset) page.value.page = 1;
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await getShopProducts({
      keyword: keyword.value || undefined,
      page: page.value.page,
      page_size: page.value.page_size,
    });
    if (version !== productVersion) return;
    products.value = response.data.items;
    page.value.total = response.data.total;
    products.value.forEach((product) => {
      if (!quantities.value[product.id]) quantities.value[product.id] = 1;
    });
  } catch (error) {
    if (version === productVersion) errorMessage.value = error instanceof Error ? error.message : "商品加载失败";
  } finally {
    if (version === productVersion) loading.value = false;
  }
}

function addToCart(product: ShopProduct) {
  if (paying.value) return;
  if (availableStock(product) <= 0) {
    ElMessage.error("商品库存不足");
    return;
  }
  const quantity = normalizeQuantity(product, quantities.value[product.id]);
  const existing = cart.value[product.id];
  const nextQuantity = Math.min(99, availableStock(product), (existing?.quantity || 0) + quantity);
  cart.value = {
    ...cart.value,
    [product.id]: { product, quantity: nextQuantity },
  };
  drawerVisible.value = true;
}

function updateCartQuantity(item: CartLine, quantity: number) {
  if (paying.value) return;
  checkoutError.value = "";
  cart.value = {
    ...cart.value,
    [item.product.id]: { ...item, quantity: normalizeQuantity(item.product, quantity) },
  };
}

function handleCartQuantityChange(item: CartLine, value: number | undefined) {
  updateCartQuantity(item, Number(value || 1));
}

function removeCartItem(productId: number) {
  if (paying.value) return;
  checkoutError.value = "";
  const nextCart = { ...cart.value };
  delete nextCart[productId];
  cart.value = nextCart;
}

async function refreshCart() {
  const response = await quoteShopOrder(cartItems.value.map(item => ({ product_id: item.product.id, quantity: item.quantity })), payMethod.value);
  const quote = response.data;
  const changed = quote.items.some(item => cart.value[item.product.id]?.product.price_cents !== item.product.price_cents);
  cart.value = Object.fromEntries(quote.items.map(item => [item.product.id, { product: item.product, quantity: item.quantity }]));
  const latest = new Map(quote.items.map(item => [item.product.id, item.product]));
  products.value = products.value.map(product => latest.get(product.id) || product);
  checkoutBalance.value = quote;
  cartNotice.value = changed ? '商品价格已更新，请核对最新金额后确认支付。' : '';
  return quote;
}

async function payOrder() {
  if (paying.value) return;
  if (!authStore.isLoggedIn) {
    await router.push({ name: 'login', query: { redirect: route.fullPath } });
    return;
  }
  if (!pendingRequest.value && !cartItems.value.length) { ElMessage.error('请先选择商品'); return; }
  paying.value = true; checkoutError.value = ''; cartNotice.value = '';
  try {
    if (!pendingRequest.value) {
      const quote = await refreshCart();
      if (!quote.can_checkout) { checkoutError.value = quote.issues.join('；'); return; }
      const payload = { items: quote.items.map(item => ({ product_id: item.product.id, quantity: item.quantity, expected_price_cents: item.product.price_cents })), remark: remark.value, pay_method: payMethod.value, request_key: crypto.randomUUID() };
      try {
        await ElMessageBox.confirm(
          `${cartNotice.value}订单合计 ${formatMoney(quote.total_amount_cents)}，使用${payMethod.value === 'balance' ? '储值余额' : '模拟支付宝'}。确认后暂留商品，请在付款期限内完成支付。`,
          '确认商城订单', { confirmButtonText: '确认下单', cancelButtonText: '返回修改' },
        );
      } catch { return; }
      pendingRequest.value = payload;
      sessionStorage.setItem(recoveryKey(), JSON.stringify(payload));
    }
    const response = await createShopOrder(pendingRequest.value);
    clearPendingRequest();
    cart.value = {}; remark.value = ''; drawerVisible.value = false; checkoutBalance.value = undefined;
    if (response.data.payment_id) { paymentId.value = response.data.payment_id; paymentVisible.value = true; }
    else await router.push('/shop/orders');
    void loadProducts();
  } catch (error) {
    if (error instanceof ApiRequestError && error.status && error.status >= 400 && error.status < 500) clearPendingRequest();
    checkoutError.value = error instanceof Error ? error.message : '下单结果尚未确认';
    if (cartItems.value.length) {
      try { await refreshCart(); } catch { /* Keep the cart for an explicit retry. */ }
    }
    ElMessage.error(checkoutError.value);
  } finally { paying.value = false; }
}

async function changePage(nextPage: number) {
  page.value.page = nextPage;
  await loadProducts();
}

async function paymentUpdated() { await Promise.allSettled([authStore.fetchProfile(), loadProducts()]); }
onMounted(() => {
  try { pendingRequest.value = JSON.parse(sessionStorage.getItem(recoveryKey()) || 'null'); } catch { clearPendingRequest(); }
  void loadProducts();
});
</script>

<template>
  <section class="page-header">
    <h1>场馆商城</h1>
    <p>选购球馆用品，使用储值余额或模拟支付宝付款，到店凭码领取。</p>
  </section>

  <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />
  <el-alert v-if="pendingRequest" title="上次下单结果尚未确认" type="warning" :closable="false" class="page-alert">
    <p>请先恢复上次订单，避免重复购买。恢复会沿用原购物清单及金额。</p>
    <el-button :loading="paying" @click="payOrder">恢复上次订单</el-button>
    <RouterLink to="/shop/orders" class="inline-action">查看我的订单</RouterLink>
  </el-alert>

  <el-card shadow="never" class="panel-card shop-toolbar" v-loading="loading">
    <el-form inline class="element-filter" @submit.prevent="loadProducts(true)">
      <el-form-item label="商品">
        <el-input v-model="keyword" placeholder="名称或编号" clearable @keyup.enter="loadProducts(true)" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" native-type="submit">搜索</el-button>
        <el-button @click="drawerVisible = true">购物车 {{ cartItems.length }}</el-button>
        <RouterLink class="inline-action" to="/shop/orders">我的订单</RouterLink>
      </el-form-item>
    </el-form>
  </el-card>

  <el-card shadow="never" class="panel-card list-page-card" v-loading="loading">
    <el-empty v-if="products.length === 0 && !loading" description="暂无商品" />
    <div v-else class="shop-grid">
      <article v-for="product in products" :key="product.id" class="shop-product-card">
        <ProductImage :name="product.product_name" :src="product.image_url" />
        <div class="shop-product-body">
          <div class="feature-card-head">
            <el-tag :type="stockTagType(product)" effect="plain">可售 {{ availableStock(product) }}</el-tag>
            <el-tag type="info" effect="plain">已售 {{ product.sold_count }}</el-tag>
          </div>
          <h2>{{ product.product_name }}</h2>
          <p>{{ product.description || "到店领取商品" }}</p>
          <strong>{{ formatMoney(product.price_cents) }}</strong>
          <div class="shop-buy-row">
            <el-input-number
              v-model="quantities[product.id]"
              :min="1"
              :max="Math.min(99, Math.max(availableStock(product), 1))"
              :disabled="availableStock(product) <= 0 || paying || authStore.isStaff || !!pendingRequest"
            />
            <el-button type="primary" :disabled="availableStock(product) <= 0 || paying || authStore.isStaff || !!pendingRequest" @click="addToCart(product)">
              加入购物车
            </el-button>
          </div>
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

  <el-drawer v-model="drawerVisible" title="购物车" size="min(420px, 100vw)" class="shop-cart-drawer" :close-on-click-modal="!paying" :close-on-press-escape="!paying" :show-close="!paying">
    <el-empty v-if="cartItems.length === 0" description="购物车为空" />
    <div v-else class="cart-list">
      <el-alert v-if="cartNotice" :title="cartNotice" type="info" :closable="false" show-icon />
      <el-alert v-if="checkoutError" :title="checkoutError" type="error" :closable="false" show-icon />
      <article v-for="item in cartItems" :key="item.product.id" class="cart-item">
        <ProductImage :name="item.product.product_name" :src="item.product.image_url" />
        <div>
          <strong>{{ item.product.product_name }}</strong>
          <span>{{ formatMoney(item.product.price_cents) }}</span>
          <el-input-number
            :model-value="item.quantity"
            :min="1"
            :max="99"
            :disabled="paying"
            @change="handleCartQuantityChange(item, $event)"
          />
        </div>
        <el-button link type="danger" :disabled="paying" @click="removeCartItem(item.product.id)">移除</el-button>
      </article>

      <el-descriptions :column="1" border class="compact-descriptions">
        <el-descriptions-item label="当前余额">{{ formatMoney(balanceCents) }}</el-descriptions-item>
        <el-descriptions-item v-if="checkoutBalance" label="待付款占用">{{ formatMoney(checkoutBalance.pending_amount_cents) }}</el-descriptions-item>
        <el-descriptions-item v-if="checkoutBalance" label="可用余额">{{ formatMoney(availableBalanceCents) }}</el-descriptions-item>
        <el-descriptions-item label="订单合计">{{ formatMoney(cartTotalCents) }}</el-descriptions-item>
      </el-descriptions>
      <p class="muted-text">结算前将核对最新价格、库存和可用余额。</p>
      <el-form label-position="top" class="element-form">
        <el-form-item label="付款方式">
          <el-radio-group v-model="payMethod" :disabled="paying || !!pendingRequest" @change="checkoutError = ''; checkoutBalance = undefined">
            <el-radio value="balance">储值余额</el-radio><el-radio value="mock_alipay">模拟支付宝</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="remark" :disabled="paying" maxlength="255" placeholder="可选，如领取时间" />
        </el-form-item>
        <el-button type="primary" size="large" :loading="paying" @click="payOrder">
          {{ pendingRequest ? '恢复上次订单' : '确认订单' }}
        </el-button>
      </el-form>
    </div>
  </el-drawer>
  <PaymentDialog v-model="paymentVisible" :payment-id="paymentId" @paid="paymentUpdated" />
</template>
