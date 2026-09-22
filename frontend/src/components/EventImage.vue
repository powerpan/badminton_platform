<script setup lang="ts">
import { computed, ref, watch } from 'vue';

const props = defineProps<{ title: string; detail?: boolean }>();
const failed = ref(false);
const pictures: Record<string, { file: string; alt: string }> = {
  '【演示】新手上场 · 基础步法与高远球': { file: 'training', alt: '球友在室内球场学习握拍与发球' },
  '【演示】周末双打积分交流赛': { file: 'doubles', alt: '四名球友在室内球场进行双打交流' },
  '【演示】周日混双搭档交流': { file: 'mixed', alt: '混双搭档在场边交流站位与配合' },
  '【演示】下班后 · 轻松双打夜': { file: 'evening', alt: '夜晚灯光下球友在室内球场进行双打' },
  '【演示】单打循环挑战赛': { file: 'singles', alt: '球友在室内羽毛球场进行单打练习' },
  '【演示】发接发专项 · 网前控制练习': { file: 'serve', alt: '球友手持羽毛球与球拍练习短发球' },
};
const picture = computed(() => pictures[props.title]);
watch(() => props.title, () => { failed.value = false; });
</script>

<template>
  <figure v-if="picture && !failed" class="event-image" :class="{ 'event-image--detail': detail }">
    <img :src="`/events/${picture.file}.jpg`"
      :srcset="`/events/${picture.file}-640.jpg 640w, /events/${picture.file}.jpg 1280w`"
      :sizes="detail ? '(max-width: 880px) calc(100vw - 80px), 880px' : '(max-width: 640px) calc(100vw - 80px), (max-width: 1100px) 45vw, 30vw'"
      :alt="`${picture.alt}，AI 生成场景示意图`"
      width="1280" height="853" :loading="detail ? 'eager' : 'lazy'" decoding="async" @error="failed = true" />
    <figcaption>AI 生成 · 场景示意</figcaption>
  </figure>
</template>

<style scoped>
.event-image { margin: 0; min-width: 0; }
.event-image img { display: block; width: 100%; height: auto; aspect-ratio: 3 / 2; object-fit: cover; border-radius: 4px; }
.event-image figcaption { margin-top: 5px; color: var(--muted); font-size: 11px; line-height: 1.4; }
.event-image--detail { margin-bottom: 18px; }
.event-image--detail img { max-height: 420px; object-position: center; }
</style>
