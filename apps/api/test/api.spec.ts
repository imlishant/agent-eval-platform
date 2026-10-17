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
    task_ids: ['count-csv-rows', 'write-json-config', 'fix-pagination'], n_trials: 2,
  });
  expect(exp.progress.total).toBe(3 * 2 * 2);
  await waitDone(exp.id);

  const c = svc.compare(exp.id);
  expect(c.complete).toBe(true);
  expect(c.metrics.score.mean_delta).toBeCloseTo(1);
  expect(c.metrics.score.tasks_better).toBe(3);
  expect(c.metrics.score.verdict).toBe('B better');
  expect(c.metrics.cost_usd.mean_delta).toBe(0); // mock: no tokens

  const trials = svc.trials(exp.id) as any[];
  const t = svc.trial(trials.find((x) => x.status === 'done').id);
  expect(t.events.length).toBeGreaterThan(0);
  expect(t.grades.length).toBeGreaterThan(0);
  expect(t.isolation).toBeTruthy();

  const csv = svc.exportCsv(exp.id).trim().split('\n');
  expect(csv).toHaveLength(1 + 12);
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
