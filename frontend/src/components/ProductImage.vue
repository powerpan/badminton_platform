<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Picture } from "@element-plus/icons-vue";
const props = defineProps<{ name: string; src?: string | null }>();
const failed = ref(false);
const missing = ref(false);
watch(() => [props.src, props.name], () => { failed.value = false; missing.value = false; });
const supplied = computed(() => Boolean(props.src && !props.src.includes('/courts/')));
const category = computed(() => {
  if (/饮用水|矿泉水|纯净水/.test(props.name)) return '/products/water.png';
  if (/手胶|吸汗带/.test(props.name)) return '/products/grip.png';
  if (/羽毛球/.test(props.name) && !/拍|包|鞋|服/.test(props.name)) return '/products/shuttle.png';
  return '';
});
const source = computed(() => missing.value ? '' : supplied.value && !failed.value ? props.src : category.value);
function imageError() {
  if (supplied.value && !failed.value) failed.value = true;
  else missing.value = true;
}
</script>

<template>
  <figure class="product-image">
    <img v-if="source" :src="source" :alt="`${name}${!supplied || failed ? '示意图' : ''}`" loading="lazy" @error="imageError" />
    <div v-else class="product-image-missing"><Picture /><span>商品图片待补充</span></div>
    <figcaption v-if="source && (!supplied || failed)">商品示意图</figcaption>
  </figure>
</template>

<style scoped>
.product-image { position: relative; margin: 0; width: 100%; aspect-ratio: 4 / 3; background: #fff; overflow: hidden; border-bottom: 1px solid var(--line); }
.product-image img { display: block; width: 100%; height: 100%; object-fit: contain; background: #fff; }
.product-image figcaption { position: absolute; bottom: 7px; right: 10px; color: #7a857e; font-size: 10px; background: #fff; padding: 2px 4px; }
.product-image-missing { height: 100%; min-height: 72px; display: flex; flex-direction: column; gap: 10px; align-items: center; justify-content: center; background: #f7f9f8; color: #758379; font-size: 12px; }
.product-image-missing svg { width: 28px; height: 28px; }
.cart-item .product-image { width: 76px; height: 76px; flex-shrink: 0; border: 1px solid var(--line); border-radius: 4px; }
.cart-item .product-image figcaption { display: none; }
</style>
