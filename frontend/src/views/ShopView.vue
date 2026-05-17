<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import { createShopOrder, getShopProducts, type ShopProduct } from "../api/shop";
import { useAuthStore } from "../stores/auth";

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

const cartItems = computed(() => Object.values(cart.value));
const cartTotalCents = computed(() =>
  cartItems.value.reduce((sum, item) => sum + item.product.price_cents * item.quantity, 0),
);
const balanceCents = computed(() => authStore.user?.member.balance_cents || 0);
const balanceEnough = computed(() => balanceCents.value >= cartTotalCents.value);

function formatMoney(cents: number | null | undefined) {
  return `￥${((cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function productImage(product: ShopProduct) {
  return product.image_url || "/courts/default-court.png";
}

function stockTagType(product: ShopProduct) {
  if (product.stock <= 0) return "danger";
  if (product.stock <= 5) return "warning";
  return "success";
}

function normalizeQuantity(product: ShopProduct, value: number | undefined) {
  return Math.min(product.stock, Math.max(1, Number(value || 1)));
}

async function loadProducts(reset = false) {
  if (reset) page.value.page = 1;
  loading.value = true;
  errorMessage.value = "";
  try {
    const response = await getShopProducts({
      keyword: keyword.value || undefined,
      page: page.value.page,
      page_size: page.value.page_size,
    });
    products.value = response.data.items;
    page.value.total = response.data.total;
    products.value.forEach((product) => {
      if (!quantities.value[product.id]) quantities.value[product.id] = 1;
    });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "商品加载失败";
  } finally {
    loading.value = false;
  }
}

function addToCart(product: ShopProduct) {
  if (product.stock <= 0) {
    ElMessage.error("商品库存不足");
    return;
  }
  const quantity = normalizeQuantity(product, quantities.value[product.id]);
  const existing = cart.value[product.id];
  const nextQuantity = Math.min(product.stock, (existing?.quantity || 0) + quantity);
  cart.value = {
    ...cart.value,
    [product.id]: { product, quantity: nextQuantity },
  };
  drawerVisible.value = true;
}

function updateCartQuantity(item: CartLine, quantity: number) {
  cart.value = {
    ...cart.value,
    [item.product.id]: { ...item, quantity: normalizeQuantity(item.product, quantity) },
  };
}

function handleCartQuantityChange(item: CartLine, value: number | undefined) {
  updateCartQuantity(item, Number(value || 1));
}

function removeCartItem(productId: number) {
  const nextCart = { ...cart.value };
  delete nextCart[productId];
  cart.value = nextCart;
}

async function payOrder() {
  if (!authStore.isLoggedIn) {
    await router.push({ name: "login", query: { redirect: route.fullPath } });
    return;
  }
  if (cartItems.value.length === 0) {
    ElMessage.error("请先选择商品");
    return;
  }
  if (!balanceEnough.value) {
    ElMessage.error("会员余额不足，请联系管理员充值或调整余额");
    return;
  }
  try {
    await ElMessageBox.confirm(
      `确认使用会员余额支付 ${formatMoney(cartTotalCents.value)}？支付后商品库存会立即扣减。`,
      "余额支付确认",
      { confirmButtonText: "确认支付", cancelButtonText: "取消", type: "warning" },
    );
  } catch {
    return;
  }
  paying.value = true;
  try {
    await createShopOrder({
      items: cartItems.value.map((item) => ({ product_id: item.product.id, quantity: item.quantity })),
      remark: remark.value,
    });
    cart.value = {};
    remark.value = "";
    drawerVisible.value = false;
    await authStore.fetchProfile();
    await loadProducts();
    ElMessage.success("订单已支付");
    await router.push("/shop/orders");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "订单支付失败");
    await loadProducts();
  } finally {
    paying.value = false;
  }
}

async function changePage(nextPage: number) {
  page.value.page = nextPage;
  await loadProducts();
}

onMounted(() => loadProducts());
</script>

<template>
  <section class="page-header">
    <p class="eyebrow">商城</p>
    <h1>场馆商城</h1>
    <p>使用会员余额购买球馆用品，到店领取。</p>
  </section>

  <el-alert v-if="errorMessage" class="page-alert" :title="errorMessage" type="error" show-icon :closable="false" />

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
        <img :src="productImage(product)" :alt="product.product_name" />
        <div class="shop-product-body">
          <div class="feature-card-head">
            <el-tag :type="stockTagType(product)" effect="plain">库存 {{ product.stock }}</el-tag>
            <el-tag type="info" effect="plain">已售 {{ product.sold_count }}</el-tag>
          </div>
          <h2>{{ product.product_name }}</h2>
          <p>{{ product.description || "到店领取商品" }}</p>
          <strong>{{ formatMoney(product.price_cents) }}</strong>
          <div class="shop-buy-row">
            <el-input-number
              v-model="quantities[product.id]"
              :min="1"
              :max="Math.max(product.stock, 1)"
              :disabled="product.stock <= 0"
            />
            <el-button type="primary" :disabled="product.stock <= 0" @click="addToCart(product)">
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

  <el-drawer v-model="drawerVisible" title="购物车" size="min(420px, 100vw)" class="shop-cart-drawer">
    <el-empty v-if="cartItems.length === 0" description="购物车为空" />
    <div v-else class="cart-list">
      <article v-for="item in cartItems" :key="item.product.id" class="cart-item">
        <img :src="productImage(item.product)" :alt="item.product.product_name" />
        <div>
          <strong>{{ item.product.product_name }}</strong>
          <span>{{ formatMoney(item.product.price_cents) }}</span>
          <el-input-number
            :model-value="item.quantity"
            :min="1"
            :max="Math.max(item.product.stock, 1)"
            @change="handleCartQuantityChange(item, $event)"
          />
        </div>
        <el-button link type="danger" @click="removeCartItem(item.product.id)">移除</el-button>
      </article>

      <el-descriptions :column="1" border class="compact-descriptions">
        <el-descriptions-item label="当前余额">{{ formatMoney(balanceCents) }}</el-descriptions-item>
        <el-descriptions-item label="订单合计">{{ formatMoney(cartTotalCents) }}</el-descriptions-item>
      </el-descriptions>
      <el-alert
        v-if="authStore.isLoggedIn && !balanceEnough"
        class="page-alert"
        title="会员余额不足，无法支付订单"
        type="error"
        show-icon
        :closable="false"
      />
      <el-form label-position="top" class="element-form">
        <el-form-item label="备注">
          <el-input v-model="remark" maxlength="255" placeholder="可选，如领取时间" />
        </el-form-item>
        <el-button type="primary" size="large" :loading="paying" :disabled="authStore.isLoggedIn && !balanceEnough" @click="payOrder">
          余额支付
        </el-button>
      </el-form>
    </div>
  </el-drawer>
</template>
