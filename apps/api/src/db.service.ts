import { Injectable, OnModuleDestroy } from '@nestjs/common';
import Database from 'better-sqlite3';
import { mkdirSync } from 'fs';
import { dirname } from 'path';
import { DB_PATH } from './paths';

/** SQLite file. Schema = PLAN §5: configs, experiments, trials, events, grades. */
const SCHEMA = `
CREATE TABLE IF NOT EXISTS configs (
  id TEXT PRIMARY KEY,            -- hash of the config content (computed by the Python runner)
  name TEXT NOT NULL,
  json TEXT NOT NULL,             -- full config snapshot, so old results stay reproducible
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  hypothesis TEXT NOT NULL DEFAULT '',
  config_a TEXT NOT NULL REFERENCES configs(id),
  config_b TEXT NOT NULL REFERENCES configs(id),
  task_ids TEXT NOT NULL,         -- JSON list
  task_hashes TEXT NOT NULL,      -- JSON {task_id: content hash at creation}
  n_trials INTEGER NOT NULL,
  code_sha TEXT NOT NULL,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL            -- running | done
);
CREATE TABLE IF NOT EXISTS trials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  experiment_id INTEGER NOT NULL REFERENCES experiments(id),
  task_id TEXT NOT NULL,
  config_id TEXT NOT NULL,
  trial_index INTEGER NOT NULL,
  status TEXT NOT NULL,           -- pending | running | done | invalid
  score REAL, passed INTEGER,
  input_tokens INTEGER, output_tokens INTEGER,
  cost_usd REAL, ref_cost_usd REAL, latency_ms INTEGER,
  attempts INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  not_before INTEGER NOT NULL DEFAULT 0,   -- epoch ms; retry backoff for invalid trials
  harness_version TEXT, isolation TEXT, task_hash TEXT,
  started_at TEXT, finished_at TEXT,
  UNIQUE (experiment_id, task_id, config_id, trial_index)
);
CREATE TABLE IF NOT EXISTS events (
  trial_id INTEGER NOT NULL REFERENCES trials(id),
  seq INTEGER NOT NULL, session INTEGER NOT NULL, type TEXT NOT NULL, ts REAL NOT NULL,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (trial_id, seq)
);
CREATE TABLE IF NOT EXISTS grades (
  trial_id INTEGER NOT NULL REFERENCES trials(id),
  grader TEXT NOT NULL, score REAL NOT NULL, passed INTEGER NOT NULL, reasoning TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS trials_by_status ON trials(status, not_before);
CREATE INDEX IF NOT EXISTS trials_by_experiment ON trials(experiment_id);
`;

@Injectable()
export class DbService implements OnModuleDestroy {
  readonly db: Database.Database;

  constructor() {
    if (DB_PATH !== ':memory:') mkdirSync(dirname(DB_PATH), { recursive: true });
    this.db = new Database(DB_PATH);
    this.db.pragma('journal_mode = WAL'); // readers (UI) never block the writer (scheduler)
    this.db.pragma('foreign_keys = ON');
    this.db.exec(SCHEMA);
    // additive migrations for databases created by earlier versions
    const cols = (this.db.prepare(`PRAGMA table_info(trials)`).all() as { name: string }[]).map((c) => c.name);
    if (!cols.includes('failure_category')) this.db.exec(`ALTER TABLE trials ADD COLUMN failure_category TEXT`);
    if (!cols.includes('failure_signals')) this.db.exec(`ALTER TABLE trials ADD COLUMN failure_signals TEXT`);
    if (!cols.includes('code_version')) this.db.exec(`ALTER TABLE trials ADD COLUMN code_version TEXT`);
    // A restart while trials were running: put them back in the queue (results are saved atomically,
    // so a running trial has written nothing yet).
    this.db.prepare(`UPDATE trials SET status = 'pending' WHERE status = 'running'`).run();
  }

  onModuleDestroy() {
    this.db.close();
  }
}
