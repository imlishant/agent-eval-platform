import { scrubIds } from '../src/scheduler.service';
import { bootstrapCI, compare, mulberry32, percentile, TrialRow } from '../src/stats';

const rows = (data: Record<string, (number | null)[]>, status: Record<string, string[]> = {}): TrialRow[] =>
  Object.entries(data).flatMap(([task, vals]) =>
    vals.map((v, i) => ({ task_id: task, trial_index: i, status: status[task]?.[i] ?? 'done', value: v })));

describe('paired comparison', () => {
  test('hand-computed example: per-task means and deltas', () => {
    // t1: A=(1,0,1)=0.667  B=(1,1,1)=1     delta +0.333
    // t2: A=(0,0,0)=0      B=(1,0,0)=0.333 delta +0.333
    // t3: A=(1,1,1)=1      B=(1,1,0)=0.667 delta -0.333
    const a = rows({ t1: [1, 0, 1], t2: [0, 0, 0], t3: [1, 1, 1] });
    const b = rows({ t1: [1, 1, 1], t2: [1, 0, 0], t3: [1, 1, 0] });
    const c = compare(a, b);
    const d = Object.fromEntries(c.tasks.map((t) => [t.task_id, t.delta]));
    expect(d.t1).toBeCloseTo(1 / 3);
    expect(d.t2).toBeCloseTo(1 / 3);
    expect(d.t3).toBeCloseTo(-1 / 3);
    expect(c.mean_delta).toBeCloseTo(1 / 9);
    expect([c.tasks_better, c.tasks_worse, c.tasks_same]).toEqual([2, 1, 0]);
    // the bootstrap mean can only be one of the averages of 3 deltas from {+1/3, +1/3, -1/3}
    expect(c.ci_low).toBeCloseTo(-1 / 3);
    expect(c.ci_high).toBeCloseTo(1 / 3);
    expect(c.verdict).toBe('too few tasks'); // 3 < MIN_TASKS: no verdict from a 3-task bootstrap
  });

  test('no detectable difference when the CI includes 0', () => {
    const a = rows({ t1: [1], t2: [0], t3: [1], t4: [0], t5: [1], t6: [0] });
    const b = rows({ t1: [0], t2: [1], t3: [1], t4: [0], t5: [0], t6: [1] });
    const c = compare(a, b);
    expect(c.verdict).toBe('no detectable difference');
    expect(c.message).toMatch(/could be noise/);
  });

  test('invalid trials drop the pair on both sides and are counted', () => {
    const a = rows({ t1: [1, 0], t2: [1, 1] }, { t1: ['done', 'invalid'] });
    const b = rows({ t1: [0, 1], t2: [1, 1] });
    const c = compare(a, b);
    const t1 = c.tasks.find((t) => t.task_id === 't1')!;
    expect(t1.n_pairs).toBe(1); // trial 1 dropped for A and B
    expect(t1.delta).toBeCloseTo(-1);
    expect(c.dropped_pairs).toBe(1);
  });

  test('same data gives the same CI (seeded)', () => {
    const d = [0.1, -0.2, 0.3, 0.05, 0];
    expect(bootstrapCI(d)).toEqual(bootstrapCI(d));
  });

  test('a large consistent effect is detected', () => {
    const tasks = Object.fromEntries(Array.from({ length: 20 }, (_, i) => [`t${i}`, [0, 0, 0]]));
    const better = Object.fromEntries(Array.from({ length: 20 }, (_, i) => [`t${i}`, i % 5 === 0 ? [0, 1, 0] : [1, 1, 1]]));
    const c = compare(rows(tasks), rows(better));
    expect(c.verdict).toBe('B better');
    expect(c.ci_low).toBeGreaterThan(0);
  });

  test('no real difference: the 95% CI contains 0 about 95% of the time', () => {
    // Simulate many experiments where A and B are the SAME agent: each task has its own pass rate,
    // both configs draw from it. A correct CI should contain 0 in roughly 95% of experiments.
    const rand = mulberry32(7);
    let contains = 0;
    const sims = 300;
    for (let s = 0; s < sims; s++) {
      const a: TrialRow[] = [];
      const b: TrialRow[] = [];
      for (let t = 0; t < 20; t++) {
        const p = rand();
        for (let i = 0; i < 3; i++) {
          a.push({ task_id: `t${t}`, trial_index: i, status: 'done', value: rand() < p ? 1 : 0 });
          b.push({ task_id: `t${t}`, trial_index: i, status: 'done', value: rand() < p ? 1 : 0 });
        }
      }
      const c = compare(a, b, { iterations: 2000, seed: s });
      if (c.ci_low <= 0 && c.ci_high >= 0) contains++;
    }
    const coverage = contains / sims;
    // percentile bootstrap with 20 tasks under-covers slightly; accept 0.88..0.99
    expect(coverage).toBeGreaterThan(0.88);
    expect(coverage).toBeLessThan(0.99);
  });

  test('percentile interpolates', () => {
    expect(percentile([0, 10], 0.5)).toBe(5);
  });
});

test('account IDs are scrubbed from stored errors', () => {
  const out = scrubIds('429 in organization `org_01abcdefghij0123456789` (ops@example.com) projects/123456789012');
  expect(out).not.toMatch(/org_01abc|ops@example|123456789012/);
  expect(out).toContain('org_[REDACTED]');
});

