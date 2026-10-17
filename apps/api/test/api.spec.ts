/**
 * End to end through the real runner (Python) with the free mock harness:
 * create experiment -> scheduler runs trials -> compare -> export. No model, no key.
 */
import { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { mkdtempSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

process.env.DB_PATH = join(mkdtempSync(join(tmpdir(), 'evals-db-')), 'test.db');
process.env.RETRY_BASE_MS = '0';

import { AppModule } from '../src/app.module';
import { ExperimentsService } from '../src/experiments.service';
import { SchedulerService } from '../src/scheduler.service';

let app: INestApplication;
let svc: ExperimentsService;
let scheduler: SchedulerService;

beforeAll(async () => {
  const mod = await Test.createTestingModule({ imports: [AppModule] }).compile();
  app = mod.createNestApplication();
  await app.init();
  svc = app.get(ExperimentsService);
  scheduler = app.get(SchedulerService);
});
afterAll(() => app.close());

async function waitDone(id: number) {
  for (let i = 0; i < 240; i++) {
    const p = svc.get(id).progress;
    if (p.pending + p.running === 0) return;
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error('experiment did not finish');
}

test('mock-fail vs mock-solve: B is better on every task, results persisted and exportable', async () => {
  const exp = await svc.create({
    name: 'pipeline test', hypothesis: 'solve beats fail', config_a: 'mock-fail.json', config_b: 'mock-solve.json',
    task_ids: ['count-csv-rows', 'write-json-config', 'fix-pagination', 'sum-amounts', 'fix-failing-test'], n_trials: 2,
  });
  expect(exp.progress.total).toBe(5 * 2 * 2);
  await waitDone(exp.id);

  const c = svc.compare(exp.id);
  expect(c.complete).toBe(true);
  expect(c.metrics.score.mean_delta).toBeCloseTo(1);
  expect(c.metrics.score.tasks_better).toBe(5);
  expect(c.metrics.score.verdict).toBe('B better');
  expect(c.metrics.cost_usd.mean_delta).toBe(0); // mock: no tokens

  const trials = svc.trials(exp.id) as any[];
  const t = svc.trial(trials.find((x) => x.status === 'done').id);
  expect(t.events.length).toBeGreaterThan(0);
  expect(t.grades.length).toBeGreaterThan(0);
  expect(t.isolation).toBeTruthy();

  // every failed trial (mock-fail does nothing) has a category; mock-fail answers without tools -> gave_up_early
  const failA = c.failures.filter((f: any) => f.config_id === c.experiment.config_a.id);
  expect(failA.reduce((s: number, f: any) => s + f.n, 0)).toBe(10);
  expect(failA.map((f: any) => f.category)).toEqual(['gave_up_early']);
  expect(c.failures.some((f: any) => f.config_id === c.experiment.config_b.id)).toBe(false);
  // API and runner compute the code version the same way: nothing changed mid-run, so no mismatch
  expect(c.code_mismatch).toBe(0);
  const db: any = (svc as any).db.db;
  db.prepare(`UPDATE trials SET code_version = 'other' WHERE id = ?`).run(trials[0].id);
  expect(svc.compare(exp.id).code_mismatch).toBe(1);

  const csv = svc.exportCsv(exp.id).trim().split('\n');
  expect(csv).toHaveLength(1 + 20);
  expect(csv[0]).toContain('task_id,config_name');
});

test('an infrastructure failure is retried, then marked invalid, never scored', async () => {
  const exp = await svc.create({ name: 'invalid test', config_a: 'mock-fail.json', config_b: 'mock-solve.json',
    task_ids: ['count-csv-rows'], n_trials: 1 });
  const trials = svc.trials(exp.id) as any[];
  const db: any = (svc as any).db.db;
  // simulate: provider down on every attempt for config A's trial
  const target = trials[0];
  db.prepare(`UPDATE trials SET status = 'running', attempts = 1 WHERE id = ?`).run(target.id);
  scheduler.save(target.id, { status: 'invalid', error: 'HTTP 429' }, {});
  expect(svc.trial(target.id).status).toBe('pending'); // retried
  db.prepare(`UPDATE trials SET status = 'running', attempts = 3 WHERE id = ?`).run(target.id);
  scheduler.save(target.id, { status: 'invalid', error: 'HTTP 429' }, {});
  const final = svc.trial(target.id);
  expect(final.status).toBe('invalid');
  expect(final.score).toBeNull();
  await waitDone(exp.id);
  expect(svc.compare(exp.id).metrics.score.dropped_pairs).toBe(1);
});

test('rejects identical configs and unknown tasks', async () => {
  await expect(svc.create({ name: 'x', config_a: 'mock-solve.json', config_b: 'mock-solve.json' })).rejects.toThrow(/identical/);
  await expect(svc.create({ name: 'x', config_a: 'mock-fail.json', config_b: 'mock-solve.json', task_ids: ['nope'] })).rejects.toThrow(/unknown tasks/);
});

test('a config defined through the API is saved, validated and gets a content-hash ID', async () => {
  const { RunnerService } = await import('../src/runner.service');
  const runner = app.get(RunnerService);
  const { rmSync } = await import('fs');
  const { REPO } = await import('../src/paths');
  const name = `test-cfg-${Date.now()}`;
  try {
    const c = await runner.createConfig({ name, harness: 'mock', model: { provider: 'none', id: 'none' },
      settings: { extra: { behavior: 'solve' } } });
    expect(c.file).toBe(`${name}.json`);
    expect(c.id).toBe('9e52e991ae9f'); // same content as mock-solve.json => same ID (name is not part of it)
    await expect(runner.createConfig({ name, harness: 'mock', model: {} })).rejects.toThrow(/already exists/);
    await expect(runner.createConfig({ name: `${name}-bad`, harness: 'mock', model: { nope: 1 } })).rejects.toThrow(/invalid config/);
    await expect(runner.createConfig({ name: 'Bad Name!' })).rejects.toThrow(/lowercase/);
  } finally {
    rmSync(join(REPO, 'configs', `${name}.json`), { force: true });
    rmSync(join(REPO, 'configs', `${name}-bad.json`), { force: true });
  }
});

test('experiments can be built from drafts (harness x model x settings); same content reuses the saved config', async () => {
  const exp = await svc.create({
    name: 'drafts', config_a: { harness: 'mock', model: 'none', settings: { extra: { behavior: 'fail' } } },
    config_b: { harness: 'mock', model: 'none', settings: { extra: { behavior: 'solve' } } },
    task_ids: ['count-csv-rows'], n_trials: 1,
  });
  expect(exp.config_a).toBe('864ccf856779'); // identical content to configs/mock-fail.json -> same ID, no new file
  expect(exp.config_b).toBe('9e52e991ae9f'); // = mock-solve.json
  await expect(svc.create({ name: 'x', config_a: { harness: 'nope', model: 'none' }, config_b: 'mock-solve.json' }))
    .rejects.toThrow(/unknown harness/);
  await expect(svc.create({ name: 'x', config_a: { harness: 'mock', model: 'nope' }, config_b: 'mock-solve.json' }))
    .rejects.toThrow(/unknown model/);
  await waitDone(exp.id);
});

test('model registry rejects bad entries and never accepts a key value', async () => {
  const { RunnerService } = await import('../src/runner.service');
  const runner = app.get(RunnerService);
  expect(() => runner.addModel({ name: 'Bad Name' })).toThrow(/lowercase/);
  expect(() => runner.addModel({ name: 'ok-name', id: 'm', base_url: 'not a url' })).toThrow(/full URL/);
  expect(() => runner.addModel({ name: 'ok-name', id: 'm', base_url: 'https://x.ai/v1', api_key_env: 'sk-abc123secret' }))
    .toThrow(/NAME of an env var/);
});

test('the runs list reports a finished experiment as done without opening it first', async () => {
  const exp = await svc.create({ name: 'status', config_a: 'mock-fail.json', config_b: 'mock-solve.json',
    task_ids: ['count-csv-rows'], n_trials: 1 });
  const db: any = (svc as any).db.db;
  for (let i = 0; i < 200; i++) {
    const { n } = db.prepare(`SELECT COUNT(*) n FROM trials WHERE experiment_id = ? AND status IN ('pending','running')`).get(exp.id);
    if (n === 0) break;
    await new Promise((r) => setTimeout(r, 100));
  }
  expect(svc.list().find((e: any) => e.id === exp.id).status).toBe('done');
});

