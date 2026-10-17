import { join, resolve } from 'path';

/** Where things live. Every path can be overridden by an environment variable (used by Docker and tests). */
export const REPO = resolve(process.env.REPO_ROOT ?? join(__dirname, '..', '..', '..'));
export const RUNNER_DIR = join(REPO, 'runner');
export const RUNNER_PYTHON = process.env.RUNNER_PYTHON ?? join(RUNNER_DIR, '.venv', 'bin', 'python');
export const DB_PATH = process.env.DB_PATH ?? join(REPO, 'data', 'evals.db');
export const PRICES_PATH = join(REPO, 'configs', 'prices.json');
export const WEB_DIST = process.env.WEB_DIST ?? join(REPO, 'apps', 'web', 'dist');
