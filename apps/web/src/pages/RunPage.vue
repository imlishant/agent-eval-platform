<template>
  <main class="page stack">
    <div>
      <h1>Experiments</h1>
      <p class="muted">Compare two configurations on the same tasks, several trials each.</p>
    </div>

    <p v-if="loadError" class="error">Could not reach the API: {{ loadError }}</p>

    <!-- New experiment -->
    <section class="card stack" v-if="catalog">
      <h2>New experiment</h2>
      <div class="grid2">
        <div><label>Name</label><input v-model="form.name" placeholder="e.g. baseline vs hermes on Gemini" /></div>
        <div><label>Trials per task (N)</label><input v-model.number="form.n_trials" type="number" min="1" max="20" /></div>
      </div>
      <div>
        <label>Hypothesis (write it before you run)</label>
        <textarea v-model="form.hypothesis" placeholder="e.g. Hermes scores higher on memory tasks but costs more tokens." />
      </div>
      <div class="grid2">
        <div>
          <label>Config A (baseline)</label>
          <select v-model="form.config_a">
            <option v-for="c in catalog.configs" :key="c.file" :value="c.file">{{ c.name }} · {{ c.id }}</option>
          </select>
          <p class="small muted" v-if="cfgA">{{ describe(cfgA) }}</p>
        </div>
        <div>
          <label>Config B (candidate)</label>
          <select v-model="form.config_b">
            <option v-for="c in catalog.configs" :key="c.file" :value="c.file">{{ c.name }} · {{ c.id }}</option>
          </select>
          <p class="small muted" v-if="cfgB">{{ describe(cfgB) }}</p>
        </div>
      </div>
      <p v-if="axes.length" class="small">
        Differs in: <span v-for="a in axes" :key="a" class="pill">{{ a }}</span>
        <span v-if="axes.length > 1" class="muted"> · more than one axis changes, so a difference cannot be pinned to one cause</span>
      </p>
      <p v-else-if="cfgA && cfgB" class="small bad">A and B are identical.</p>

      <div>
        <div class="row"><label style="margin: 0">Tasks ({{ form.task_ids.length }} of {{ catalog.tasks.length }})</label>
          <span class="spacer" />
          <button class="small" @click="form.task_ids = catalog.tasks.map((t) => t.id)">All</button>
          <button class="small" @click="form.task_ids = []">None</button>
        </div>
        <div v-for="(tasks, cat) in byCategory" :key="cat" class="cat">
          <span class="muted small cat-name">{{ cat }}</span>
          <div class="chips">
            <label v-for="t in tasks" :key="t.id" class="chip" :class="{ on: form.task_ids.includes(t.id) }">
              <input type="checkbox" :value="t.id" v-model="form.task_ids" />{{ t.id }}
            </label>
          </div>
        </div>
      </div>
      <div class="row">
        <span class="muted small">{{ form.task_ids.length * 2 * (form.n_trials || 0) }} trials</span>
        <span class="spacer" />
        <span v-if="createError" class="error">{{ createError }}</span>
        <button class="primary" :disabled="!canStart || starting" @click="start">{{ starting ? 'Starting…' : 'Start' }}</button>
      </div>
    </section>

    <!-- Define a config -->
    <details class="card" v-if="catalog">
      <summary><h2 style="display: inline">Define a config</h2></summary>
      <div class="stack" style="margin-top: 16px">
        <div class="grid2">
          <div><label>Name (file in configs/)</label><input v-model="cfg.name" placeholder="baseline-groq-120b" /></div>
          <div><label>Harness</label>
            <select v-model="cfg.harness"><option>baseline</option><option>hermes</option><option>mock</option></select></div>
        </div>
        <div class="grid2">
          <div><label>Model preset</label>
            <select v-model="preset" @change="applyPreset">
              <option v-for="(p, k) in PRESETS" :key="k" :value="k">{{ k }}</option>
            </select></div>
          <div><label>Model id</label><input v-model="cfg.model.id" /></div>
        </div>
        <div class="grid2">
          <div><label>Base URL (OpenAI-compatible)</label><input v-model="cfg.model.base_url" /></div>
          <div><label>API key env var (name only)</label><input v-model="cfg.model.api_key_env" placeholder="none for local" /></div>
        </div>
        <div class="grid2">
          <div><label>Memory</label><select v-model="cfg.settings.memory"><option>off</option><option>on</option></select></div>
          <div><label>Temperature (baseline only)</label><input v-model.number="cfg.settings.temperature" type="number" step="0.1" min="0" max="2" /></div>
        </div>
        <div class="grid2">
          <div><label>Max steps</label><input v-model.number="cfg.settings.max_steps" type="number" min="1" /></div>
          <div><label>Max tokens per reply · timeout (s)</label>
            <div class="row" style="flex-wrap: nowrap"><input v-model.number="cfg.settings.max_tokens" type="number" /><input v-model.number="cfg.settings.timeout_s" type="number" /></div></div>
        </div>
        <div>
          <label>Skills</label>
          <label v-for="s in catalog.skills" :key="s.name" class="chip" :class="{ on: cfg.settings.skills.includes(s.name) }" :title="s.description">
            <input type="checkbox" :value="s.name" v-model="cfg.settings.skills" />{{ s.name }}
          </label>
        </div>
        <div class="row">
          <span v-if="cfgResult" class="small good">Saved {{ cfgResult.file }} · ID {{ cfgResult.id }}</span>
          <span v-if="cfgError" class="error">{{ cfgError }}</span>
          <span class="spacer" />
          <button class="primary" :disabled="!cfg.name" @click="saveConfig">Save config</button>
        </div>
      </div>
    </details>

    <!-- Past experiments -->
    <section class="card">
      <h2>Runs</h2>
      <p v-if="experiments && !experiments.length" class="muted">No experiments yet. Start one above.</p>
      <p v-if="!experiments && !loadError" class="muted">Loading…</p>
      <table v-if="experiments?.length">
        <thead><tr><th>#</th><th>Name</th><th>A → B</th><th>N</th><th style="width: 180px">Progress</th><th>Status</th></tr></thead>
        <tbody>
          <tr v-for="e in experiments" :key="e.id" class="link" @click="$router.push(`/experiments/${e.id}`)">
            <td class="muted">{{ e.id }}</td>
            <td><RouterLink :to="`/experiments/${e.id}`">{{ e.name }}</RouterLink></td>
            <td class="small">{{ e.config_a_name }} → {{ e.config_b_name }}</td>
            <td>{{ e.n_trials }}</td>
            <td><ProgressBar :p="e.progress" /></td>
            <td><span class="pill" :class="{ good: e.status === 'done' }">{{ e.status }}</span></td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { api, type Catalog, type ConfigEntry } from '../api';
import ProgressBar from '../components/ProgressBar.vue';

const router = useRouter();
const catalog = ref<Catalog>();
const experiments = ref<any[]>();
const loadError = ref('');
const form = reactive({ name: '', hypothesis: '', config_a: '', config_b: '', task_ids: [] as string[], n_trials: 3 });
const starting = ref(false);
const createError = ref('');

const PRESETS: Record<string, { id: string; base_url: string; api_key_env: string | null }> = {
  'Gemini 3.1 Flash Lite (free)': { id: 'gemini-3.1-flash-lite', base_url: 'https://generativelanguage.googleapis.com/v1beta/openai/', api_key_env: 'GEMINI_API_KEY' },
  'Gemini 3.5 Flash Lite (free)': { id: 'gemini-3.5-flash-lite', base_url: 'https://generativelanguage.googleapis.com/v1beta/openai/', api_key_env: 'GEMINI_API_KEY' },
  'Groq gpt-oss-20b (free)': { id: 'openai/gpt-oss-20b', base_url: 'https://api.groq.com/openai/v1', api_key_env: 'GROQ_API_KEY' },
  'Groq gpt-oss-120b (free)': { id: 'openai/gpt-oss-120b', base_url: 'https://api.groq.com/openai/v1', api_key_env: 'GROQ_API_KEY' },
  'Local Ollama qwen3:8b': { id: 'qwen3:8b', base_url: 'http://localhost:11434/v1', api_key_env: null },
};
const preset = ref(Object.keys(PRESETS)[0]);
const cfg = reactive({
  name: '', harness: 'baseline',
  model: { provider: 'openai_compat', ...PRESETS[preset.value] },
  settings: { memory: 'off', temperature: 0.7, max_steps: 15, max_tokens: 2000, timeout_s: 180, skills: [] as string[] },
});
const cfgResult = ref<ConfigEntry>();
const cfgError = ref('');
const applyPreset = () => Object.assign(cfg.model, PRESETS[preset.value]);

const cfgA = computed(() => catalog.value?.configs.find((c) => c.file === form.config_a));
const cfgB = computed(() => catalog.value?.configs.find((c) => c.file === form.config_b));
const describe = (c: ConfigEntry) =>
  `${c.config.harness} · ${c.config.model.id} · memory ${c.config.settings.memory}` +
  (c.config.settings.skills.length ? ` · skills: ${c.config.settings.skills.join(', ')}` : '');

/** Which axes differ between A and B (the PDF asks for experiments that change one meaningful axis). */
const axes = computed(() => {
  if (!cfgA.value || !cfgB.value) return [];
  const a = cfgA.value.config, b = cfgB.value.config, out: string[] = [];
  if (a.harness !== b.harness) out.push('harness');
  if (a.model.id !== b.model.id || a.model.base_url !== b.model.base_url) out.push('model');
  for (const k of Object.keys({ ...a.settings, ...b.settings }))
    if (JSON.stringify(a.settings[k]) !== JSON.stringify(b.settings[k])) out.push(k);
  return out;
});

const byCategory = computed(() => {
  const g: Record<string, Catalog['tasks']> = {};
  for (const t of catalog.value?.tasks ?? []) (g[t.category] ??= []).push(t);
  return g;
});
const canStart = computed(() => form.name && form.config_a && form.config_b && axes.value.length && form.task_ids.length && form.n_trials >= 1);

async function load() {
  try {
    experiments.value = await api.experiments();
    loadError.value = '';
  } catch (e: any) {
    loadError.value = e.message;
  }
}

async function start() {
  starting.value = true;
  createError.value = '';
  try {
    const e = await api.createExperiment({ ...form });
    router.push(`/experiments/${e.id}`);
  } catch (e: any) {
    createError.value = e.message;
  } finally {
    starting.value = false;
  }
}

async function saveConfig() {
  cfgError.value = '';
  cfgResult.value = undefined;
  try {
    const model = { ...cfg.model, api_key_env: cfg.model.api_key_env || null };
    cfgResult.value = await api.createConfig({ name: cfg.name, harness: cfg.harness, model, settings: cfg.settings });
    catalog.value = await api.catalog();
  } catch (e: any) {
    cfgError.value = e.message;
  }
}

let timer: number | undefined;
onMounted(async () => {
  try {
    catalog.value = await api.catalog();
    form.task_ids = catalog.value.tasks.map((t) => t.id);
    form.config_a = catalog.value.configs[0]?.file ?? '';
    form.config_b = catalog.value.configs[1]?.file ?? '';
  } catch (e: any) {
    loadError.value = e.message;
  }
  await load();
  timer = window.setInterval(load, 3000);
});
onUnmounted(() => clearInterval(timer));
</script>

<style scoped>
.cat { display: grid; grid-template-columns: 64px 1fr; gap: 6px; align-items: start; margin-top: 8px; }
.cat-name { padding-top: 3px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  display: inline-flex; align-items: center; margin: 0; padding: 3px 10px; border-radius: 980px; cursor: pointer;
  font-size: 12.5px; color: var(--text-2); background: var(--surface-2); border: 1px solid transparent;
  transition: background var(--beat) var(--ease), color var(--beat) var(--ease);
}
.chip.on { color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, transparent); }
.chip input { display: none; }
summary { cursor: pointer; list-style: none; }
summary::-webkit-details-marker { display: none; }
summary::after { content: '›'; display: inline-block; margin-left: 8px; color: var(--text-2); transition: transform var(--beat) var(--ease); }
details[open] summary::after { transform: rotate(90deg); }
tr.link { cursor: pointer; transition: background var(--beat) var(--ease); }
tr.link:hover { background: var(--surface-2); }
</style>
