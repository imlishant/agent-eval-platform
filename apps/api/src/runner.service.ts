import { Injectable } from '@nestjs/common';
import { execFile } from 'child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { promisify } from 'util';
import { REPO, RUNNER_DIR, RUNNER_PYTHON } from './paths';

const run = promisify(execFile);

export interface CatalogConfig { file: string; name: string; id: string; config: any }
export interface CatalogTask { id: string; category: string; hash: string; sessions: number; graders: string[] }
export interface Catalog { configs: CatalogConfig[]; tasks: CatalogTask[] }

/** The only bridge to Python: spawn the runner, read one JSON object from stdout. */
@Injectable()
export class RunnerService {
  async catalog(): Promise<Catalog> {
    const { stdout } = await run(RUNNER_PYTHON, ['-m', 'evalrunner.catalog'], { cwd: RUNNER_DIR, maxBuffer: 20e6 });
    return JSON.parse(stdout);
  }

  async codeSha(): Promise<string> {
    try {
      const { stdout } = await run('git', ['rev-parse', '--short', 'HEAD'], { cwd: REPO });
      const { stdout: dirty } = await run('git', ['status', '--porcelain'], { cwd: REPO });
      return stdout.trim() + (dirty.trim() ? '-dirty' : '');
    } catch {
      return process.env.CODE_SHA ?? 'unknown';
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
