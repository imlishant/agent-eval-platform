<template>
  <span class="dots">
    <RouterLink v-for="t in sorted" :key="t.id" :to="`/trials/${t.id}`" class="dot" :class="cls(t)"
      :title="`trial ${t.trial_index + 1}: ${t.status}${t.score !== null ? ` · score ${t.score.toFixed(2)}` : ''}${t.error ? ` · ${t.error.slice(0, 80)}` : ''}`"
      :aria-label="`trial ${t.trial_index + 1} ${t.status}`" />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { TrialRow } from '../api';

const props = defineProps<{ trials: TrialRow[] }>();
const sorted = computed(() => [...props.trials].sort((a, b) => a.trial_index - b.trial_index));
const cls = (t: TrialRow) =>
  t.status === 'invalid' ? 'invalid'
  : t.status !== 'done' ? 'waiting'
  : (t.score ?? 0) >= 1 ? 'pass' : (t.score ?? 0) > 0 ? 'partial' : 'fail';
</script>

<style scoped>
.dots { display: inline-flex; gap: 5px; }
.dot { width: 14px; height: 14px; border-radius: 50%; display: inline-block; transition: transform var(--beat) var(--ease); }
.dot:hover { transform: scale(1.25); text-decoration: none; }
.pass { background: var(--good); }
.partial { background: #e0a800; }
.fail { background: var(--bad); }
.invalid { background: transparent; border: 2px dashed var(--bad); }
.waiting { background: var(--surface-2); border: 1px solid var(--line); }
</style>
