<template>
  <div class="wrap" :title="`${p.done} done · ${p.running} running · ${p.pending} queued · ${p.invalid} invalid`">
    <div class="progress">
      <span :style="{ width: pct(p.done), background: 'var(--good)' }" />
      <span :style="{ width: pct(p.invalid), background: 'var(--bad)' }" />
      <span :style="{ width: pct(p.running), background: 'var(--accent)' }" class="running" />
    </div>
    <span class="small muted">{{ p.done + p.invalid }}/{{ p.total }}</span>
  </div>
</template>

<script setup lang="ts">
import type { Progress } from '../api';

const props = defineProps<{ p: Progress }>();
const pct = (n: number) => `${props.p.total ? (100 * n) / props.p.total : 0}%`;
</script>

<style scoped>
.wrap { display: flex; align-items: center; gap: 8px; }
.progress { flex: 1; min-width: 80px; }
.running { opacity: 0.6; }
</style>
