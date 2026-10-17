<template>
  <div class="builder card stack">
    <div class="row">
      <span class="side">{{ side }}</span>
      <h3 style="margin: 0">{{ side === 'A' ? 'Baseline' : 'Candidate' }}</h3>
      <span class="spacer" />
      <select class="load" @change="load(($event.target as HTMLSelectElement).value); ($event.target as HTMLSelectElement).value = ''">
        <option value="">Load saved…</option>
        <option v-for="c in loadable" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
    </div>

    <div>
      <label>Harness</label>
      <select :value="draft.harness" @change="setHarness(($event.target as HTMLSelectElement).value)">
        <option v-for="h in catalog.harnesses" :key="h.id" :value="h.id">{{ h.id === 'mock' ? 'mock (test, no model)' : h.id }}</option>
      </select>
      <p class="hint">{{ harness?.description }}</p>
    </div>

    <div v-if="draft.harness !== 'mock'">
      <label>Model</label>
      <select v-model="draft.model">
        <option v-for="m in models" :key="m.name" :value="m.name">{{ m.label }}</option>
      </select>
      <p class="hint" :class="{ warn: mismatch }">{{ mismatch ? harness?.requirements + ' ' : '' }}{{ model?.notes }}</p>
    </div>
    <div v-else>
      <label>Mock behaviour</label>
      <select v-model="draft.settings.extra.behavior"><option value="solve">solve (reference answer)</option><option value="fail">fail (does nothing)</option></select>
    </div>

    <template v-if="uses('memory')">
      <div class="row toggle-row">
        <span>Memory between sessions</span><span class="spacer" />
        <button class="seg" :class="{ on: draft.settings.memory === 'off' }" @click="draft.settings.memory = 'off'">Off</button>
        <button class="seg" :class="{ on: draft.settings.memory === 'on' }" @click="draft.settings.memory = 'on'">On</button>
      </div>
    </template>

    <div v-if="uses('skills')">
      <label>Skills</label>
      <div class="chips">
        <label v-for="s in catalog.skills" :key="s.name" class="chip" :class="{ on: draft.settings.skills.includes(s.name) }" :title="s.description">
          <input type="checkbox" :value="s.name" v-model="draft.settings.skills" />{{ s.name }}
        </label>
      </div>
    </div>

    <details v-if="draft.harness !== 'mock'">
      <summary class="small muted">Limits and sampling</summary>
      <div class="grid2" style="margin-top: 10px">
        <div v-if="uses('temperature')"><label>Temperature</label><input v-model.number="draft.settings.temperature" type="number" step="0.1" min="0" max="2" /></div>
        <div><label>Max steps</label><input v-model.number="draft.settings.max_steps" type="number" min="1" /></div>
        <div v-if="uses('max_tokens')"><label>Max tokens per reply</label><input v-model.number="draft.settings.max_tokens" type="number" min="100" /></div>
        <div><label>Timeout (s)</label><input v-model.number="draft.settings.timeout_s" type="number" min="30" /></div>
      </div>
    </details>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { Catalog, Draft } from '../api';

const props = defineProps<{ side: 'A' | 'B'; catalog: Catalog }>();
const draft = defineModel<Draft>({ required: true });

const harness = computed(() => props.catalog.harnesses.find((h) => h.id === draft.value.harness));
const models = computed(() => props.catalog.models.filter((m) => m.name !== 'none'));
const model = computed(() => props.catalog.models.find((m) => m.name === draft.value.model));
const uses = (k: string) => harness.value?.settings.includes(k) ?? false;
/** Hermes needs a big context and token budget: warn when the model's notes say it is baseline-only. */
const mismatch = computed(() => draft.value.harness === 'hermes' && /baseline only/i.test(model.value?.notes ?? ''));

function setHarness(id: string) {
  draft.value.harness = id;
  if (id === 'mock') draft.value.model = 'none';
  else if (draft.value.model === 'none') draft.value.model = models.value[0]?.name ?? '';
}

/** Saved configs whose model is in the registry can be loaded into the builder. */
const modelNameOf = (m: any) =>
  props.catalog.models.find((r) => r.id === m.id && (r.base_url ?? null) === (m.base_url ?? null))?.name;
const loadable = computed(() => props.catalog.configs.filter((c) => modelNameOf(c.config.model)));
function load(id: string) {
  const c = props.catalog.configs.find((x) => x.id === id);
  if (!c) return;
  const s = c.config.settings;
  draft.value = {
    harness: c.config.harness, model: modelNameOf(c.config.model)!,
    settings: { memory: s.memory, skills: [...s.skills], temperature: s.temperature, max_steps: s.max_steps,
      max_tokens: s.max_tokens, timeout_s: s.timeout_s, extra: { behavior: s.extra?.behavior ?? 'solve' } },
  };
}
</script>

<style scoped>
.side {
  width: 26px; height: 26px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 13px; background: var(--surface-2);
}
.load { width: auto; font-size: 13px; padding: 4px 8px; }
.hint { font-size: 12.5px; color: var(--text-2); margin: 6px 0 0; }
.hint.warn { color: var(--bad); }
.toggle-row { font-size: 14px; }
.seg { padding: 4px 14px; font-size: 13px; }
.seg.on { background: var(--accent); color: #fff; }
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
