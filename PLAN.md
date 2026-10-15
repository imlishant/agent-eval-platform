# Agent Evals Platform — Implementation Plan

Context for the IDE agent: this file is the agreed plan from a planning chat. Follow it. Keep everything simple, because the author must explain every part on a live call and change things on request. Time box: 4 hours.

## 1. The assignment in one paragraph

Build a platform that evaluates an AI agent = harness (loop, tools, skills, memory, prompts) + model, and answers: when we change the harness or model, did the agent get better, worse, or stay the same, and how sure are we? Stack: NestJS API, Vue 3 + TypeScript UI, Python allowed for harness workers. Must run with `docker compose up`, API keys in `.env`. Graded on: eval method and honest statistics first, clean adapters second, then trace detail, reliability, and stated assumptions/limits.

Required pieces:
- Harnesses: Hermes Agent (Nous Research, required) + one more (we write a minimal baseline loop).
- Models: reached through a common interface. Adding a harness or model = writing an adapter, no core changes.
- Graders: deterministic (exact match, unit tests, file/state checks) + LLM-as-judge with rubric. Judge must be validated against human labels.
- Configs: harness × model × settings (skills, memory, tools, temperature, step/token budgets), versioned.
- Execution: every task × every config × N trials, isolated, with timeouts, retries, partial-failure handling.
- Comparison: CIs + paired test, per-task deltas, clear "this is noise" message, cost/latency/tokens next to quality.
- Trial inspection: full trajectory (messages, tool calls, memory reads/writes, skills used, grader reasoning, score).
- Failure analysis: stretch goal.
- 20+ tasks with mixed graders, some that separate configs (skill/memory helps).
- Results persisted, exportable as JSON/CSV.
- Deliverables: repo + README (setup, add task, add harness, add model), design doc, known limits, cost formula + actual spend, one real experiment, video ≤10 min.

## 2. Key decisions

- **API key:** Anthropic API key from console.anthropic.com (billed separately from Claude Pro). Expected spend $2–5.
- **Models:** model is a config value. Use `claude-haiku-5-5` and `claude-sonnet-5-5`. Second provider (OpenRouter open-weight model) only if time allows; otherwise document "one config entry to add".
- **Docker:** develop natively. Write Dockerfile + compose in the last 20 minutes and test once from a clean clone.
- **No Redis, no Postgres, no LiteLLM proxy.** SQLite file + API-managed subprocess pool.
- **Configs are JSON files in the repo.** Config ID = hash of file content. Git provides version history.
- **Tasks are files in the repo** (one folder per task).
- **One statistical method:** paired bootstrap over tasks.
- **N = 3 trials** (time box); explain the reasoning in the design doc.

## 3. Architecture

```
Vue UI  →  NestJS API  →  SQLite file
                │
                └── spawns: python runner/run_trial.py <trial.json>
                     1. create temp dir (sandbox) + own HOME, copy task files
                     2. run harness adapter (baseline or Hermes) with the chosen model
                     3. run graders
                     4. print {trace, grades, usage} as JSON on stdout
                   API parses JSON and saves it in one transaction
```

- API runs up to 4 subprocesses at once.
- Retry: provider errors (429, 5xx, network) retried 3 times with backoff. Still failing → trial status `invalid`, excluded from the comparison, count shown in UI.
- Agent timeout / step limit / wrong answer → real result, score 0, reason saved.
- Docker: one container (Node + Python), serves API and built UI, one volume for SQLite.

### Repo layout
```
apps/api        NestJS
apps/web        Vue 3 + TS
runner/         Python: run_trial.py, harnesses/, graders/, sandbox.py
tasks/<id>/     task.yaml, fixtures/, tests/, reference/ (solution)
configs/        *.json
judge_validation/  labels.json + validate_judge.py
docs/           DESIGN.md, LIMITS.md, EXPERIMENT.md
docker-compose.yml, Dockerfile, .env.example, README.md
```

## 4. Interfaces

### Harness adapter (Python)
```python
class HarnessAdapter:
    id: str
    version: str
    def run_trial(self, ctx: TrialContext) -> Trace:  # must not raise on agent failure
        ...
# TrialContext: sessions[list of prompts], sandbox_dir, home_dir,
#   model {provider, id}, settings {skills[], memory: "off"|"on",
#   tools[], temperature, max_steps, max_tokens, timeout_s}
```
Register adapters by id in a dict. New harness = new class + one dict entry.

Harnesses:
- `mock` — scripted trace, no API calls (for free pipeline testing).
- `baseline` — plain tool-calling loop with Anthropic SDK. Tools: bash, read_file, write_file. Skills = markdown text added to system prompt. Memory = `memory.md` in home_dir + `memory_write` tool, loaded into prompt at session start.
- `hermes` — run Hermes headless with HOME/Hermes dir pointed at the trial's home_dir. Copy chosen skills into its skills folder; memory "off" = empty memory files and memory disabled. Detect memory writes by comparing memory files before/after each session. Reset everything per trial (Hermes can edit its own skills).

### Trace event (shared schema)
```json
{"seq": 3, "session": 1, "type": "tool_call", "ts": 1729000000.1,
 "payload": {"name": "bash", "args": {"cmd": "pytest"}}}
```
Types: `message`, `model_call` (tokens, latency), `tool_call`, `tool_result`, `memory_read`, `memory_write`, `skill_used`, `error`, `final_answer`.

### Config file
```json
{"name": "baseline-haiku", "harness": "baseline",
 "model": {"provider": "anthropic", "id": "claude-haiku-5-5"},
 "settings": {"skills": [], "memory": "off", "tools": ["bash","read_file","write_file"],
              "temperature": 0.7, "max_steps": 20, "max_tokens": 4000, "timeout_s": 180}}
```

### Task file (task.yaml)
```yaml
id: fix-failing-test
category: code            # code | exact | skill | memory | judge
sessions:
  - "The tests in tests/ fail. Fix src/calc.py so they pass."
graders:
  - type: unit_tests       # exact_match | file_check | unit_tests | llm_judge
    command: "pytest -q tests"
```
Memory tasks have 2 sessions (session 1 gives a fact, session 2 needs it). Judge tasks have a `rubric` list of yes/no criteria.

## 5. Data model (SQLite, 4 tables)
- `experiments`: id, config_a, config_b, task_ids, n_trials, code_sha, created_at, status
- `trials`: id, experiment_id, task_id, config_id, trial_index, status (pending/running/done/invalid), score, input_tokens, output_tokens, cost_usd, latency_ms, attempts, error
- `events`: trial_id, seq, session, type, payload_json
- `grades`: trial_id, grader, score, passed, reasoning

## 6. Graders
- Deterministic: exact_match, file_check (file exists, contains/regex/JSON fields), unit_tests (run command in sandbox, pass = exit 0).
- Each deterministic task has a reference solution (must score 1) and an empty run (must score 0). Run both in pytest. This proves graders work.
- LLM judge: rubric of yes/no criteria, score = share met, temperature 0, returns reasoning per criterion. Use a different model than the one being tested where possible.
- Judge validation: 12–15 outputs labelled pass/fail by hand in `judge_validation/labels.json`. Script reports accuracy and Cohen's kappa. If kappa < 0.6, mark judge tasks "low trust".

## 7. Task set (20)
| Group | Count | Grader |
|---|---|---|
| File/code (fix test, write file with fields, CSV transform) | 8 | unit_tests / file_check |
| Exact-answer tool tasks | 3 | exact_match |
| Skill-sensitive (skill describes house format or fake internal CLI) | 3 | file_check |
| Memory-sensitive (2 sessions) | 3 | file_check |
| Judge-graded (summary, README, policy reply) | 3 | llm_judge |

## 8. Statistics (paired bootstrap)
1. Per task and config: mean score over N trials.
2. Per task: `delta = mean_B − mean_A`. Show every delta.
3. Mean delta over tasks. CI: resample tasks with replacement 10,000 times, recompute mean delta, take 2.5th and 97.5th percentiles.
4. If CI contains 0 → UI shows "No detectable difference (could be noise)". Also show minimum detectable effect ≈ 2 × CI half-width.
5. Same treatment for cost, tokens, latency.
6. Invalid trials: drop that task-trial pair from both configs; show count.
7. Why N=3: variation between tasks is usually larger than between repeated runs, so more tasks help more than more trials. A pilot would measure both; N=3 chosen for time.
8. Unit test: hand-computed small example; and a no-difference simulation where the CI contains 0 most of the time.

## 9. UI (3 pages)
- Run: pick config A, config B, task set, N → start; progress bar.
- Compare: overall delta + CI + verdict, per-task delta table, cost/latency/tokens, invalid count, export JSON/CSV buttons.
- Trial: event timeline (messages, tool calls/results, memory, skills), grades with reasoning, score.

## 10. Failure analysis (stretch, rule-based from trace)
- step limit hit → `step_exhaustion`
- tool error from bad args → `bad_tool_args`
- final answer early + failed grade → `gave_up_early`
- same tool call repeated 3+ times → `loop`

## 11. Experiment
- Primary: baseline harness, `claude-haiku-5-5` vs `claude-sonnet-5-5`. 20 tasks × 3 trials × 2 configs = 120 trials.
- Stretch: Hermes memory on vs off (only if Hermes works by the 1:45 mark).
- Write hypothesis before running. Report CI, per-task deltas, 2–3 inspected trajectories, conclusion.
- Cost formula: `tasks × trials × configs × avg tokens per trial × price per token` (input and output separately) + actual spend from console. Reduce cost by: caching identical model calls, stopping early when CI excludes 0, screening on a task subset.

## 12. Schedule (4 hours)
| Time | Work | Checkpoint |
|---|---|---|
| 0:00–0:30 | Repo, SQLite, Hermes spike | Hermes answers one prompt from a script |
| 0:30–1:15 | Runner: sandbox, mock + baseline harness, trace, deterministic graders | 1 task graded end to end |
| 1:15–1:45 | Hermes adapter | Decide Hermes in experiment or not |
| 1:45–2:15 | 20 tasks + grader tests, judge + labels | Graders pass tests |
| 2:15–2:50 | API: experiments, subprocess pool, retries, stats, export | Compare via API |
| 2:50–3:25 | UI: run, compare, trial viewer | Click failed trial, see trace |
| 3:25–3:45 | Run experiment, pick trajectories | Results saved |
| 3:45–4:00 | Docker, README, short DESIGN.md | `docker compose up` works from clean clone |

Cut order if behind: failure analysis → Hermes in experiment → judge tasks to 2 → config dropdown (use CLI flag).

## 13. Build order for the IDE
1. Shared schemas (trace event, config, task).
2. Runner + sandbox + mock harness.
3. Baseline harness.
4. Graders + tasks + grader tests.
5. Hermes adapter.
6. API + stats (+ tests).
7. UI.
8. Docker.

## 14. Assumptions and known limits (for LIMITS.md)
- Hermes runs headless and accepts the Anthropic provider (verify in spike).
- Skills and memory work differently in Hermes and baseline, so cross-harness comparisons include that difference.
- 20 tasks only detect large differences.
- One provider used; second provider is a config entry.
- Tasks and judge labels written by the author; judge validated on a small set.
- Possible training-data contamination; tasks are custom to reduce it.
- Temp-dir isolation, not containers per trial.
- Hermes can edit its own skills; skills and memory reset per trial.

## 15. One-line answers for the call
- Harness adapter: one Python class with `run_trial()` returning the standard trace.
- Model adapter: model is a config value; baseline reads provider and id from config.
- Isolation: fresh temp dir and HOME per trial.
- Judge: yes/no rubric, checked against my own labels with kappa.
- Stats: per-task deltas, bootstrap over tasks for the CI; CI containing 0 = noise.
