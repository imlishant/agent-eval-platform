# Agent Evals Platform

Evaluate any AI agent harness (X) running any model (Y), and answer one question with evidence:
**when we change the harness or the model, did the agent get better, worse, or stay the same, and how sure are we?**

An agent = **harness** (the loop, tools, skills, memory, prompts) + **model**. The platform runs the same tasks under two
configurations, several times each, grades every run, and compares the two with confidence intervals, so a real
improvement can be told apart from noise. Every number links back to the trace of what the agent did.

> **Version 0.11.0.** History in [CHANGELOG.md](CHANGELOG.md). Design: [docs/DESIGN.md](docs/DESIGN.md) ·
> Known limits: [docs/LIMITS.md](docs/LIMITS.md) · Experiment: [docs/EXPERIMENT.md](docs/EXPERIMENT.md) ·
> Decisions: [docs/DECISIONS.md](docs/DECISIONS.md)

## Contents
[What is in the box](#what-is-in-the-box) · [Setup](#setup) · [Run an experiment from the UI](#run-an-experiment-from-the-ui) ·
[Read the results](#read-the-results) · [Add a model](#add-a-model) · [Add a harness](#add-a-harness) · [Add a task](#add-a-task) ·
[API](#api) · [Tests](#tests) · [Status](#status) · [Repository layout](#repository-layout)

## What is in the box

| | |
|---|---|
| **Harnesses** | `baseline` (our minimal tool-calling loop), `hermes` (Hermes Agent, Nous Research), `mock` (scripted, no model, for testing) |
| **Models** | Any OpenAI-compatible endpoint. Pre-registered: Gemini 3.1 / 3.5 Flash Lite, gpt-oss-20b / 120b on Groq, qwen3:8b on local Ollama (all free) |
| **Tasks** | 20, in 5 categories: code (8), exact answer (3), skill (3), memory (3, two sessions), judge (3) |
| **Graders** | `exact_match`, `file_check`, `unit_tests` (deterministic) and `llm_judge` (rubric, validated against labels) |
| **Statistics** | Per-task deltas, 95% bootstrap CI over tasks, "no detectable difference (could be noise)" verdict, minimum detectable effect; same for tokens, latency and cost |
| **Inspection** | Full trajectory per trial: messages, tool calls and results, memory reads/writes, skills used, grader reasoning, failure category |
| **Isolation** | Fresh folder and HOME per trial; every agent process in an OS sandbox (macOS); secrets and account IDs scrubbed |

## Setup

**Requirements (native):** macOS (for the OS sandbox; or use Docker), [uv](https://docs.astral.sh/uv/) (installs Python 3.13),
Node.js 22+. Optional: [Ollama](https://ollama.com) for a local model; [Hermes Agent](https://hermes-agent.nousresearch.com)
for the `hermes` harness (its first trial prepares a shared base in `~/.cache/evalrunner/hermes-base`, ~350 MB, once).

```bash
git clone <this repo> && cd <repo>
cp .env.example .env                                   # add the keys you have (all have free tiers)
cd runner   && uv sync && uv run pytest && cd ..       # Python env + 80 tests (no key needed)
cd apps/web && npm install && npm run build && cd ../..
cd apps/api && npm install && npm run start:dev        # builds and starts the API + UI
```

Open **http://localhost:3000**. Results are stored in `data/evals.db` (SQLite).

**Keys** go in `.env` (git-ignored). The platform only ever stores the variable *name*.

| Variable | Used for | Free option |
|---|---|---|
| `GEMINI_API_KEY` | Gemini Flash Lite (works with Hermes) and Gemma (the LLM judge) | aistudio.google.com |
| `GROQ_API_KEY` | gpt-oss-20b / 120b, fast, baseline harness only (8k tokens/min) | console.groq.com |
| none | local model: `ollama pull qwen3:8b` | your machine |

### With Docker (one command)

```bash
cp .env.example .env            # add your keys
docker compose up --build       # → http://localhost:3000
```

One container: API + UI + runner + Hermes Agent (`INSTALL_HERMES=0 docker compose up --build` to skip Hermes). Results live
in the `evals-data` volume. Agents run as a per-trial unprivileged user that cannot read the answer keys. To record the code
version on every trial: `CODE_SHA=$(git rev-parse --short HEAD) docker compose up --build`. For a local Ollama model, use
base URL `http://host.docker.internal:11434/v1`.

Verified from a fresh clone (2026-10-18, OrbStack on Apple Silicon): `docker compose up --build` starts API + UI, the
runner reports isolation `unprivileged-user`, all 80 runner tests pass inside the container, and real trials ran for both
harnesses (baseline on Groq, Hermes on Gemini). First build takes ~5 minutes (Hermes install).

## Run an experiment from the UI

An experiment compares **A** and **B** on the same tasks. Change **one** thing between them to learn what that thing does.

1. **Models & harnesses** (top bar). Optional: press **Test** on the model you want. It makes one real request with a tool
   and tells you whether the key works and the model can call tools.
2. **New experiment.** Two builders, side by side:
   - **Harness:** `baseline`, `hermes` or `mock`. The description and any requirement (Hermes needs ≥ 64k context) are shown.
   - **Model:** from the registry, with its limits underneath.
   - **Memory between sessions:** Off / On.
   - **Skills:** click the chips to give the agent skill documents it can open.
   - **Limits and sampling** (folded): temperature, max steps, max tokens, timeout.
3. Set up A, press **A → B** to copy it, then change **one** thing in B. The **What changes** bar names the axes that differ:
   green = exactly one, red = none or several (then a difference cannot be pinned to one cause).
4. **Tasks.** Click a category chip to include or exclude it (blue = included), or **Pick individual tasks**. Choose the tasks
   where your change can matter, plus a few where it should not (controls):

   | You are testing | A vs B differ in | Include |
   |---|---|---|
   | skills | skills | **skill** tasks (+ exact as controls) |
   | memory | memory | **memory** tasks (+ a few others) |
   | a model or a harness | model / harness | all 20 |

5. **Trials per task** (N, default 3), a **name** (default "A vs B") and your **hypothesis**, written before you see results.
   The line underneath shows the total: *tasks × 2 × N trials*.
6. **Start experiment.** You land on the experiment page; it updates every 2 s.

While it runs: grey dots fill in as trials finish. A red dashed dot is **invalid** (the provider or harness failed after
retries, e.g. a rate limit); it is not counted as a wrong answer, and **Retry invalid** appears when the run ends. **Do not
edit the project files during a run:** trials run on the working copy, and the page warns if the code changed mid-run.
For results you will report, run from a separate `git worktree` nobody edits.

Configs you build are saved automatically as `configs/<harness>-<model>-<id>.json`. If the same content already exists, it
is reused: the config ID is a hash of its content.

## Read the results

On an experiment's page, top to bottom:

| Section | What it tells you |
|---|---|
| **Verdict card** | Score change B − A, its 95% CI as a chart, and the verdict: *B better*, *B worse*, *No detectable difference (could be noise)*, or *Too few tasks to judge* (under 5 finished tasks). Also how many tasks got better, worse or stayed the same, and the noise between repeated runs. |
| **Quality, cost and speed** | Score, tokens, latency, actual cost and the same tokens priced at Claude Opus 5.5 list price, each with a CI; per-config totals; **Export JSON / CSV**. |
| **Why trials failed** | Failure categories per config: timeout, step_exhaustion, loop, bad_tool_args, wrong_tool, grader_disagreement, gave_up_early, wrong_answer. |
| **Per task** | One row per task: a dot per trial for A and B (green pass, amber partial, red fail, dashed red invalid) and the per-task delta. **Click a dot** to open that trial. |
| **Trial page** | Score, status, failure category and signals, tokens, latency, isolation; **Why**: each grader's reasoning; **Trajectory**: every step by session: messages, model calls, tool calls and results, memory reads/writes, skills used, errors, final answer. |

Worked example with real numbers: [docs/EXPERIMENT.md](docs/EXPERIMENT.md).

## Add a model

**From the UI:** *Models & harnesses → Add a model*: display name, the model id at the provider, base URL, and the **name** of
the key variable in `.env` (empty for a local model). **Test connection** makes one real tool-calling request before you save.
It is stored in `configs/models.json` and appears in the experiment builder.

**By hand:** add the same fields to `configs/models.json`. Any OpenAI-compatible endpoint works with no code (Ollama, Groq,
Gemini, OpenRouter, OpenAI, vLLM). A **different API protocol** (e.g. Anthropic's Messages API) needs one adapter class in
`runner/evalrunner/models/` implementing `ModelAdapter.chat()` plus one line in `models/__init__.py`.

## Add a harness

A harness is a program, so it is added in code, not in the UI (the *Models & harnesses* page lists the registered ones
and these steps). One class plus one registry line; nothing else in the platform changes.

1. Create `runner/evalrunner/harnesses/<name>.py`:
   ```python
   class MyHarness(HarnessAdapter):
       id = "my-harness"
       version = "1"
       description = "What it is, in one line."
       settings = ("skills", "memory", "max_steps", "timeout_s")   # the config settings it uses
       requirements = ""                                            # e.g. "needs >= 64k context"

       def run_trial(self, ctx: TrialContext) -> Trace:
           trace = Trace()
           # for each prompt in ctx.task.sessions: run the agent in ctx.sandbox_dir with ctx.config.model,
           # record steps: trace.add("tool_call", ...), trace.add("tool_result", ...), trace.add("final_answer", text=...)
           return trace
   ```
   Record agent failures (wrong answer, step limit, timeout) in the trace; raise `ProviderError` only for infrastructure
   failures. Run any external process through `isolation.confine(cmd, ctx.sandbox_dir.parent)`.
2. Register it in `runner/evalrunner/harnesses/__init__.py`: `MyHarness.id: MyHarness`.
3. Reload the UI: it appears in the builder.

## Add a task

1. Create `tasks/<task-id>/`:
   - `task.yaml`: `id`, `category` (`code | exact | skill | memory | judge`), `sessions` (one prompt per session; two for
     memory tasks), `graders`.
   - `fixtures/`: files the agent starts with. `tests/`: hidden tests for `unit_tests` (the grader uses this copy).
   - `reference/files/` and/or `reference/answer.txt`: a correct solution.
2. Graders:
   ```yaml
   graders:
     - type: exact_match      # final answer equals `expected`
       expected: "37"
     - type: file_check       # contains / not_contains / regex / json_fields on a file
       path: out.json
       json_fields: {port: 8080}
     - type: unit_tests       # pass = all tests pass
       command: "python -m pytest -q tests"
     - type: llm_judge        # yes/no rubric graded by the judge model
       target_file: summary.md
       context_files: [incident.md]
       rubric: ["States the root cause.", "Invents no facts."]
   ```
   Trial score = mean of its graders; passed = all passed.
3. `cd runner && uv run pytest tests/test_graders.py` checks that your reference solution scores 1.0 and an empty attempt
   0.0, so a broken task fails loudly.

## API

`cd apps/api && npm run start:dev` → http://localhost:3000/api

| Endpoint | What it does |
|---|---|
| `GET /api/catalog` | configs (with content-hash IDs), tasks, skills, harnesses, models |
| `POST /api/experiments` | `{name, hypothesis, config_a, config_b, task_ids?, n_trials?}`; a config is a saved file name or `{harness, model, settings}` |
| `GET /api/experiments/:id` | status and progress |
| `GET /api/experiments/:id/compare` | per-task deltas, CIs, verdicts, totals, failure categories, code-version mismatches |
| `GET /api/trials/:id` | one trial: full trace and grades |
| `POST /api/experiments/:id/retry-invalid` | re-queue invalid trials (e.g. after a daily quota reset) |
| `GET /api/experiments/:id/export.json` · `export.csv` | export |
| `POST /api/models` · `POST /api/models/check` | add a model · test one |

One trial without the API: `cd runner && uv run python -m evalrunner.run_trial trial.json` with
`{"task_dir": "../tasks/count-csv-rows", "config": <a config>}` (use `configs/mock-solve.json` for no model, no key).

## Tests

| Command | Proves |
|---|---|
| `cd runner && uv run pytest` | 80 tests: every grader on reference/empty runs, harness loop, retries, isolation attacks, failure rules |
| `cd apps/api && npm test` | 2 suites, 15 tests: statistics (hand example, coverage simulation), an end-to-end experiment through the real runner |
| `cd apps/web && npm run build` | UI type-checks and builds |
| `cd runner && uv run python ../judge_validation/validate_judge.py` | judge accuracy and Cohen's kappa against labels |

## Status

| Area | Status |
|---|---|
| Runner, harnesses (mock, baseline, hermes), model adapter, graders, 20 tasks, failure analysis | ✅ |
| Isolation (macOS OS sandbox), secret and account-ID scrubbing, per-trial code version | ✅ |
| API, statistics, export; UI (runs, A/B builder, compare, trial, models & harnesses) | ✅ |
| Design doc, known limits, experiment write-up with cost | ✅ |
| Judge validation | 🟡 provisional: labels await human review (CHORE-5) |
| Experiments: skills off vs on (B better, +0.36); baseline vs Hermes (no detectable difference, Hermes 18× tokens) | ✅ [docs/EXPERIMENT.md](docs/EXPERIMENT.md) |
| Docker (`docker compose up --build`) with per-trial unprivileged-user isolation | ✅ verified from a clean clone |
| Video | ⬜ |

## Repository layout

```
runner/            Python: run_trial, sandbox, isolation, harnesses/, models/, graders/, failures, tests/
apps/api           NestJS API: experiments, scheduler, statistics, export (SQLite in data/)
apps/web           Vue 3 UI
tasks/             20 tasks, one folder each
configs/           configs (JSON), models.json (model registry), judge.json, prices.json
skills/            skill documents
judge_validation/  labelled judge outputs + validate_judge.py
docs/              DESIGN, LIMITS, EXPERIMENT, DECISIONS
```
