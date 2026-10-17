<template>
  <main class="page stack">
    <div>
      <h1>Models &amp; harnesses</h1>
      <p class="muted">An agent = a harness (the loop, tools, skills, memory) + a model. Pick both per side when you build an experiment.</p>
    </div>
    <p v-if="error" class="error">{{ error }}</p>

    <section class="card" v-if="catalog">
      <h2>Models</h2>
      <p class="small muted">Any OpenAI-compatible endpoint (Ollama, Groq, Gemini, OpenRouter, OpenAI, vLLM…). Keys stay in <code>.env</code>; here you only name the variable.</p>
      <table>
        <thead><tr><th>Model</th><th>Endpoint</th><th>Key variable</th><th></th></tr></thead>
        <tbody>
          <tr v-for="m in models" :key="m.name">
            <td><b>{{ m.label }}</b><div class="small muted">{{ m.id }}</div><div class="small muted" v-if="m.notes">{{ m.notes }}</div></td>
            <td class="small">{{ host(m.base_url) }}</td>
            <td class="small"><code v-if="m.api_key_env">{{ m.api_key_env }}</code><span v-else class="muted">none</span></td>
            <td class="num" style="white-space: nowrap">
              <span v-if="checks[m.name]" class="small" :class="checks[m.name]!.ok && checks[m.name]!.tool_calling ? 'good' : 'bad'">{{ checkText(checks[m.name]!) }}</span>
              <button class="small" :disabled="checking[m.name]" @click="check(m)">{{ checking[m.name] ? 'Testing…' : 'Test' }}</button>
            </td>
          </tr>
        </tbody>
      </table>

      <details style="margin-top: 16px">
        <summary><b>Add a model</b></summary>
        <div class="stack" style="margin-top: 12px">
          <div class="grid2">
            <div><label>Display name</label><input v-model="form.label" placeholder="e.g. Llama 3.3 70B (OpenRouter)" /></div>
            <div><label>Model id at the provider</label><input v-model="form.id" placeholder="e.g. meta-llama/llama-3.3-70b-instruct" /></div>
          </div>
          <div class="grid2">
            <div><label>Base URL</label><input v-model="form.base_url" placeholder="https://openrouter.ai/api/v1" /></div>
            <div><label>Key variable in .env <span class="muted">(name only, empty for local)</span></label><input v-model="form.api_key_env" placeholder="OPENROUTER_API_KEY" /></div>
          </div>
          <div><label>Notes <span class="muted">(limits, context size…)</span></label><input v-model="form.notes" /></div>
          <div class="row">
            <span v-if="formCheck" class="small" :class="formCheck.ok && formCheck.tool_calling ? 'good' : 'bad'">{{ checkText(formCheck) }}</span>
            <span v-if="formError" class="error">{{ formError }}</span>
            <span class="spacer" />
            <button :disabled="!form.id || !form.base_url || formChecking" @click="checkForm">{{ formChecking ? 'Testing…' : 'Test connection' }}</button>
            <button class="primary" :disabled="!form.label || !form.id || !form.base_url" @click="save">Save model</button>
          </div>
        </div>
      </details>
    </section>

    <section class="card" v-if="catalog">
      <h2>Harnesses</h2>
      <div v-for="h in catalog.harnesses" :key="h.id" class="harness">
        <div class="row"><b>{{ h.id }}</b><span v-for="s in h.settings" :key="s" class="pill">{{ s }}</span></div>
        <p class="small" style="margin: 4px 0 0">{{ h.description }}</p>
        <p class="small muted" v-if="h.requirements" style="margin: 2px 0 0">Requires: {{ h.requirements }}</p>
      </div>
      <details style="margin-top: 16px">
        <summary><b>Add a harness</b> <span class="muted small">(code, not a form: a harness is a program)</span></summary>
        <ol class="small" style="margin-top: 10px">
          <li>Create <code>runner/evalrunner/harnesses/&lt;name&gt;.py</code> with a class that extends <code>HarnessAdapter</code>:
            set <code>id</code>, <code>version</code>, <code>description</code>, the <code>settings</code> it uses, and implement
            <code>run_trial(ctx) → Trace</code> (run the task's sessions in <code>ctx.sandbox_dir</code>, record each step with <code>trace.add(...)</code>).</li>
          <li>Register it with one line in <code>runner/evalrunner/harnesses/__init__.py</code>.</li>
          <li>Run its process through <code>isolation.confine(...)</code> so it stays in its sandbox.</li>
          <li>Reload this page: it appears here and in the experiment builder. Full guide: README → "Add a harness".</li>
        </ol>
      </details>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { api, type Catalog, type ModelCheck, type ModelEntry } from '../api';

const catalog = ref<Catalog>();
const error = ref('');
const models = computed(() => catalog.value?.models.filter((m) => m.name !== 'none') ?? []);
const checks = reactive<Record<string, ModelCheck>>({});
const checking = reactive<Record<string, boolean>>({});
const form = reactive({ label: '', id: '', base_url: '', api_key_env: '', notes: '' });
const formCheck = ref<ModelCheck>();
const formChecking = ref(false);
const formError = ref('');

const host = (u: string | null) => { try { return new URL(u ?? '').host; } catch { return '–'; } };
const checkText = (c: ModelCheck) =>
  !c.ok ? `failed: ${c.message}` : c.tool_calling ? `works, tool calling ok (${(c.latency_ms / 1000).toFixed(1)} s)` : c.message;
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9.]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60);

async function check(m: ModelEntry) {
  checking[m.name] = true;
  try { checks[m.name] = await api.checkModel(m); } catch (e: any) { checks[m.name] = { ok: false, latency_ms: 0, tool_calling: false, message: e.message }; }
  checking[m.name] = false;
}
async function checkForm() {
  formChecking.value = true;
  formCheck.value = await api.checkModel({ ...form, api_key_env: form.api_key_env || null })
    .catch((e) => ({ ok: false, latency_ms: 0, tool_calling: false, message: e.message }));
  formChecking.value = false;
}
async function save() {
  formError.value = '';
  try {
    await api.addModel({ ...form, name: slug(form.label), api_key_env: form.api_key_env || null });
    catalog.value = await api.catalog();
    Object.assign(form, { label: '', id: '', base_url: '', api_key_env: '', notes: '' });
    formCheck.value = undefined;
  } catch (e: any) {
    formError.value = e.message;
  }
}
onMounted(async () => {
  try { catalog.value = await api.catalog(); } catch (e: any) { error.value = `Could not reach the API: ${e.message}`; }
});
</script>

<style scoped>
.harness + .harness { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--line); }
summary { cursor: pointer; }
ol { padding-left: 20px; }
li + li { margin-top: 6px; }
</style>
