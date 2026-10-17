<template>
  <!-- Mean delta (dot) with its 95% CI (bar) on a symmetric axis around 0 (dashed). -->
  <svg :viewBox="`0 0 ${W} 34`" class="ci" role="img" :aria-label="`mean ${mean.toFixed(3)}, 95% CI ${low.toFixed(3)} to ${high.toFixed(3)}`">
    <line :x1="x(0)" :x2="x(0)" y1="4" y2="26" class="zero" />
    <line :x1="x(low)" :x2="x(high)" y1="15" y2="15" :class="['bar', tone]" />
    <line :x1="x(low)" :x2="x(low)" y1="10" y2="20" :class="['bar', tone]" />
    <line :x1="x(high)" :x2="x(high)" y1="10" y2="20" :class="['bar', tone]" />
    <circle :cx="x(mean)" cy="15" r="5" :class="['dot', tone]" />
    <text :x="x(-range)" y="33" class="tick">{{ (-range).toFixed(2) }}</text>
    <text :x="x(0)" y="33" class="tick" text-anchor="middle">0</text>
    <text :x="x(range)" y="33" class="tick" text-anchor="end">{{ range.toFixed(2) }}</text>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{ mean: number; low: number; high: number; scale?: number }>();
const W = 420;
const range = computed(() => props.scale ?? Math.max(0.05, Math.abs(props.low), Math.abs(props.high)) * 1.1);
const x = (v: number) => 10 + ((v + range.value) / (2 * range.value)) * (W - 20);
const tone = computed(() => (props.low > 0 ? 'good' : props.high < 0 ? 'bad' : 'neutral'));
</script>

<style scoped>
.ci { width: 100%; max-width: 420px; height: auto; display: block; }
.zero { stroke: var(--text-2); stroke-dasharray: 3 3; }
.bar { stroke-width: 3; stroke-linecap: round; }
.bar.good, .dot.good { stroke: var(--good); fill: var(--good); }
.bar.bad, .dot.bad { stroke: var(--bad); fill: var(--bad); }
.bar.neutral, .dot.neutral { stroke: var(--text-2); fill: var(--text-2); }
.tick { font-size: 10px; fill: var(--text-2); }
</style>
