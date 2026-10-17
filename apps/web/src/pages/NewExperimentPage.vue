<template>
  <main class="page stack">
    <div>
      <RouterLink to="/" class="small">‹ Runs</RouterLink>
      <h1>New experiment</h1>
      <p class="muted">Build two agents. Change one thing between them to learn what that one thing does.</p>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="!catalog && !error" class="muted">Loading…</p>

    <template v-if="catalog">
      <div class="ab">
        <ConfigBuilder side="A" :catalog="catalog" v-model="a" />
        <div class="mid"><button title="Make B a copy of A, then change one thing" @click="copyAtoB">A → B</button></div>
        <ConfigBuilder side="B" :catalog="catalog" v-model="b" />
      </div>

      <section class="card changes" :class="{ warn: axes.length !== 1 }">
        <template v-if="axes.length === 0">A and B are identical. Change something in B.</template>
        <template v-else>
          <b>What changes:</b> <span v-for="x in axes" :key="x" class="pill">{{ x }}</span>
          <span v-if="axes.length > 1" class="small"> · more than one thing changes, so a difference cannot be pinned to a single cause</span>
        </template>
      </section>

      <section class="card stack">
        <div>
          <label>Tasks <span class="muted">({{ taskIds.length }} of {{ catalog.tasks.length }})</span></label>
          <div class="chips">
            <label v-for="(ids, cat) in byCategory" :key="cat" class="chip" :class="{ on: ids.every((t) => taskIds.includes(t)) }">
              <input type="checkbox" :checked="ids.every((t) => taskIds.includes(t))" @change="toggleCategory(ids)" />{{ cat }} · {{ ids.length }}
            </label>
          </div>
          <details style="margin-top: 8px">
            <summary class="small muted">Pick individual tasks</summary>
            <div class="chips" style="margin-top: 8px">
              <label v-for="t in catalog.tasks" :key="t.id" class="chip" :class="{ on: taskIds.includes(t.id) }">
                <input type="checkbox" :value="t.id" v-model="taskIds" />{{ t.id }}
              </label>
            </div>
          </details>
        </div>
        <div class="grid2">
          <div><label>Trials per task</label><input v-model.number="n" type="number" min="1" max="20" /></div>
          <div><label>Name</label><input v-model="name" :placeholder="defaultName" /></div>
        </div>
        <div><label>Hypothesis <span class="muted">(optional; write it before you see results)</span></label>
          <textarea v-model="hypothesis" placeholder="e.g. Hermes scores higher on memory tasks but uses more tokens." /></div>
        <div class="row">
          <span class="muted small">{{ taskIds.length }} tasks × 2 configs × {{ n }} = <b>{{ taskIds.length * 2 * n }} trials</b></span>
          <span class="spacer" />
          <span v-if="startError" class="error">{{ startError }}</span>
          <button class="primary" :disabled="!canStart || starting" @click="start">{{ starting ? 'Starting…' : 'Start experiment' }}</button>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api, newDraft, type Catalog, type Draft } from '../api';
import ConfigBuilder from '../components/ConfigBuilder.vue';

const router = useRouter();
const catalog = ref<Catalog>();
const error = ref('');
const a = ref<Draft>(newDraft('baseline', 'gemini-3.1-flash-lite'));
const b = ref<Draft>(newDraft('hermes', 'gemini-3.1-flash-lite'));
const taskIds = ref<string[]>([]);
const n = ref(3);
const name = ref('');
const hypothesis = ref('');
const starting = ref(false);
const startError = ref('');

const copyAtoB = () => (b.value = JSON.parse(JSON.stringify(a.value)));
const label = (d: Draft) => (d.harness === 'mock' ? `mock-${d.settings.extra.behavior}` : `${d.harness} · ${d.model}`);
const defaultName = computed(() => `${label(a.value)} vs ${label(b.value)}`);

/** The settings each harness actually uses; a difference in an unused setting is not a real change. */
const used = (d: Draft) => catalog.value?.harnesses.find((h) => h.id === d.harness)?.settings ?? [];
const axes = computed(() => {
  const out: string[] = [];
  if (a.value.harness !== b.value.harness) out.push('harness');
  if (a.value.model !== b.value.model) out.push('model');
  const keys = new Set([...used(a.value), ...used(b.value)]);
  for (const k of ['memory', 'skills', 'temperature', 'max_steps', 'max_tokens', 'timeout_s'])
    if (keys.has(k) && JSON.stringify((a.value.settings as any)[k]) !== JSON.stringify((b.value.settings as any)[k])) out.push(k);
  if (a.value.harness === 'mock' && b.value.harness === 'mock' && a.value.settings.extra.behavior !== b.value.settings.extra.behavior) out.push('behaviour');
  return out;
});

const byCategory = computed(() => {
  const g: Record<string, string[]> = {};
  for (const t of catalog.value?.tasks ?? []) (g[t.category] ??= []).push(t.id);
  return g;
});
function toggleCategory(ids: string[]) {
  const all = ids.every((t) => taskIds.value.includes(t));
  taskIds.value = all ? taskIds.value.filter((t) => !ids.includes(t)) : [...new Set([...taskIds.value, ...ids])];
}
const canStart = computed(() => axes.value.length > 0 && taskIds.value.length > 0 && n.value >= 1);

/** Send only the settings the harness uses (plus mock behaviour), so unused knobs do not change the config ID. */
function toBody(d: Draft) {
  const keep = used(d);
  const settings: Record<string, unknown> = Object.fromEntries(Object.entries(d.settings).filter(([k]) => keep.includes(k)));
  if (d.harness === 'mock') settings.extra = { behavior: d.settings.extra.behavior };
  return { harness: d.harness, model: d.model, settings };
}

async function start() {
  starting.value = true;
  startError.value = '';
  try {
    const e = await api.createExperiment({ name: name.value || defaultName.value, hypothesis: hypothesis.value,
      config_a: toBody(a.value), config_b: toBody(b.value), task_ids: taskIds.value, n_trials: n.value });
    router.push(`/experiments/${e.id}`);
  } catch (e: any) {
    startError.value = e.message;
  } finally {
    starting.value = false;
  }
}

onMounted(async () => {
  try {
    catalog.value = await api.catalog();
    taskIds.value = catalog.value.tasks.map((t) => t.id);
  } catch (e: any) {
    error.value = `Could not reach the API: ${e.message}`;
  }
});
</script>

<style scoped>
.ab { display: grid; grid-template-columns: 1fr auto 1fr; gap: 12px; align-items: start; }
.mid { padding-top: 64px; }
@media (max-width: 860px) { .ab { grid-template-columns: 1fr; } .mid { padding: 0; text-align: center; } }
.changes { padding: 12px 18px; border-left: 4px solid var(--good); }
.changes.warn { border-left-color: var(--bad); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  display: inline-flex; align-items: center; margin: 0; padding: 3px 10px; border-radius: 980px; cursor: pointer;
  font-size: 12.5px; color: var(--text-2); background: var(--surface-2);
  transition: background var(--beat) var(--ease), color var(--beat) var(--ease);
}
.chip.on { color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, transparent); }
.chip input { display: none; }
summary { cursor: pointer; }
</style>
