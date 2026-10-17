import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { DbService } from './db.service';
import { CatalogConfig, ConfigDraft, RunnerService } from './runner.service';
import { compare, TrialRow } from './stats';

export interface CreateExperiment {
  name: string;
  hypothesis?: string;
  config_a: string | ConfigDraft; // saved config (file name or id), or a draft built in the UI
  config_b: string | ConfigDraft;
  task_ids?: string[]; // default: all tasks
  n_trials?: number;
}

const METRICS = {
  score: 'score',
  cost_usd: 'cost_usd',
  ref_cost_usd: 'ref_cost_usd',
  total_tokens: 'input_tokens + output_tokens',
  latency_s: 'latency_ms / 1000.0',
} as const;

@Injectable()
export class ExperimentsService {
  constructor(private readonly db: DbService, private readonly runner: RunnerService) {}

  async create(body: CreateExperiment) {
    const resolve = async (ref: string | ConfigDraft): Promise<CatalogConfig | undefined> => {
      if (typeof ref === 'object' && ref) {
        try {
          return await this.runner.resolveDraft(ref);
        } catch (e: any) {
          throw new BadRequestException(e.message);
        }
      }
      const configs = (await this.runner.catalog()).configs;
      return configs.find((c) => c.file === ref || c.id === ref || c.name === ref);
    };
    const a = await resolve(body.config_a);
    const b = await resolve(body.config_b);
    if (!a || !b) throw new BadRequestException('config_a and config_b must name a saved config, or be {harness, model, settings}');
    const cat = await this.runner.catalog();
    if (a.id === b.id) throw new BadRequestException('config A and B are identical (same content hash)');
    const taskIds = body.task_ids?.length ? body.task_ids : cat.tasks.map((t) => t.id);
    const unknown = taskIds.filter((id) => !cat.tasks.some((t) => t.id === id));
    if (unknown.length) throw new BadRequestException(`unknown tasks: ${unknown.join(', ')}`);
    const n = body.n_trials ?? 3;
    if (!Number.isInteger(n) || n < 1 || n > 20) throw new BadRequestException('n_trials must be 1..20');
    const hashes = Object.fromEntries(cat.tasks.filter((t) => taskIds.includes(t.id)).map((t) => [t.id, t.hash]));
    const sha = await this.runner.codeSha();
    const now = new Date().toISOString();
    const db = this.db.db;

    const id = db.transaction(() => {
      const upsert = db.prepare(`INSERT OR IGNORE INTO configs (id, name, json, created_at) VALUES (?, ?, ?, ?)`);
      upsert.run(a.id, a.name, JSON.stringify(a.config), now);
      upsert.run(b.id, b.name, JSON.stringify(b.config), now);
      const exp = db
        .prepare(
          `INSERT INTO experiments (name, hypothesis, config_a, config_b, task_ids, task_hashes, n_trials, code_sha, created_at, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'running')`,
        )
        .run(body.name, body.hypothesis ?? '', a.id, b.id, JSON.stringify(taskIds), JSON.stringify(hashes), n, sha, now);
      const ins = db.prepare(
        `INSERT INTO trials (experiment_id, task_id, config_id, trial_index, status) VALUES (?, ?, ?, ?, 'pending')`,
      );
      // interleave A and B per task and trial, so a quota cut-off leaves both sides equally covered
      for (let i = 0; i < n; i++) for (const t of taskIds) for (const c of [a.id, b.id]) ins.run(exp.lastInsertRowid, t, c, i);
      return Number(exp.lastInsertRowid);
    })();
    return this.get(id);
  }

  list() {
    return this.db.db
      .prepare(`SELECT e.*, ca.name AS config_a_name, cb.name AS config_b_name FROM experiments e
                JOIN configs ca ON ca.id = e.config_a JOIN configs cb ON cb.id = e.config_b ORDER BY e.id DESC`)
      .all()
      .map((e: any) => {
        const progress = this.progress(e.id);
        return { ...e, status: this.refreshStatus(e.id, e.status, progress), task_ids: JSON.parse(e.task_ids),
          task_hashes: JSON.parse(e.task_hashes), progress };
      });
  }

  get(id: number) {
    const e: any = this.db.db
      .prepare(`SELECT e.*, ca.name AS config_a_name, ca.json AS config_a_json, cb.name AS config_b_name, cb.json AS config_b_json
                FROM experiments e JOIN configs ca ON ca.id = e.config_a JOIN configs cb ON cb.id = e.config_b WHERE e.id = ?`)
      .get(id);
    if (!e) throw new NotFoundException(`experiment ${id} not found`);
    const progress = this.progress(id);
    e.status = this.refreshStatus(id, e.status, progress);
    return {
      ...e,
      task_ids: JSON.parse(e.task_ids),
      task_hashes: JSON.parse(e.task_hashes),
      config_a_json: JSON.parse(e.config_a_json),
      config_b_json: JSON.parse(e.config_b_json),
      progress,
    };
  }

  /** An experiment is done when no trial is pending or running; every reader sees the same status. */
  private refreshStatus(id: number, status: string, p: { pending: number; running: number }): string {
    if (status === 'running' && p.pending + p.running === 0) {
      this.db.db.prepare(`UPDATE experiments SET status = 'done' WHERE id = ?`).run(id);
      return 'done';
    }
    return status;
  }

  progress(id: number) {
    const rows = this.db.db.prepare(`SELECT status, COUNT(*) n FROM trials WHERE experiment_id = ? GROUP BY status`).all(id) as any[];
    const p = { total: 0, pending: 0, running: 0, done: 0, invalid: 0 };
    for (const r of rows) {
      (p as any)[r.status] = r.n;
      p.total += r.n;
    }
    return p;
  }

  trials(id: number) {
    return this.db.db
      .prepare(`SELECT t.*, c.name AS config_name FROM trials t JOIN configs c ON c.id = t.config_id
                WHERE experiment_id = ? ORDER BY task_id, trial_index, config_id`)
      .all(id);
  }

  /** Quality, cost, tokens and latency side by side, each with per-task deltas and a bootstrap CI. */
  compare(id: number) {
    const e = this.get(id);
    const rows = (configId: string, metric: string): TrialRow[] =>
      this.db.db
        .prepare(`SELECT task_id, trial_index, status, ${metric} AS value FROM trials WHERE experiment_id = ? AND config_id = ?`)
        .all(id, configId) as TrialRow[];
    const metrics = Object.fromEntries(
      Object.entries(METRICS).map(([name, sql]) => [name, compare(rows(e.config_a, sql), rows(e.config_b, sql))]),
    );
    return {
      experiment: { id: e.id, name: e.name, hypothesis: e.hypothesis, status: e.status, n_trials: e.n_trials,
        code_sha: e.code_sha, config_a: { id: e.config_a, name: e.config_a_name }, config_b: { id: e.config_b, name: e.config_b_name } },
      progress: e.progress,
      complete: e.progress.pending + e.progress.running === 0,
      metrics,
      totals: this.totals(id),
      failures: this.failures(id),
      // trials that ran on different code than the experiment was created with (code changed mid-run)
      code_mismatch: (this.db.db.prepare(`SELECT COUNT(*) n FROM trials WHERE experiment_id = ? AND status = 'done'
        AND code_version IS NOT NULL AND code_version != ?`).get(id, e.code_sha) as { n: number }).n,
    };
  }

  totals(id: number) {
    return this.db.db
      .prepare(`SELECT c.name AS config, t.config_id, COUNT(*) AS trials, SUM(t.status = 'invalid') AS invalid,
                AVG(t.score) AS mean_score, SUM(t.input_tokens) AS input_tokens, SUM(t.output_tokens) AS output_tokens,
                SUM(t.cost_usd) AS cost_usd, SUM(t.ref_cost_usd) AS ref_cost_usd, AVG(t.latency_ms) AS mean_latency_ms
                FROM trials t JOIN configs c ON c.id = t.config_id WHERE t.experiment_id = ? GROUP BY t.config_id
                ORDER BY t.config_id = (SELECT config_b FROM experiments WHERE id = ?)`)
      .all(id, id);
  }

  /** Failed trials per config and failure category, so a regression points to a cause. */
  failures(id: number) {
    return this.db.db
      .prepare(`SELECT c.name AS config, t.config_id, t.failure_category AS category, COUNT(*) AS n
                FROM trials t JOIN configs c ON c.id = t.config_id
                WHERE t.experiment_id = ? AND t.status = 'done' AND t.failure_category IS NOT NULL
                GROUP BY t.config_id, t.failure_category ORDER BY n DESC`)
      .all(id);
  }

  /** Give finally-invalid trials another round (e.g. the next day, after a daily quota reset). */
  retryInvalid(id: number) {
    this.get(id);
    const r = this.db.db
      .prepare(`UPDATE trials SET status = 'pending', attempts = 0, not_before = 0 WHERE experiment_id = ? AND status = 'invalid'`)
      .run(id);
    this.db.db.prepare(`UPDATE experiments SET status = 'running' WHERE id = ?`).run(id);
    return { requeued: r.changes };
  }

  trial(trialId: number) {
    const t: any = this.db.db
      .prepare(`SELECT t.*, c.name AS config_name, c.json AS config_json FROM trials t JOIN configs c ON c.id = t.config_id WHERE t.id = ?`)
      .get(trialId);
    if (!t) throw new NotFoundException(`trial ${trialId} not found`);
    const events = this.db.db.prepare(`SELECT seq, session, type, ts, payload_json FROM events WHERE trial_id = ? ORDER BY seq`).all(trialId) as any[];
    const grades = this.db.db.prepare(`SELECT grader, score, passed, reasoning FROM grades WHERE trial_id = ?`).all(trialId);
    return {
      ...t,
      config_json: JSON.parse(t.config_json),
      events: events.map(({ payload_json, ...ev }) => ({ ...ev, payload: JSON.parse(payload_json) })),
      grades,
    };
  }

  exportJson(id: number) {
    return { experiment: this.get(id), comparison: this.compare(id), trials: this.trials(id) };
  }

  exportCsv(id: number): string {
    const rows = this.trials(id) as any[];
    const cols = ['id', 'task_id', 'config_name', 'config_id', 'trial_index', 'status', 'score', 'passed', 'failure_category', 'input_tokens',
      'output_tokens', 'cost_usd', 'ref_cost_usd', 'latency_ms', 'attempts', 'error', 'harness_version', 'isolation', 'task_hash', 'code_version'];
    const cell = (v: unknown) => {
      const s = v === null || v === undefined ? '' : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    return [cols.join(','), ...rows.map((r) => cols.map((c) => cell(r[c])).join(','))].join('\n') + '\n';
  }
}
