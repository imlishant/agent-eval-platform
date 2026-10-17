/** Thin typed wrapper over the API. Errors carry the server's message so the UI can show it. */

export interface ConfigEntry { file: string; name: string; id: string; config: any }
export interface TaskEntry { id: string; category: string; hash: string; sessions: number; graders: string[] }
export interface ModelEntry { name: string; label: string; provider: string; id: string; base_url: string | null; api_key_env: string | null; notes?: string }
export interface HarnessEntry { id: string; description: string; settings: string[]; requirements: string }
export interface Catalog {
  configs: ConfigEntry[]; tasks: TaskEntry[]; skills: { name: string; description: string }[];
  harnesses: HarnessEntry[]; models: ModelEntry[];
}
/** One side of an experiment as built in the UI: harness x model x settings. */
export interface Draft {
  harness: string; model: string;
  settings: { memory: string; skills: string[]; temperature: number; max_steps: number; max_tokens: number; timeout_s: number;
    extra: { behavior: string } };
}
export const newDraft = (harness: string, model: string): Draft => ({
  harness, model,
  settings: { memory: 'off', skills: [], temperature: 0.7, max_steps: 15, max_tokens: 2000,
    timeout_s: 300, extra: { behavior: 'solve' } }, // same budget for every harness: one axis at a time
});
export interface ModelCheck { ok: boolean; latency_ms: number; tool_calling: boolean; message: string }
export interface Progress { total: number; pending: number; running: number; done: number; invalid: number }

export interface TaskDelta { task_id: string; n_pairs: number; mean_a: number; mean_b: number; delta: number; sd_a: number; sd_b: number }
export interface Comparison {
  n_tasks: number; mean_a: number; mean_b: number; mean_delta: number; ci_low: number; ci_high: number;
  verdict: 'B better' | 'B worse' | 'no detectable difference' | 'too few tasks'; message: string; mde: number;
  tasks_better: number; tasks_worse: number; tasks_same: number; within_task_sd: number; between_task_sd: number;
  dropped_pairs: number; tasks: TaskDelta[];
}
export interface CompareResponse {
  experiment: { id: number; name: string; hypothesis: string; status: string; n_trials: number; code_sha: string;
    config_a: { id: string; name: string }; config_b: { id: string; name: string } };
  progress: Progress; complete: boolean;
  metrics: Record<'score' | 'cost_usd' | 'ref_cost_usd' | 'total_tokens' | 'latency_s', Comparison>;
  totals: { config: string; config_id: string; trials: number; invalid: number; mean_score: number | null;
    input_tokens: number | null; output_tokens: number | null; cost_usd: number | null; ref_cost_usd: number | null;
    mean_latency_ms: number | null }[];
  failures: { config: string; config_id: string; category: string; n: number }[];
  code_mismatch: number;
}
export interface TrialRow {
  id: number; task_id: string; config_id: string; config_name: string; trial_index: number; status: string;
  score: number | null; passed: number | null; error: string | null; attempts: number; failure_category?: string | null;
}
export interface TrialEvent { seq: number; session: number; type: string; ts: number; payload: any }
export interface Trial extends TrialRow {
  experiment_id: number; input_tokens: number | null; output_tokens: number | null; latency_ms: number | null;
  cost_usd: number | null; ref_cost_usd: number | null; harness_version: string | null; isolation: string | null;
  failure_signals: string | null; config_json: any; events: TrialEvent[]; grades: { grader: string; score: number; passed: number; reasoning: string }[];
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { headers: { 'Content-Type': 'application/json' }, ...init });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(Array.isArray(body.message) ? body.message.join('; ') : body.message ?? res.statusText);
  return body as T;
}

export const api = {
  catalog: () => call<Catalog>('/catalog'),
  experiments: () => call<any[]>('/experiments'),
  experiment: (id: number) => call<any>(`/experiments/${id}`),
  trials: (id: number) => call<TrialRow[]>(`/experiments/${id}/trials`),
  compare: (id: number) => call<CompareResponse>(`/experiments/${id}/compare`),
  trial: (id: number) => call<Trial>(`/trials/${id}`),
  createExperiment: (body: any) => call<any>('/experiments', { method: 'POST', body: JSON.stringify(body) }),
  createConfig: (body: any) => call<ConfigEntry>('/configs', { method: 'POST', body: JSON.stringify(body) }),
  addModel: (body: any) => call<ModelEntry>('/models', { method: 'POST', body: JSON.stringify(body) }),
  checkModel: (body: any) => call<ModelCheck>('/models/check', { method: 'POST', body: JSON.stringify(body) }),
  retryInvalid: (id: number) => call<{ requeued: number }>(`/experiments/${id}/retry-invalid`, { method: 'POST' }),
};

/** Failure categories (runner/evalrunner/failures.py), in the order the rules are checked. */
export const FAILURES: Record<string, string> = {
  timeout: 'Hit the time limit',
  step_exhaustion: 'Used all its steps without finishing',
  loop: 'Repeated the same tool call 3+ times',
  bad_tool_args: 'Called a tool with invalid or missing arguments',
  wrong_tool: 'Called a tool that does not exist',
  grader_disagreement: 'Graders disagree (one passes, one fails)',
  gave_up_early: 'Answered without using any tool, or gave no answer',
  wrong_answer: 'Finished normally, but the result is wrong',
};

export const fmt = {
  num: (x: number | null | undefined, d = 2) => (x === null || x === undefined ? '–' : x.toFixed(d)),
  signed: (x: number, d = 2) => (x > 0 ? '+' : x < 0 ? '−' : '±') + Math.abs(x).toFixed(d),
  usd: (x: number | null | undefined) => (x === null || x === undefined ? '–' : x < 0.01 && x > 0 ? `$${x.toFixed(4)}` : `$${x.toFixed(2)}`),
  int: (x: number | null | undefined) => (x === null || x === undefined ? '–' : Math.round(x).toLocaleString()),
};
