/**
 * Paired comparison of config A vs config B over the same tasks (PLAN §8).
 *
 * 1. For each task: mean of the metric over its N trials, for A and for B.
 * 2. delta(task) = meanB - meanA. Every delta is reported.
 * 3. Overall effect = mean of the task deltas.
 * 4. 95% CI by bootstrap over TASKS: resample tasks with replacement 10,000 times, recompute the mean delta,
 *    take the 2.5th and 97.5th percentiles. Tasks are the unit because task-to-task variation is the main
 *    source of uncertainty, and the same tasks are used for A and B (that is the pairing).
 * 5. If the CI contains 0 the verdict is "no detectable difference (could be noise)".
 * 5b. Below MIN_TASKS finished tasks there is no verdict at all: a bootstrap over 2-4 tasks can only take a
 *    handful of values, so its "CI" is not a confidence interval.
 * 6. Invalid trials (infrastructure failures) are dropped together with the same trial index of the other
 *    config, so both sides of each task are averaged over the same number of trials.
 */

export interface TrialRow {
  task_id: string;
  trial_index: number;
  status: string; // done | invalid | pending | running
  value: number | null; // the metric for this trial (score, cost, tokens, latency)
}

export interface TaskDelta {
  task_id: string;
  n_pairs: number;
  mean_a: number;
  mean_b: number;
  delta: number;
  sd_a: number; // spread across repeated trials of the same task (within-task noise)
  sd_b: number;
}

export interface Comparison {
  n_tasks: number;
  mean_a: number;
  mean_b: number;
  mean_delta: number;
  ci_low: number;
  ci_high: number;
  verdict: 'B better' | 'B worse' | 'no detectable difference' | 'too few tasks';
  message: string;
  mde: number; // minimum detectable effect at 80% power, alpha 0.05
  tasks_better: number;
  tasks_worse: number;
  tasks_same: number;
  within_task_sd: number; // average SD across repeated trials (noise per run)
  between_task_sd: number; // SD of task deltas (how much tasks disagree)
  dropped_pairs: number; // trial pairs dropped because one side was invalid
  tasks: TaskDelta[];
}

export const MIN_TASKS = 5;

/** Small seeded PRNG so the same data always gives the same CI (reproducibility). */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const mean = (xs: number[]) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : 0);
const sd = (xs: number[]) => {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return Math.sqrt(xs.reduce((s, x) => s + (x - m) ** 2, 0) / (xs.length - 1));
};

export function percentile(sorted: number[], p: number): number {
  const i = (sorted.length - 1) * p;
  const lo = Math.floor(i);
  const hi = Math.ceil(i);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
}

export function bootstrapCI(deltas: number[], iterations = 10_000, seed = 42): [number, number] {
  if (deltas.length === 0) return [0, 0];
  const rand = mulberry32(seed);
  const means: number[] = new Array(iterations);
  for (let b = 0; b < iterations; b++) {
    let s = 0;
    for (let i = 0; i < deltas.length; i++) s += deltas[Math.floor(rand() * deltas.length)];
    means[b] = s / deltas.length;
  }
  means.sort((x, y) => x - y);
  return [percentile(means, 0.025), percentile(means, 0.975)];
}

export function compare(a: TrialRow[], b: TrialRow[], opts: { iterations?: number; seed?: number; eps?: number } = {}): Comparison {
  const eps = opts.eps ?? 1e-9;
  const key = (r: TrialRow) => `${r.task_id}#${r.trial_index}`;
  const bByKey = new Map(b.map((r) => [key(r), r]));
  const perTask = new Map<string, { a: number[]; b: number[] }>();
  let dropped = 0;

  for (const ra of a) {
    const rb = bByKey.get(key(ra));
    if (!rb) continue;
    const bothDone = ra.status === 'done' && rb.status === 'done' && ra.value !== null && rb.value !== null;
    if (!bothDone) {
      if (ra.status === 'invalid' || rb.status === 'invalid') dropped++;
      continue;
    }
    const t = perTask.get(ra.task_id) ?? { a: [], b: [] };
    t.a.push(ra.value as number);
    t.b.push(rb.value as number);
    perTask.set(ra.task_id, t);
  }

  const tasks: TaskDelta[] = [...perTask.entries()]
    .map(([task_id, v]) => ({
      task_id,
      n_pairs: v.a.length,
      mean_a: mean(v.a),
      mean_b: mean(v.b),
      delta: mean(v.b) - mean(v.a),
      sd_a: sd(v.a),
      sd_b: sd(v.b),
    }))
    .sort((x, y) => x.delta - y.delta || x.task_id.localeCompare(y.task_id));

  const deltas = tasks.map((t) => t.delta);
  const [lo, hi] = bootstrapCI(deltas, opts.iterations, opts.seed);
  const md = mean(deltas);
  const halfWidth = (hi - lo) / 2;
  // SE ~ halfWidth / 1.96; MDE (80% power, two-sided 5%) ~ (1.96 + 0.84) * SE
  const mde = (2.8 / 1.96) * halfWidth;

  let verdict: Comparison['verdict'] = 'no detectable difference';
  if (lo > 0) verdict = 'B better';
  if (hi < 0) verdict = 'B worse';
  if (tasks.length < MIN_TASKS) verdict = 'too few tasks';
  const message =
    verdict === 'too few tasks'
      ? `Too few tasks to judge: ${tasks.length} finished, at least ${MIN_TASKS} are needed for a meaningful interval.`
      : verdict === 'no detectable difference'
      ? `No detectable difference (could be noise): the 95% CI [${lo.toFixed(3)}, ${hi.toFixed(3)}] includes 0. ` +
        `With ${tasks.length} tasks, only effects larger than about ${mde.toFixed(3)} would be reliably detected.`
      : `${verdict === 'B better' ? 'B is better' : 'B is worse'} by ${Math.abs(md).toFixed(3)} on average; ` +
        `95% CI [${lo.toFixed(3)}, ${hi.toFixed(3)}] excludes 0.`;

  return {
    n_tasks: tasks.length,
    mean_a: mean(tasks.map((t) => t.mean_a)),
    mean_b: mean(tasks.map((t) => t.mean_b)),
    mean_delta: md,
    ci_low: lo,
    ci_high: hi,
    verdict,
    message,
    mde,
    tasks_better: tasks.filter((t) => t.delta > eps).length,
    tasks_worse: tasks.filter((t) => t.delta < -eps).length,
    tasks_same: tasks.filter((t) => Math.abs(t.delta) <= eps).length,
    within_task_sd: mean(tasks.flatMap((t) => [t.sd_a, t.sd_b])),
    between_task_sd: sd(deltas),
    dropped_pairs: dropped,
    tasks,
  };
}
