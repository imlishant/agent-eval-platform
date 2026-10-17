import { Injectable } from '@nestjs/common';
import { execFile, spawn } from 'child_process';
import { createHash } from 'crypto';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { promisify } from 'util';
import { REPO, RUNNER_DIR, RUNNER_PYTHON } from './paths';

const run = promisify(execFile);

export interface CatalogConfig { file: string; name: string; id: string; config: any }
export interface CatalogTask { id: string; category: string; hash: string; sessions: number; graders: string[] }
export interface ModelEntry { name: string; label: string; provider: string; id: string; base_url: string | null; api_key_env: string | null; notes?: string }
export interface HarnessEntry { id: string; description: string; settings: string[]; requirements: string }
export interface Catalog {
  configs: CatalogConfig[]; tasks: CatalogTask[]; skills: { name: string; description: string }[];
  harnesses: HarnessEntry[]; models: ModelEntry[];
}
/** What the UI sends for one side of an experiment: a harness, a model from the registry, and settings. */
export interface ConfigDraft { harness: string; model: string; settings?: Record<string, unknown> }

const MODELS_FILE = join(REPO, 'configs', 'models.json');

/** Run a runner module with JSON on stdin; resolve with parsed stdout, reject with its error text. */
function runPy(module: string, input: unknown, timeoutMs = 60_000): Promise<any> {
  return new Promise((resolve, reject) => {
    const p = spawn(RUNNER_PYTHON, ['-m', module], { cwd: RUNNER_DIR, env: process.env });
    let out = '';
    let err = '';
    const timer = setTimeout(() => p.kill(), timeoutMs);
    p.stdout.on('data', (d) => (out += d));
    p.stderr.on('data', (d) => (err += d));
    p.on('close', (code) => {
      clearTimeout(timer);
      if (code === 0) resolve(JSON.parse(out));
      else reject(new Error((err.trim().split('\n').pop() ?? '').slice(0, 400) || `exit ${code}`));
    });
    p.stdin.end(JSON.stringify(input));
  });
}

/** The only bridge to Python: spawn the runner, read one JSON object from stdout. */
@Injectable()
export class RunnerService {
  async catalog(): Promise<Catalog> {
    const { stdout } = await run(RUNNER_PYTHON, ['-m', 'evalrunner.catalog'], { cwd: RUNNER_DIR, maxBuffer: 20e6 });
    return JSON.parse(stdout);
  }

  /**
   * Save a new config as configs/<name>.json (git then versions it). The Python runner validates it
   * and computes its content-hash ID; an invalid config is removed again.
   */
  async createConfig(body: { name?: string; harness?: string; model?: any; settings?: any }): Promise<CatalogConfig> {
    const name = String(body.name ?? '');
    if (!/^[a-z0-9][a-z0-9.-]{2,60}$/.test(name)) {
      throw new Error('name: 3-61 characters, lowercase letters, digits, "." and "-"');
    }
    const file = join(REPO, 'configs', `${name}.json`);
    if (existsSync(file) || name === 'judge' || name === 'prices') throw new Error(`a config named "${name}" already exists`);
    const config = { name, harness: body.harness, model: body.model, settings: body.settings ?? {} };
    writeFileSync(file, JSON.stringify(config, null, 2) + '\n');
    try {
      const entry = (await this.catalog()).configs.find((c) => c.file === `${name}.json`);
      if (!entry) throw new Error('config could not be read back');
      return entry;
    } catch (e: any) {
      rmSync(file, { force: true });
      throw new Error(`invalid config: ${String(e.stderr || e.message).trim().split('\n').pop()}`);
    }
  }

  /** Same format as runner/evalrunner/version.py, so experiment and trial versions can be compared. */
  /**
   * Turn a draft (harness + registry model + settings) into a saved config. If a config with the same
   * content already exists it is reused (same content = same ID); otherwise a new file is written.
   */
  async resolveDraft(draft: ConfigDraft): Promise<CatalogConfig> {
    const cat = await this.catalog();
    const model = cat.models.find((m) => m.name === draft.model);
    if (!model) throw new Error(`unknown model "${draft.model}"`);
    if (!cat.harnesses.some((h) => h.id === draft.harness)) throw new Error(`unknown harness "${draft.harness}"`);
    const { name: modelName, label: _l, notes: _n, ...spec } = model;
    const name = `${draft.harness}-${modelName}`;
    const { id, config } = await runPy('evalrunner.config_tool', { name, harness: draft.harness, model: spec, settings: draft.settings ?? {} });
    const existing = cat.configs.find((c) => c.id === id);
    if (existing) return existing;
    const fileName = `${name}-${id.slice(0, 6)}`;
    config.name = fileName;
    writeFileSync(join(REPO, 'configs', `${fileName}.json`), JSON.stringify(config, null, 2) + '\n');
    return { file: `${fileName}.json`, name: fileName, id, config };
  }

  /** Add a model to configs/models.json (any OpenAI-compatible endpoint). */
  addModel(body: Partial<ModelEntry>): ModelEntry {
    const models: ModelEntry[] = JSON.parse(readFileSync(MODELS_FILE, 'utf8'));
    const name = String(body.name ?? '');
    if (!/^[a-z0-9][a-z0-9.-]{2,60}$/.test(name)) throw new Error('name: 3-61 characters, lowercase letters, digits, "." and "-"');
    if (models.some((m) => m.name === name)) throw new Error(`a model named "${name}" already exists`);
    if (!body.id) throw new Error('model id is required (the name the provider uses)');
    try {
      new URL(String(body.base_url));
    } catch {
      throw new Error('base URL must be a full URL, e.g. https://api.example.com/v1');
    }
    const keyEnv = body.api_key_env ? String(body.api_key_env) : null;
    if (keyEnv && !/^[A-Z][A-Z0-9_]{2,60}$/.test(keyEnv)) throw new Error('key variable: the NAME of an env var in .env, e.g. MY_PROVIDER_KEY (never the key itself)');
    const entry: ModelEntry = { name, label: body.label || name, provider: 'openai_compat', id: String(body.id),
      base_url: String(body.base_url), api_key_env: keyEnv, notes: body.notes ?? '' };
    models.splice(models.length - 1, 0, entry); // keep "none" last
    writeFileSync(MODELS_FILE, JSON.stringify(models, null, 2) + '\n');
    return entry;
  }

  /** One real request with a tool, to check URL, key and tool-calling support. */
  checkModel(spec: { provider?: string; id: string; base_url: string | null; api_key_env: string | null }) {
    return runPy('evalrunner.check_model', { provider: spec.provider ?? 'openai_compat', id: spec.id,
      base_url: spec.base_url, api_key_env: spec.api_key_env || null }, 90_000);
  }

  async codeSha(): Promise<string> {
    if (process.env.CODE_SHA) return process.env.CODE_SHA;
    try {
      const git = async (...args: string[]) => (await run('git', args, { cwd: REPO, maxBuffer: 50e6 })).stdout;
      const sha = (await git('rev-parse', '--short', 'HEAD')).trim();
      const status = await git('status', '--porcelain');
      if (!status.trim()) return sha;
      const diff = await git('diff', 'HEAD');
      return `${sha}-dirty.${createHash('sha256').update(status + diff).digest('hex').slice(0, 8)}`;
    } catch {
      return 'unknown';
    }
  }

  /** Run one trial. Throws only if the runner process itself failed (treated as invalid by the caller). */
  async runTrial(spec: { task_dir: string; config: any; trial_index: number }, timeoutMs: number): Promise<any> {
    const dir = mkdtempSync(join(tmpdir(), 'spec-'));
    const file = join(dir, 'trial.json');
    writeFileSync(file, JSON.stringify(spec));
    try {
      const { stdout } = await run(RUNNER_PYTHON, ['-m', 'evalrunner.run_trial', file], {
        cwd: RUNNER_DIR,
        timeout: timeoutMs,
        maxBuffer: 50e6,
        env: process.env,
      });
      return JSON.parse(stdout);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  }
}
