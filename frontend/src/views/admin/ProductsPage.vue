<script setup lang="ts">
import { onMounted, ref } from "vue";

import { adminCreateShopProduct, adminGetShopProducts, adminUpdateShopProduct, adminUpdateShopProductStatus } from "../../api/admin";
import { type ShopProduct } from "../../api/shop";
import { type PageState, formatMoney, centsToYuanInput, yuanInputToCents, confirmAction, setSuccess, setError, resetPage, changePage } from "./shared";

const loading = ref(false);

async function changeShopProductPage(page: number) {
  await changePage(shopProductPage.value, page, () => refreshShopProducts());
}

const shopProducts = ref<ShopProduct[]>([]);

const shopProductPage = ref<PageState>({ page: 1, page_size: 10, total: 0 });

const shopProductFilters = ref({ status: "", keyword: "" });

const emptyShopProductForm = () => ({
  product_no: "",
  product_name: "",
  description: "",
  image_url: "",
  price_yuan: "10",
  stock: 10,
  status: 1,
});

const shopProductForm = ref(emptyShopProductForm());

const editingShopProductId = ref<number | null>(null);

const editingShopProduct = ref<ShopProduct | null>(null);

const shopProductEditForm = ref(emptyShopProductForm());

function shopProductPayload(form: ReturnType<typeof emptyShopProductForm>) {
  return {
    product_no: form.product_no,
    product_name: form.product_name,
    description: form.description,
    image_url: form.image_url,
    price_cents: yuanInputToCents(form.price_yuan),
    stock: form.stock,
    status: form.status,
  };
}

async function loadShopProducts() {
  const response = await adminGetShopProducts({
    status: shopProductFilters.value.status || undefined,
    keyword: shopProductFilters.value.keyword || undefined,
    page: shopProductPage.value.page,
    page_size: shopProductPage.value.page_size,
  });
  shopProducts.value = response.data.items;
  shopProductPage.value.total = response.data.total;
}

async function refreshShopProducts(reset = false) {
  if (reset) resetPage(shopProductPage.value);
  loading.value = true;
  try {
    await loadShopProducts();
  } catch (error) {
    setError(error, "商品列表加载失败");
  } finally {
    loading.value = false;
  }
}

async function submitShopProduct() {
  const payload = editingShopProductId.value
    ? shopProductPayload(shopProductEditForm.value)
    : shopProductPayload(shopProductForm.value);
  loading.value = true;
  try {
    if (editingShopProductId.value) {
      await adminUpdateShopProduct(editingShopProductId.value, payload);
      setSuccess("商品已更新");
    } else {
      await adminCreateShopProduct(payload);
      createVisible.value = false;
    setSuccess("商品已创建");
    }
    resetShopProductForm();
    resetPage(shopProductPage.value);
    await loadShopProducts();
  } catch (error) {
    setError(error, "保存商品失败");
  } finally {
    loading.value = false;
  }
}

function editShopProduct(product: ShopProduct) {
  editingShopProductId.value = product.id;
  editingShopProduct.value = product;
  shopProductEditForm.value = {
    product_no: product.product_no,
    product_name: product.product_name,
    description: product.description || "",
    image_url: product.image_url || "",
    price_yuan: centsToYuanInput(product.price_cents),
    stock: product.stock,
    status: product.status,
  };
}

function resetShopProductForm() {
  editingShopProductId.value = null;
  editingShopProduct.value = null;
  shopProductForm.value = emptyShopProductForm();
  shopProductEditForm.value = emptyShopProductForm();
}

async function toggleShopProductStatus(product: ShopProduct) {
  const nextStatusLabel = product.status === 1 ? "下架" : "上架";
  if (!(await confirmAction(`确认${nextStatusLabel}商品 ${product.product_name}？`))) return;
  loading.value = true;
  try {
    await adminUpdateShopProductStatus(product.id, product.status === 1 ? 0 : 1);
    await loadShopProducts();
    setSuccess("商品状态已更新");
  } catch (error) {
    setError(error, "更新商品状态失败");
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  loading.value = true;
  try {
    await loadShopProducts();
  } catch (error) { setError(error, "数据加载失败"); }
  finally { loading.value = false; }
});
const createVisible = ref(false);
</script>

<template>
  <section class="page-header"><h1>商城商品</h1><p>维护商品资料、库存和销售状态。</p></section>
  <el-card shadow="never" class="admin-shell element-admin">
    <section v-loading="loading" class="admin-section">
      <div class="admin-create-action"><el-button type="primary" @click="createVisible = true">新增商品</el-button></div>
      <el-drawer v-model="createVisible" title="新增商品" size="min(600px, 100vw)" class="admin-edit-drawer">
        <el-form label-position="top" class="element-form" @submit.prevent="submitShopProduct">
          <el-form-item label="编号"><el-input v-model="shopProductForm.product_no" /></el-form-item>
          <el-form-item label="名称"><el-input v-model="shopProductForm.product_name" /></el-form-item>
          <el-form-item label="价格"><el-input v-model="shopProductForm.price_yuan" /></el-form-item>
          <el-form-item label="库存"><el-input-number v-model="shopProductForm.stock" :min="0" :max="999999" /></el-form-item>
          <el-form-item label="状态">
            <el-select v-model="shopProductForm.status" class="short-select">
              <el-option label="上架" :value="1" />
              <el-option label="下架" :value="0" />
            </el-select>
          </el-form-item>
          <el-form-item label="图片"><el-input v-model="shopProductForm.image_url" /></el-form-item>
          <el-form-item label="说明"><el-input v-model="shopProductForm.description" /></el-form-item>
          <el-form-item><el-button type="primary" native-type="submit">新增商品</el-button></el-form-item>
        </el-form>
      </el-drawer>

      <el-card shadow="never" class="panel-card">
        <template #header><strong>商品管理</strong></template>
        <el-form inline class="element-filter">
          <el-form-item label="状态">
            <el-select v-model="shopProductFilters.status" clearable class="short-select" @change="refreshShopProducts(true)">
              <el-option label="上架" value="1" />
              <el-option label="下架" value="0" />
            </el-select>
          </el-form-item>
          <el-form-item label="商品"><el-input v-model="shopProductFilters.keyword" placeholder="编号或名称" @keyup.enter="refreshShopProducts(true)" /></el-form-item>
          <el-form-item><el-button type="primary" @click="refreshShopProducts(true)">查询商品</el-button></el-form-item>
        </el-form>
        <el-table :data="shopProducts" empty-text="暂无商品数据" stripe>
          <el-table-column prop="product_no" label="编号" min-width="100" />
          <el-table-column prop="product_name" label="名称" min-width="150" />
          <el-table-column label="价格" width="110"><template #default="{ row }">{{ formatMoney(row.price_cents) }}</template></el-table-column>
          <el-table-column prop="stock" label="库存" width="90" />
          <el-table-column prop="sold_count" label="销量" width="90" />
          <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag :type="row.status === 1 ? 'success' : 'info'" effect="plain">{{ row.status === 1 ? "上架" : "下架" }}</el-tag></template></el-table-column>
          <el-table-column label="操作" fixed="right" width="140">
            <template #default="{ row }">
              <el-button link type="primary" @click="editShopProduct(row)">编辑</el-button>
              <el-button link type="warning" @click="toggleShopProductStatus(row)">{{ row.status === 1 ? "下架" : "上架" }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination class="element-pagination" :current-page="shopProductPage.page" :page-size="shopProductPage.page_size" :total="shopProductPage.total" layout="prev, pager, next, total" @current-change="changeShopProductPage" />
      </el-card>
    </section>
    <el-drawer :model-value="Boolean(editingShopProductId)" :title="`编辑商品：${editingShopProduct?.product_name || ''}`" size="min(600px, 100vw)" @close="resetShopProductForm" class="admin-edit-drawer">
      <el-alert title="库存为当前可售库存；已支付订单取消时会自动退回库存。" type="info" show-icon :closable="false" />
      <el-form label-position="top" class="element-form dialog-form" @submit.prevent="submitShopProduct">
        <el-form-item label="商品编号"><el-input v-model="shopProductEditForm.product_no" /></el-form-item>
        <el-form-item label="商品名称"><el-input v-model="shopProductEditForm.product_name" /></el-form-item>
        <el-form-item label="价格（元）"><el-input v-model="shopProductEditForm.price_yuan" /></el-form-item>
        <el-form-item label="库存"><el-input-number v-model="shopProductEditForm.stock" :min="0" :max="999999" /></el-form-item>
        <el-form-item label="图片路径"><el-input v-model="shopProductEditForm.image_url" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="shopProductEditForm.status">
            <el-option label="上架" :value="1" />
            <el-option label="下架" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="商品说明"><el-input v-model="shopProductEditForm.description" type="textarea" :rows="4" /></el-form-item>
        <div class="dialog-actions">
          <el-button @click="resetShopProductForm">取消</el-button>
          <el-button type="primary" :loading="loading" native-type="submit">保存商品</el-button>
        </div>
      </el-form>
    </el-drawer>
  </el-card>
</template>
