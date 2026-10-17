<template>
  <main class="page stack">
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="!t && !error" class="muted">Loading…</p>

    <template v-if="t">
      <div>
        <RouterLink :to="`/experiments/${t.experiment_id}`" class="small">‹ Experiment {{ t.experiment_id }}</RouterLink>
        <h1>{{ t.task_id }} <span class="muted" style="font-weight: 400">· trial {{ t.trial_index + 1 }}</span></h1>
        <p class="muted small">{{ t.config_name }} <code>{{ t.config_id }}</code> · {{ t.config_json.harness }} · {{ t.config_json.model.id }}
          · memory {{ t.config_json.settings.memory }}<span v-if="t.config_json.settings.skills?.length"> · skills {{ t.config_json.settings.skills.join(', ') }}</span></p>
      </div>

      <section class="card">
        <div class="row summary">
          <div><div class="muted small">Score</div><div class="kpi" :class="scoreTone">{{ t.score === null ? '–' : t.score.toFixed(2) }}</div></div>
          <div><div class="muted small">Status</div><span class="pill" :class="{ good: t.status === 'done' && t.passed, bad: t.status === 'invalid' || (t.status === 'done' && !t.passed) }">{{ t.status === 'done' ? (t.passed ? 'passed' : 'failed') : t.status }}</span></div>
          <div v-if="t.failure_category"><div class="muted small">Failure category</div><span class="pill bad" :title="FAILURES[t.failure_category]">{{ t.failure_category }}</span>
            <div class="small muted" v-if="signals.length > 1">also: {{ signals.filter((x) => x !== t!.failure_category).join(', ') }}</div></div>
          <div><div class="muted small">Tokens in / out</div>{{ fmt.int(t.input_tokens) }} / {{ fmt.int(t.output_tokens) }}</div>
          <div><div class="muted small">Latency</div>{{ t.latency_ms === null ? '–' : (t.latency_ms / 1000).toFixed(1) + ' s' }}</div>
          <div><div class="muted small">At Opus 5.5 price</div>{{ fmt.usd(t.ref_cost_usd) }}</div>
          <div><div class="muted small">Attempts</div>{{ t.attempts }}</div>
          <div><div class="muted small">Isolation</div>{{ t.isolation ?? '–' }}</div>
        </div>
        <p v-if="t.error" class="error" style="margin-bottom: 0">{{ t.error }}</p>
      </section>

      <section class="card" v-if="t.grades.length">
        <h2>Why: grader verdicts</h2>
        <div v-for="g in t.grades" :key="g.grader" class="grade">
          <div class="row"><b>{{ g.grader }}</b><span class="pill" :class="g.passed ? 'good' : 'bad'">{{ g.passed ? 'pass' : 'fail' }} · {{ g.score.toFixed(2) }}</span></div>
          <pre class="reason">{{ g.reasoning }}</pre>
        </div>
      </section>

      <section class="card">
        <div class="row"><h2 style="margin: 0">Trajectory</h2><span class="muted small">{{ t.events.length }} events</span><span class="spacer" />
          <button class="small" @click="expandAll = !expandAll">{{ expandAll ? 'Collapse' : 'Expand' }} all</button></div>
        <p v-if="!t.events.length" class="muted">No trace: this trial did not complete.</p>
        <div v-for="(events, session) in bySession" :key="session" class="session">
          <div class="session-label muted small" v-if="Object.keys(bySession).length > 1">Session {{ session }}</div>
          <div v-for="e in events" :key="e.seq" class="event" :class="e.type">
            <span class="type">{{ LABEL[e.type] ?? e.type }}</span>
            <div class="body">
              <template v-if="e.type === 'message'"><span class="muted small">{{ e.payload.role }}</span><div class="text">{{ e.payload.text }}</div></template>
              <template v-else-if="e.type === 'tool_call'"><b>{{ e.payload.name }}</b> <code class="args">{{ short(JSON.stringify(e.payload.args)) }}</code></template>
              <template v-else-if="e.type === 'tool_result'">
                <span v-if="e.payload.is_error" class="pill bad">error</span>
                <details :open="expandAll || e.payload.output.length < 240"><summary class="small muted">{{ e.payload.name }} · {{ e.payload.output.length }} chars</summary><pre>{{ e.payload.output }}</pre></details>
              </template>
              <template v-else-if="e.type === 'model_call'"><span class="muted small">{{ e.payload.input_tokens }} in · {{ e.payload.output_tokens }} out · {{ (e.payload.latency_ms / 1000).toFixed(1) }} s<span v-if="e.payload.attempts > 1"> · {{ e.payload.attempts }} attempts<span v-if="e.payload.waited_ms"> (waited {{ (e.payload.waited_ms / 1000).toFixed(1) }} s for the rate limit, not counted in latency)</span></span><span v-if="e.payload.aggregated"> · whole session (Hermes reports totals)</span></span></template>
              <template v-else-if="e.type === 'memory_read'"><span class="muted small">loaded {{ e.payload.chars ?? e.payload.content?.length ?? 0 }} chars</span><pre v-if="e.payload.content">{{ e.payload.content }}</pre></template>
              <template v-else-if="e.type === 'memory_write'"><pre>{{ e.payload.note }}</pre></template>
              <template v-else-if="e.type === 'skill_used'"><b>{{ e.payload.name }}</b></template>
              <template v-else-if="e.type === 'error'"><span class="bad"><b>{{ e.payload.kind }}</b>: {{ e.payload.message }}</span></template>
              <template v-else-if="e.type === 'final_answer'"><div class="text answer">{{ e.payload.text || '(no answer)' }}</div></template>
              <pre v-else>{{ JSON.stringify(e.payload, null, 2) }}</pre>
            </div>
          </div>
        </div>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { api, fmt, FAILURES, type Trial, type TrialEvent } from '../api';

const props = defineProps<{ id: number }>();
const t = ref<Trial>();
const error = ref('');
const expandAll = ref(false);

const LABEL: Record<string, string> = {
  message: 'Message', model_call: 'Model call', tool_call: 'Tool call', tool_result: 'Result', memory_read: 'Memory read',
  memory_write: 'Memory write', skill_used: 'Skill', error: 'Error', final_answer: 'Answer',
};
const short = (s: string) => (s.length > 400 ? s.slice(0, 400) + '…' : s);
const scoreTone = computed(() => (t.value?.score === null ? '' : t.value!.score! >= 1 ? 'good' : t.value!.score! > 0 ? '' : 'bad'));
const signals = computed<string[]>(() => JSON.parse(t.value?.failure_signals || '[]'));
const bySession = computed(() => {
  const g: Record<number, TrialEvent[]> = {};
  for (const e of t.value?.events ?? []) (g[e.session] ??= []).push(e);
  return g;
});

onMounted(async () => {
  try {
    t.value = await api.trial(props.id);
  } catch (e: any) {
    error.value = e.message;
  }
});
</script>

<style scoped>
.summary { gap: 28px; align-items: flex-start; }
.kpi { font-size: 28px; font-weight: 700; font-variant-numeric: tabular-nums; }
.kpi.good { color: var(--good); }
.kpi.bad { color: var(--bad); }
.grade + .grade { margin-top: 14px; }
pre { font-family: var(--mono); font-size: 12.5px; white-space: pre-wrap; word-break: break-word; margin: 6px 0 0;
  background: var(--surface-2); padding: 8px 10px; border-radius: var(--radius-s); max-height: 420px; overflow: auto; }
.reason { background: transparent; padding: 0; }
.session + .session { margin-top: 18px; padding-top: 12px; border-top: 1px solid var(--line); }
.session-label { margin: 8px 0; text-transform: uppercase; letter-spacing: 0.05em; }
.event { display: grid; grid-template-columns: 104px 1fr; gap: 12px; padding: 7px 0; border-bottom: 1px solid var(--line); }
.event:last-child { border-bottom: none; }
.type { font-size: 12px; color: var(--text-2); padding-top: 2px; }
.event.tool_call .type, .event.tool_result .type { color: var(--accent); }
.event.memory_read .type, .event.memory_write .type, .event.skill_used .type { color: #8e5bd8; }
.event.error .type { color: var(--bad); }
.event.final_answer .type { color: var(--text); font-weight: 600; }
.text { white-space: pre-wrap; }
.answer { font-weight: 500; }
.args { word-break: break-all; }
summary { cursor: pointer; }
</style>
