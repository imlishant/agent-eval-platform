# Design

The platform answers one question with evidence: **when the harness or the model changes, did the agent get better,
worse, or stay the same, and how sure are we?** It runs the same tasks under two configurations, several times each,
grades every run, and compares the two with paired statistics. Every number on screen can be traced back to the steps
an agent took.

Why each choice was made, with dates and evidence, is in [DECISIONS.md](DECISIONS.md) (D1–D20). Where the results should
not be trusted is in [LIMITS.md](LIMITS.md).

## 1. Architecture

```
 Vue 3 UI ──HTTP──▶ NestJS API ──▶ SQLite (one file)
 (Runs, New                │
  experiment, Compare,     └─ scheduler: one lane per provider, spawns
  Trial, Models &              python -m evalrunner.run_trial <trial.json>
  harnesses)                   ├─ 1. fresh sandbox folder + private HOME, task files copied in
                               ├─ 2. harness adapter runs the agent (model via model adapter),
                               │     every agent process confined by the OS sandbox
                               ├─ 3. graders score the result, failure category from the trace
                               └─ 4. prints ONE JSON object (secrets + account IDs scrubbed)
                             API saves trial + events + grades in one transaction
```

| Part | Language | Responsibility |
|---|---|---|
| `runner/` (`evalrunner`) | Python 3.13 | One trial end to end: isolation, harness, model calls, graders, failure analysis. Stateless; its only output is one JSON object on stdout. |
| `apps/api` | TypeScript, NestJS 11, better-sqlite3 | Control plane: experiments, scheduling and retries, statistics, export, model registry. Calls Python only through `run_trial`, `catalog`, `config_tool`, `check_model`. |
| `apps/web` | TypeScript, Vue 3 | Build A/B configs, start experiments, read comparisons, inspect trials. Served by the API on the same port. |
| `tasks/`, `configs/`, `skills/` | YAML / JSON / Markdown | Data, versioned by git. |

The boundary is a process boundary on purpose: Python is where agent frameworks live (Hermes is Python), TypeScript is
required for API and UI, and a subprocess per trial gives isolation and crash containment for free (a crashing agent
cannot take the API down).

## 2. Interfaces: adding a harness or a model never touches the core

### Harness adapter (`runner/evalrunner/harnesses/base.py`)

```python
class HarnessAdapter(ABC):
    id: str                      # "baseline", "hermes", ...
    version: str                 # stored with every trial
    description: str
    settings: tuple[str, ...]    # which config settings it actually uses (UI hides the rest)
    requirements: str            # e.g. "needs >= 64k context"

    def run_trial(self, ctx: TrialContext) -> Trace: ...
        # ctx: task (sessions = list of prompts), config, sandbox_dir, home_dir, trial_index
        # Agent failures (wrong answer, step limit, timeout) are recorded in the trace, never raised.
        # Infrastructure failures raise ProviderError -> the trial is "invalid", not scored.
```

New harness = one class + one line in `harnesses/__init__.py`. Registered harnesses:

| Harness | What it is | Skills | Memory |
|---|---|---|---|
| `mock` | Scripted fake agent (reference answer or nothing). No model, no cost; tests the pipeline. | – | – |
| `baseline` | Our minimal tool-calling loop: `bash`, `read_file`, `write_file`. | Names + one-line descriptions in the system prompt; the agent loads one with `use_skill(name)` (logged as `skill_used`). | `HOME/memory.md`, loaded at each session start (`memory_read`); `memory_write` tool. |
| `hermes` | Hermes Agent (Nous Research), headless: `hermes chat -q … --oneshot --format stream-json`, one process per session. | Copied into the trial's Hermes home as `skills/<name>/SKILL.md`. | Hermes's own memory files; writes detected by diffing `memories/` per session. Memory off = a fresh Hermes home per session, deleted when the session ends (Hermes stores every prompt in its home and can search past sessions even with memory disabled; FIX-21). |

Hermes's JSON events (`tool_use`, `tool_result`, `text`, `result`) are mapped onto our trace schema, so both harnesses
produce comparable traces.

### Model adapter (`runner/evalrunner/models/base.py`)

```python
class ModelAdapter(ABC):
    def chat(self, messages, tools, *, temperature, max_tokens) -> ModelResponse
        # ModelResponse: text, tool_calls, input/output tokens, latency_ms, attempts, waited_ms,
        #                assistant_message (appended to the conversation as-is)
```

One adapter, `openai_compat`, serves every OpenAI-compatible endpoint (Ollama, Groq, Gemini, OpenRouter, OpenAI, vLLM).
A provider is therefore **data**: `base_url` + model `id` + the **name** of the env var holding the key. New model =
one entry in `configs/models.json` (from the UI, with a connection test). New protocol (e.g. Anthropic Messages API) =
one class + one line in `models/__init__.py`.

The adapter owns the retry policy: 429, 5xx, timeouts and network errors are retried up to 4 times, honouring
`retry-after`; the time spent waiting is reported (`waited_ms`) and excluded from latency. A 400 caused by the **model**
producing an invalid tool call is not an infrastructure failure: it becomes a `bad_tool_args` agent error and costs a
step (DECISIONS D17).

## 3. Data model

### Files (versioned by git)

| Object | Where | Identity |
|---|---|---|
| **Task** | `tasks/<id>/`: `task.yaml` (id, category, sessions, graders), `fixtures/` (starting files), `tests/` (hidden tests), `reference/` (a correct solution) | `id` + **content hash** of every file in the folder, stored on each trial |
| **Config** | `configs/<name>.json`: `harness`, `model {provider, id, base_url, api_key_env}`, `settings {skills, memory, tools, temperature, max_steps, max_tokens, timeout_s, extra}` | **ID = sha256 of the canonical JSON without the name** (12 hex chars). Same content = same ID, whatever its name. Configs built in the UI are saved as files automatically; identical content reuses the existing file. |
| **Model registry** | `configs/models.json` | `name` |
| **Skill** | `skills/<name>.md` (first line = description) | `name` |

### Database (`data/evals.db`, SQLite, WAL)

| Table | Key columns |
|---|---|
| `configs` | `id` (content hash), `name`, `json` (full snapshot, so old results stay reproducible after a file changes) |
| `experiments` | `id`, `name`, `hypothesis`, `config_a`, `config_b`, `task_ids`, `task_hashes`, `n_trials`, `code_sha`, `status` |
| `trials` | `experiment_id`, `task_id`, `config_id`, `trial_index`, `status` (pending / running / done / invalid), `score`, `passed`, `failure_category`, `failure_signals`, tokens, `cost_usd`, `ref_cost_usd`, `latency_ms`, `attempts`, `error`, `harness_version`, `isolation`, `task_hash`, `code_version` |
| `events` (the trace) | `trial_id`, `seq`, `session`, `type`, `ts`, `payload_json` |
| `grades` | `trial_id`, `grader`, `score`, `passed`, `reasoning` |

**Trace event types:** `message`, `model_call` (tokens, latency, attempts, rate-limit wait), `tool_call`, `tool_result`,
`memory_read`, `memory_write`, `skill_used`, `error` (kind: timeout, step_exhaustion, bad_tool_args, agent, …),
`final_answer`. Each event has a `session` number, so two-session memory tasks read as two conversations.

## 4. Execution, isolation and reproducibility

**Scheduling.** Creating an experiment inserts every task × config × trial as `pending`, interleaved (A and B per task
and trial index), so a quota cut-off leaves both sides equally covered. A scheduler polls every 500 ms and starts trials
in **one lane per provider** (local Ollama 1, Gemini 1, Groq 2, mock 4; max 4 total), because each provider has its own
rate limit. On restart, `running` trials go back to `pending`; a result is saved in one transaction or not at all.

**Failure handling.**

| What went wrong | Recorded as | In the comparison? |
|---|---|---|
| Wrong answer, step limit, timeout, bad tool call, loop | `done`, score from graders, failure category | yes: it is the agent's result |
| Provider 429 / 5xx / network after retries, harness crash | `invalid` after 3 attempts (60 s × attempt back-off) | no: dropped together with the same trial index of the other config; count shown |

**Isolation (no state leaks between trials).** Folder isolation alone failed in testing: an agent with a terminal searched
the disk, found this repo's reference answer and copied it, and printed API keys with `env` (DECISIONS D14). Now:
- every trial gets a fresh temp folder and its own HOME; memory files live there, so memory carries over only between
  the sessions of one trial, and only when the config says `memory: on`;
- every agent process (Hermes, baseline `bash`, and the agent's code while `unit_tests` grades it) runs under the macOS
  OS sandbox (`sandbox-exec`): no reading or writing the user's home, this repo, or other trials; only its own trial folder
  plus read-only tool installs. In Docker (Linux, as root) each trial's agent processes run via `setpriv` as their own
  unprivileged user ID with a mode-700 trial folder, and the answer keys are root-only in the image. Anywhere else the
  level is recorded as `folder-only` on every trial (never silent);
- results are scrubbed: env-var secrets → `[REDACTED:NAME]`, provider account IDs and emails → `[REDACTED]`;
- the `unit_tests` grader removes pytest config files the agent may have planted and requires a JUnit report with >0
  tests and 0 failures, so code that exits 0 on import cannot pass.
Each of these is a test that replays the attack (`runner/tests/test_isolation.py`), and those tests fail when the sandbox
is turned off.

**Reproducibility.** A trial records: config ID and snapshot, task content hash, harness version (Hermes includes its CLI
version), isolation level, and the **code version it actually ran on** (git SHA, or SHA + hash of the uncommitted diff).
The experiment records the code version at creation; Compare warns if any trial differs (the code changed mid-run,
DECISIONS D17/FIX-17). To reproduce a result: check out that code version, use the config snapshot, run the same tasks.
Model outputs themselves are not reproducible (sampling, provider-side model updates), which is why trials repeat.

## 5. Graders and how they were validated

| Grader | Kind | Checks | Score |
|---|---|---|---|
| `exact_match` | deterministic | final answer equals the expected text (trimmed, case-insensitive by default) | 1 / 0 |
| `file_check` | deterministic | a file: exists, contains / not contains, regex, JSON fields | share of checks passed |
| `unit_tests` | deterministic | the task's own hidden tests on the agent's code | 1 / 0 |
| `llm_judge` | model-based | yes/no rubric criteria, temperature 0, reason per criterion | share of criteria met |

A task lists one or more graders. **Trial score = mean of its graders' scores; passed = every grader passed.** Only
`rename-function` has several (tests + two file checks); disagreement between them is its own failure category.

| Task category (count) | Grader | What makes it useful |
|---|---|---|
| code (8) | `unit_tests`, `file_check` | Real fixes and small programs |
| exact (3) | `exact_match` | One right answer; `top-city` built so the most frequent city is not the answer (no shortcut) |
| skill (3) | `file_check` | A made-up house format / internal CLI: unsolvable without the skill → separates skills on/off |
| memory (3, two sessions) | `file_check` | A fact given in session 1, needed in session 2 → separates memory on/off |
| judge (3) | `llm_judge` | Summary, README, customer reply: no single right text |

**Validation of deterministic graders.** For every deterministic task, pytest runs the `mock` harness twice: with the
reference solution the score must be 1.0, doing nothing must score 0.0 (34 cases, `runner/tests/test_graders.py`).
This proves each grader recognises success *and* catches failure.

**Validation of the LLM judge.** The judge is `gemma-4-26b-a4b-it`, a different model family from every model under test
(self-preference bias). `judge_validation/labels.json` holds 15 outputs (5 per judge task: correct, wrong fact, missing
part, invented feature, borderline) with pass/fail labels; `validate_judge.py` grades them and reports accuracy and
Cohen's kappa. Result: accuracy 1.00, kappa 1.00 against a 0.6 threshold. This is **provisional**: the labels were
drafted by the agent and await the author's review, and they are cleaner than real agent output (see LIMITS).
Below kappa 0.6 the plan is to flag judge tasks as low-trust and report them separately.

**Failure analysis.** Each failed trial gets one category from its trace, first matching rule wins, every match kept as a
signal: timeout, step_exhaustion, loop (same call 3+ times), bad_tool_args, wrong_tool, grader_disagreement,
gave_up_early, wrong_answer. Rule-based, so every category points at events a person can check.

## 6. Statistical method and the choice of N

**Unit of analysis: the task.** The same tasks run under A and B, so the comparison is paired by task.

1. For each task and config: mean score over its N trials.
2. Per task: `delta = mean_B − mean_A`. Every delta is shown.
3. Effect = mean of the task deltas.
4. **95% CI by bootstrap over tasks**: resample the tasks with replacement 10,000 times (seeded, so the same data always
   gives the same interval), recompute the mean delta, take the 2.5th and 97.5th percentiles.
5. Verdict: CI above 0 → "B better", below 0 → "B worse", contains 0 → **"No detectable difference (could be noise)"**.
   With fewer than 5 finished tasks there is no verdict ("too few tasks"): a bootstrap over 2–4 values is not an interval.
6. The minimum detectable effect is shown next to it: ≈ 1.43 × CI half-width (80% power, two-sided 5%), so "no
   difference" reads as "no difference larger than X".
7. The same treatment for tokens, latency, actual cost and list-price-equivalent cost, so trade-offs sit next to quality.
8. Invalid trials drop the same trial index on both sides; the count is shown.

Why bootstrap over tasks rather than a test over trials: trials of the same task are not independent (same prompt, same
files), and tasks differ far more from each other than repeated runs of one task do. Resampling tasks puts the
uncertainty where it is. Tests: a hand-computed example; a coverage simulation (300 experiments where A and B are the
same agent: the CI contains 0 in 88–99% of them); a large-effect case that must be detected.

**Choosing N = 3.** The variance that matters splits into *between tasks* and *within a task across repeated runs*.
Measured in experiment 1 (N = 2, 8 tasks): within-task SD 0.04, between-task SD 0.18. Repeating a trial mostly
re-measures the same outcome; adding tasks narrows the interval much more. N = 3 is enough to see whether a task is
flaky (and to average out a single lucky or unlucky run) while keeping the free-tier quota for tasks. The platform reports
both SDs on every comparison, so N can be revisited from data: if within-task SD grows (e.g. a less deterministic
model), raise N. Cost and time grow linearly in N (see EXPERIMENT.md, cost formula).

## 7. Where things are

| Need | Look at |
|---|---|
| Run one trial without the UI | `cd runner && uv run python -m evalrunner.run_trial trial.json` |
| Tests | `cd runner && uv run pytest` (79) · `cd apps/api && npm test` (2 suites, 15 tests) |
| Judge validation | `cd runner && uv run python ../judge_validation/validate_judge.py` |
| Why a decision was made | [DECISIONS.md](DECISIONS.md) |
