import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { readFileSync } from 'fs';
import { join } from 'path';
import { DbService } from './db.service';
import { PRICES_PATH, REPO } from './paths';
import { RunnerService } from './runner.service';

/** Invalid (infrastructure) failures are retried this many times in total, with a growing wait. */
export const MAX_ATTEMPTS = Number(process.env.MAX_ATTEMPTS ?? 3);
const RETRY_BASE_MS = Number(process.env.RETRY_BASE_MS ?? 60_000); // free-tier quotas reset per minute
const TOTAL_SLOTS = Number(process.env.MAX_WORKERS ?? 4);

/**
 * Parallel trials per provider. Each provider has its own rate limit, so each gets its own lane:
 * local Ollama runs one at a time (one GPU), Gemini one (a Hermes trial can use most of a minute's tokens).
 */
const LANE_LIMITS: Record<string, number> = {
  mock: 4,
  'localhost:11434': 1,
  'generativelanguage.googleapis.com': 1,
  'api.groq.com': 2,
  ...JSON.parse(process.env.LANE_LIMITS ?? '{}'),
};

export function laneOf(config: any): string {
  if (config.harness === 'mock') return 'mock';
  try {
    return new URL(config.model.base_url).host;
  } catch {
    return 'default';
  }
}

/** Same account-ID patterns as runner/evalrunner/isolation.py: never store or export provider account IDs. */
export function scrubIds(text: string): string {
  return text
    .replace(/\borg_[A-Za-z0-9]{8,}/g, 'org_[REDACTED]')
    .replace(/\bprojects\/\d{6,}/g, 'projects/[REDACTED]')
    .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '[REDACTED_EMAIL]');
}

interface Prices { actual: Record<string, { input: number; output: number }>; reference: { input: number; output: number } }

@Injectable()
export class SchedulerService implements OnModuleInit, OnModuleDestroy {
  private readonly log = new Logger('Scheduler');
  private timer?: NodeJS.Timeout;
  private readonly running = new Map<number, string>(); // trial id -> lane
  private prices: Prices = JSON.parse(readFileSync(PRICES_PATH, 'utf8'));

  constructor(private readonly db: DbService, private readonly runner: RunnerService) {}

  onModuleInit() {
    if (process.env.SCHEDULER !== 'off') this.timer = setInterval(() => this.tick(), 500);
  }

  onModuleDestroy() {
    if (this.timer) clearInterval(this.timer);
  }

  get busy(): number {
    return this.running.size;
  }

  /** Start as many pending trials as the lanes allow. Called every 500 ms. */
  tick(): void {
    if (this.running.size >= TOTAL_SLOTS) return;
    const pending = this.db.db
      .prepare(
        `SELECT t.id, t.task_id, t.trial_index, c.json AS config_json
         FROM trials t JOIN configs c ON c.id = t.config_id
         WHERE t.status = 'pending' AND t.not_before <= ? ORDER BY t.trial_index, t.id LIMIT 200`,
      )
      .all(Date.now()) as { id: number; task_id: string; trial_index: number; config_json: string }[];

    for (const t of pending) {
      if (this.running.size >= TOTAL_SLOTS) break;
      const config = JSON.parse(t.config_json);
      const lane = laneOf(config);
      const inLane = [...this.running.values()].filter((l) => l === lane).length;
      if (inLane >= (LANE_LIMITS[lane] ?? 2)) continue;
      this.running.set(t.id, lane);
      this.db.db
        .prepare(`UPDATE trials SET status = 'running', attempts = attempts + 1, started_at = ? WHERE id = ?`)
        .run(new Date().toISOString(), t.id);
      this.execute(t.id, t.task_id, t.trial_index, config).finally(() => this.running.delete(t.id));
    }
  }

  private async execute(id: number, taskId: string, trialIndex: number, config: any) {
    const timeoutMs = ((config.settings?.timeout_s ?? 180) + 180) * 1000; // agent budget + grading + startup
    let result: any;
    try {
      result = await this.runner.runTrial(
        { task_dir: join(REPO, 'tasks', taskId), config, trial_index: trialIndex },
        timeoutMs,
      );
    } catch (e: any) {
      result = { status: 'invalid', error: scrubIds(`runner failed: ${String(e.message ?? e).slice(0, 1000)}`) };
    }
    this.save(id, result, config);
  }

  /** Save one result atomically: the trial row, its events and its grades, or nothing. */
  save(id: number, r: any, config: any) {
    const db = this.db.db;
    const tx = db.transaction(() => {
      db.prepare(`DELETE FROM events WHERE trial_id = ?`).run(id);
      db.prepare(`DELETE FROM grades WHERE trial_id = ?`).run(id);
      if (r.status !== 'done') {
        const { attempts } = db.prepare(`SELECT attempts FROM trials WHERE id = ?`).get(id) as { attempts: number };
        const retry = attempts < MAX_ATTEMPTS;
        db.prepare(
          `UPDATE trials SET status = ?, error = ?, not_before = ?, finished_at = ?, score = NULL, passed = NULL WHERE id = ?`,
        ).run(retry ? 'pending' : 'invalid', scrubIds(String(r.error ?? 'unknown error')), Date.now() + RETRY_BASE_MS * attempts,
          new Date().toISOString(), id);
        this.log.warn(`trial ${id} invalid (attempt ${attempts}/${MAX_ATTEMPTS}${retry ? ', will retry' : ''}): ${scrubIds(String(r.error)).slice(0, 160)}`);
        return;
      }
      const inTok = r.usage?.input_tokens ?? 0;
      const outTok = r.usage?.output_tokens ?? 0;
      const actual = this.prices.actual[config.model?.id] ?? this.prices.actual.default;
      const cost = (inTok * actual.input + outTok * actual.output) / 1e6;
      const ref = (inTok * this.prices.reference.input + outTok * this.prices.reference.output) / 1e6;
      db.prepare(
        `UPDATE trials SET status = 'done', score = ?, passed = ?, input_tokens = ?, output_tokens = ?, cost_usd = ?,
         ref_cost_usd = ?, latency_ms = ?, error = NULL, harness_version = ?, isolation = ?, task_hash = ?, code_version = ?, finished_at = ?,
         failure_category = ?, failure_signals = ?
         WHERE id = ?`,
      ).run(r.score, r.passed ? 1 : 0, inTok, outTok, cost, ref, r.latency_ms, r.harness_version, r.isolation,
        r.task_hash, r.code_version ?? null, new Date().toISOString(), r.failure?.category ?? null,
        JSON.stringify(r.failure?.signals ?? []), id);
      const ev = db.prepare(`INSERT INTO events (trial_id, seq, session, type, ts, payload_json) VALUES (?, ?, ?, ?, ?, ?)`);
      for (const e of r.trace ?? []) ev.run(id, e.seq, e.session, e.type, e.ts, JSON.stringify(e.payload));
      const gr = db.prepare(`INSERT INTO grades (trial_id, grader, score, passed, reasoning) VALUES (?, ?, ?, ?, ?)`);
      for (const g of r.grades ?? []) gr.run(id, g.grader, g.score, g.passed ? 1 : 0, g.reasoning);
    });
    tx();
  }
}
