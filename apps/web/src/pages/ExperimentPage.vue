<template>
  <main class="page stack">
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="!c && !error" class="muted">Loading…</p>

    <template v-if="c">
      <div>
        <RouterLink to="/" class="small">‹ Experiments</RouterLink>
        <h1>{{ c.experiment.name }}</h1>
        <p class="muted small">
          <b>A</b> {{ c.experiment.config_a.name }} <code>{{ c.experiment.config_a.id }}</code>
          → <b>B</b> {{ c.experiment.config_b.name }} <code>{{ c.experiment.config_b.id }}</code>
          · N = {{ c.experiment.n_trials }} · code <code>{{ c.experiment.code_sha }}</code>
        </p>
        <p v-if="c.experiment.hypothesis" class="hypothesis">Hypothesis: {{ c.experiment.hypothesis }}</p>
      </div>

      <p v-if="c.code_mismatch" class="card warn">
        <b>{{ c.code_mismatch }} trial(s) ran on different code</b> than this experiment was started with
        (<code>{{ c.experiment.code_sha }}</code>): the code changed while it was running, so these results may not be
        comparable. Run experiments of record from a dedicated git worktree that nobody edits.
      </p>

      <!-- progress -->
      <section class="card" v-if="!c.complete || c.progress.invalid">
        <div class="row">
          <h3 style="margin: 0">{{ c.complete ? 'Finished' : 'Running' }}</h3>
          <span class="muted small">{{ c.progress.done }} done · {{ c.progress.running }} running · {{ c.progress.pending }} queued · {{ c.progress.invalid }} invalid</span>
          <span class="spacer" />
          <button v-if="c.complete && c.progress.invalid" @click="retry">Retry {{ c.progress.invalid }} invalid</button>
        </div>
        <ProgressBar :p="c.progress" style="margin-top: 10px" />
        <p v-if="c.progress.invalid" class="small muted" style="margin-bottom: 0">
          Invalid = the provider or harness failed (rate limit, crash) after retries. These are not counted as wrong
          answers; each one is dropped from both A and B for that task and trial.
        </p>
      </section>

      <!-- verdict -->
      <section class="card verdict" :class="toneOf(s)">
        <div class="row" style="align-items: flex-start">
          <div class="big">
            <div class="muted small">Score change B − A</div>
            <div class="delta">{{ fmt.signed(s.mean_delta, 3) }}</div>
            <div class="small muted">A {{ fmt.num(s.mean_a, 3) }} → B {{ fmt.num(s.mean_b, 3) }}</div>
          </div>
          <div class="spacer" style="min-width: 260px">
            <span class="pill" :class="toneOf(s)">{{ verdictLabel(s) }}</span>
            <p style="margin: 8px 0 6px">{{ s.message }}</p>
            <CiBar :mean="s.mean_delta" :low="s.ci_low" :high="s.ci_high" />
            <p class="small muted" style="margin: 6px 0 0">
              95% CI from 10,000 bootstrap resamples of the {{ s.n_tasks }} tasks ·
              {{ s.tasks_better }} tasks better, {{ s.tasks_worse }} worse, {{ s.tasks_same }} same ·
              noise between repeated runs (SD) {{ fmt.num(s.within_task_sd, 2) }}
              <span v-if="!c.complete"> · <b>partial: still running</b></span>
            </p>
          </div>
        </div>
      </section>

      <!-- quality next to cost -->
      <section class="card">
        <h2>Quality, cost and speed</h2>
        <table>
          <thead><tr><th>Metric (per trial)</th><th class="num">A</th><th class="num">B</th><th class="num">B − A</th><th class="num">95% CI</th><th>Verdict</th></tr></thead>
          <tbody>
            <tr v-for="m in metricRows" :key="m.key">
              <td>{{ m.label }}<div v-if="m.note" class="small muted">{{ m.note }}</div></td>
              <td class="num">{{ m.f(c.metrics[m.key].mean_a) }}</td>
              <td class="num">{{ m.f(c.metrics[m.key].mean_b) }}</td>
              <td class="num">{{ m.f(c.metrics[m.key].mean_delta, true) }}</td>
              <td class="num small">[{{ m.f(c.metrics[m.key].ci_low, true) }}, {{ m.f(c.metrics[m.key].ci_high, true) }}]</td>
              <td><span class="pill" :class="m.lowerIsBetter ? flip(toneOf(c.metrics[m.key])) : toneOf(c.metrics[m.key])">{{ m.lowerIsBetter ? costLabel(c.metrics[m.key]) : verdictLabel(c.metrics[m.key]) }}</span></td>
            </tr>
          </tbody>
        </table>
        <table style="margin-top: 16px">
          <thead><tr><th>Config</th><th class="num">Trials</th><th class="num">Invalid</th><th class="num">Mean score</th><th class="num">Tokens (in / out)</th><th class="num">Actual cost</th><th class="num">At Opus 5.5 list price</th></tr></thead>
          <tbody>
            <tr v-for="t in c.totals" :key="t.config_id">
              <td>{{ t.config }}</td><td class="num">{{ t.trials }}</td><td class="num">{{ t.invalid }}</td>
              <td class="num">{{ fmt.num(t.mean_score, 3) }}</td>
              <td class="num">{{ fmt.int(t.input_tokens) }} / {{ fmt.int(t.output_tokens) }}</td>
              <td class="num">{{ fmt.usd(t.cost_usd) }}</td><td class="num">{{ fmt.usd(t.ref_cost_usd) }}</td>
            </tr>
          </tbody>
        </table>
        <div class="row" style="margin-top: 16px">
          <span class="spacer" />
          <a :href="`/api/experiments/${id}/export.json`" download><button>Export JSON</button></a>
          <a :href="`/api/experiments/${id}/export.csv`" download><button>Export CSV</button></a>
        </div>
      </section>

      <!-- failure analysis -->
      <section class="card" v-if="failureRows.length">
        <h2>Why trials failed</h2>
        <p class="small muted">Each failed trial gets one category from its trace (first matching rule). Open a trial to see the evidence.</p>
        <table>
          <thead><tr><th>Category</th><th class="num">A</th><th class="num">B</th><th class="num">B − A</th></tr></thead>
          <tbody>
            <tr v-for="r in failureRows" :key="r.category">
              <td><b>{{ r.category }}</b><div class="small muted">{{ FAILURES[r.category] ?? '' }}</div></td>
              <td class="num">{{ r.a }}</td><td class="num">{{ r.b }}</td>
              <td class="num" :class="r.b > r.a ? 'bad' : r.b < r.a ? 'good' : 'muted'">{{ r.b - r.a > 0 ? '+' : '' }}{{ r.b - r.a }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- per-task -->
      <section class="card">
        <h2>Per task</h2>
        <p class="small muted">Each dot is one trial (green pass, amber partial, red fail, grey not finished). Click a dot to see why.</p>
        <table>
          <thead><tr><th>Task</th><th>A trials</th><th>B trials</th><th class="num">A</th><th class="num">B</th><th style="width: 160px">B − A</th></tr></thead>
          <tbody>
            <tr v-for="row in taskRows" :key="row.task_id">
              <td>{{ row.task_id }}</td>
              <td><TrialDots :trials="row.a" /></td>
              <td><TrialDots :trials="row.b" /></td>
              <td class="num">{{ fmt.num(row.d?.mean_a, 2) }}</td>
              <td class="num">{{ fmt.num(row.d?.mean_b, 2) }}</td>
              <td>
                <div v-if="row.d" class="deltabar">
                  <span class="axis" />
                  <span class="fill" :class="row.d.delta > 0 ? 'good' : 'bad'"
                    :style="{ left: row.d.delta >= 0 ? '50%' : `${50 + row.d.delta * 50}%`, width: `${Math.abs(row.d.delta) * 50}%` }" />
                  <span class="label small">{{ fmt.signed(row.d.delta, 2) }}</span>
                </div>
                <span v-else class="muted small">–</span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { api, fmt, FAILURES, type CompareResponse, type Comparison, type TrialRow } from '../api';
import CiBar from '../components/CiBar.vue';
import ProgressBar from '../components/ProgressBar.vue';
import TrialDots from '../components/TrialDots.vue';

const props = defineProps<{ id: number }>();
const c = ref<CompareResponse>();
const trials = ref<TrialRow[]>([]);
const error = ref('');
const s = computed(() => c.value!.metrics.score);

const toneOf = (m: Comparison) => (m.verdict === 'B better' ? 'good' : m.verdict === 'B worse' ? 'bad' : '');
const flip = (t: string) => (t === 'good' ? 'bad' : t === 'bad' ? 'good' : '');
const verdictLabel = (m: Comparison) =>
  ({ 'no detectable difference': 'No detectable difference (could be noise)', 'too few tasks': 'Too few tasks to judge',
     'B better': 'B better', 'B worse': 'B worse' })[m.verdict];
const costLabel = (m: Comparison) =>
  ({ 'no detectable difference': 'No detectable difference', 'too few tasks': 'Too few tasks to judge',
     'B better': 'B higher', 'B worse': 'B lower' })[m.verdict];

interface MetricRow { key: keyof CompareResponse['metrics']; label: string; note?: string; lowerIsBetter?: boolean; f: (x: number, sign?: boolean) => string }
const metricRows: MetricRow[] = [
  { key: 'score', label: 'Score (0–1)', f: (x: number, sign = false) => (sign ? fmt.signed(x, 3) : fmt.num(x, 3)) },
  { key: 'total_tokens', label: 'Tokens', lowerIsBetter: true, f: (x: number, sign = false) => (sign && x > 0 ? '+' : '') + fmt.int(x) },
  { key: 'latency_s', label: 'Latency (s)', lowerIsBetter: true, f: (x: number, sign = false) => (sign ? fmt.signed(x, 1) : fmt.num(x, 1)) },
  { key: 'cost_usd', label: 'Actual cost', note: 'free tiers and local models = $0', lowerIsBetter: true, f: (x: number) => fmt.usd(x) },
  { key: 'ref_cost_usd', label: 'Cost at Claude Opus 5.5 list price', note: '$4 / $20 per 1M tokens in / out', lowerIsBetter: true,
    f: (x: number) => (x < 0 ? '−' : '') + fmt.usd(Math.abs(x)) },
];

const failureRows = computed(() => {
  if (!c.value) return [];
  const rows = new Map<string, { category: string; a: number; b: number }>();
  for (const f of c.value.failures) {
    const r = rows.get(f.category) ?? { category: f.category, a: 0, b: 0 };
    if (f.config_id === c.value.experiment.config_a.id) r.a += f.n;
    else r.b += f.n;
    rows.set(f.category, r);
  }
  const order = Object.keys(FAILURES);
  return [...rows.values()].sort((x, y) => order.indexOf(x.category) - order.indexOf(y.category));
});

const taskRows = computed(() => {
  if (!c.value) return [];
  const byTask = new Map<string, { a: TrialRow[]; b: TrialRow[] }>();
  for (const t of trials.value) {
    const r = byTask.get(t.task_id) ?? { a: [], b: [] };
    (t.config_id === c.value.experiment.config_a.id ? r.a : r.b).push(t);
    byTask.set(t.task_id, r);
  }
  const deltas = new Map(s.value.tasks.map((d) => [d.task_id, d]));
  return [...byTask.entries()]
    .map(([task_id, r]) => ({ task_id, ...r, d: deltas.get(task_id) }))
    .sort((x, y) => (x.d?.delta ?? 0) - (y.d?.delta ?? 0) || x.task_id.localeCompare(y.task_id));
});

async function load() {
  try {
    [c.value, trials.value] = await Promise.all([api.compare(props.id), api.trials(props.id)]);
    error.value = '';
  } catch (e: any) {
    error.value = e.message;
  }
}
async function retry() {
  await api.retryInvalid(props.id);
  await load();
}

let timer: number | undefined;
onMounted(async () => {
  await load();
  timer = window.setInterval(() => !c.value?.complete && load(), 2000);
});
onUnmounted(() => clearInterval(timer));
</script>

<style scoped>
.warn { border-left: 4px solid var(--bad); }
.hypothesis { font-style: italic; margin: 6px 0 0; }
.verdict { border-left: 4px solid var(--line); }
.verdict.good { border-left-color: var(--good); }
.verdict.bad { border-left-color: var(--bad); }
.big { min-width: 180px; }
.delta { font-size: 40px; font-weight: 700; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; }
.verdict.good .delta { color: var(--good); }
.verdict.bad .delta { color: var(--bad); }
.deltabar { position: relative; height: 18px; }
.deltabar .axis { position: absolute; left: 50%; top: 0; bottom: 0; border-left: 1px dashed var(--text-2); }
.deltabar .fill { position: absolute; top: 5px; height: 8px; border-radius: 3px; }
.deltabar .fill.good { background: var(--good); }
.deltabar .fill.bad { background: var(--bad); }
.deltabar .label { position: absolute; right: 0; top: -1px; font-variant-numeric: tabular-nums; color: var(--text-2); }
</style>
