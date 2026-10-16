# Agent Evals Platform

Evaluate any AI agent harness (X) running any model (Y) and answer one question with evidence:
**when we change the harness or the model, did the agent get better, worse, or stay the same, and how sure are we?**

An agent = **harness** (the loop, tools, skills, memory, prompts) + **model**. The platform runs a fixed set of
tasks under two configurations, several times each, grades every run, and compares the two with confidence
intervals, so a real improvement can be told apart from noise.

> **Version 0.5.0 (in development).** See [Progress](#progress) for what works today and [CHANGELOG.md](CHANGELOG.md) for history.

## Progress

| Area | Status | Notes |
|---|---|---|
| Plan, decisions, provider spikes | ✅ done | [PLAN.md](PLAN.md), [docs/DECISIONS.md](docs/DECISIONS.md) |
| Trial runner: trace, retries, invalid-trial handling | ✅ done | `runner/evalrunner/run_trial.py` |
| Isolation: OS sandbox for agent processes, secret scrubbing | ✅ done (macOS) | `runner/evalrunner/isolation.py`, DECISIONS D14 |
| Harnesses: `mock`, `baseline` | ✅ done | `runner/evalrunner/harnesses/` |
| Harness: `hermes` (Hermes Agent, required) | ✅ done | `harnesses/hermes.py`, DECISIONS D9, D15 |
| Model adapter: any OpenAI-compatible endpoint (Ollama, Groq, Gemini, …) | ✅ done | `runner/evalrunner/models/` |
| Graders: exact_match, file_check, unit_tests, llm_judge | ✅ done | each deterministic grader self-tested |
| 20 tasks (code, exact, skill, memory, judge) | ✅ done | `tasks/` |
| Judge validation (agreement with human labels, Cohen's kappa) | 🟡 provisional | labels await human review |
| API (NestJS + SQLite): experiments, worker pool, stats, export | 🔜 next | |
| UI (Vue 3): Run, Compare, Trial pages | ⬜ todo | |
| Failure analysis (stretch) | ⬜ todo | |
| Experiment + report | ⬜ todo | `docs/EXPERIMENT.md` |
| Docker (`docker compose up`) | ⬜ todo | |
| Design doc, known limits | ⬜ todo | `docs/DESIGN.md`, `docs/LIMITS.md` |

## How it works

```
Vue UI  →  NestJS API  →  SQLite
                │
                └── spawns: python -m evalrunner.run_trial <trial.json>
                     1. fresh temp folder (sandbox) + private HOME, task files copied in
                     2. harness runs the agent with the configured model → trace of every step
                     3. graders score the result (0..1) and explain why
                     4. prints one JSON object: {status, score, grades, usage, trace}
```

- **Config** = harness + model + settings (skills, memory, tools, temperature, step/token budgets, timeout), stored as a
  JSON file in `configs/`. Its ID is a hash of its content, so the same settings always give the same ID; git keeps the history.
- **Task** = a folder in `tasks/` with the prompt(s), starting files, how it is graded, and a reference solution.
- **Trial** = one task × one config × one repetition. Agents are non-deterministic, so every task runs N times.
- A provider failure (rate limit, server error) or a harness crash is retried; if it still fails the trial is marked
  **invalid** and left out of the comparison instead of being counted as a wrong answer.
- **Isolation:** every agent process runs in an OS sandbox that can only touch its own trial folder. This is not
  optional: in testing, an agent with a terminal searched the disk and copied a task's reference answer
  ([DECISIONS D14](docs/DECISIONS.md)). API keys are scrubbed from every result.

## Setup

Requirements: [uv](https://docs.astral.sh/uv/) (installs Python 3.13 for you). Optional: [Ollama](https://ollama.com) for a
local model, [Hermes Agent](https://hermes-agent.nousresearch.com) for the `hermes` harness (its first trial prepares a
shared base in `~/.cache/evalrunner/hermes-base`, ~350 MB, once). Native runs use the macOS sandbox; on other systems use Docker.

```bash
git clone <this repo> && cd <repo>
cp .env.example .env          # add the keys you have (all have free tiers; see below)
cd runner && uv sync          # creates the Python environment
uv run pytest                 # all tests should pass; no API key needed
```

Keys (`.env`, never committed):

| Variable | Used for | Free option |
|---|---|---|
| `GROQ_API_KEY` | fast hosted open-weight models for development | console.groq.com |
| `GEMINI_API_KEY` | Gemini Flash Lite (experiments, Hermes) and Gemma (LLM judge) | aistudio.google.com |
| none | local model via Ollama: `ollama pull qwen3:8b` | runs on your machine |

## Run one trial

```bash
cd runner
set -a; . ../.env; set +a
echo '{"task_dir": "../tasks/count-csv-rows",
       "config": '"$(cat ../configs/baseline-groq-gpt-oss-20b.json)"'}' > /tmp/trial.json
uv run python -m evalrunner.run_trial /tmp/trial.json
```

Use `configs/mock-solve.json` to run without any model or key.

## Add a task

1. Create `tasks/<task-id>/` with:
   - `task.yaml`: `id`, `category` (`code | exact | skill | memory | judge`), `sessions` (one prompt per session;
     two sessions for memory tasks), and `graders`.
   - `fixtures/`: files the agent starts with (copied into its sandbox).
   - `tests/`: hidden tests for `unit_tests` graders (the grader uses this copy, not the agent's).
   - `reference/files/` and/or `reference/answer.txt`: a correct solution.
2. Grader types:
   ```yaml
   graders:
     - type: exact_match      # final answer equals `expected`
       expected: "37"
     - type: file_check       # contains / not_contains / regex / json_fields on a file
       path: out.json
       json_fields: {port: 8080}
     - type: unit_tests       # pass = command exits 0
       command: "python -m pytest -q tests"
     - type: llm_judge        # yes/no rubric graded by the judge model
       target_file: summary.md
       context_files: [incident.md]
       rubric: ["States the root cause.", "Invents no facts."]
   ```
3. Run `cd runner && uv run pytest tests/test_graders.py`. For deterministic graders it checks that your reference
   solution scores 1.0 and an empty attempt scores 0.0, so a broken task fails loudly.

## Add a harness

A harness is one Python class plus one registry line; nothing else in the platform changes.

1. Create `runner/evalrunner/harnesses/<name>.py`:
   ```python
   class MyHarness(HarnessAdapter):
       id = "my-harness"
       version = "1"
       def run_trial(self, ctx: TrialContext) -> Trace:
           trace = Trace()
           # run ctx.task.sessions inside ctx.sandbox_dir with ctx.config.model / ctx.config.settings
           # record steps with trace.add("tool_call", ...), trace.add("final_answer", text=...)
           return trace
   ```
   Agent failures (wrong answer, step limit, timeout) are recorded in the trace, never raised. Raise
   `ProviderError` only for infrastructure failures.
2. Register it in `runner/evalrunner/harnesses/__init__.py`: `MyHarness.id: MyHarness`.
3. Use it from a config: `"harness": "my-harness"`.

## Add a model

**Any OpenAI-compatible endpoint** (Ollama, Groq, Gemini, OpenRouter, OpenAI, vLLM, …) needs only a config file:

```json
{"name": "baseline-my-model", "harness": "baseline",
 "model": {"provider": "openai_compat", "id": "<model name>",
           "base_url": "https://<provider>/v1", "api_key_env": "MY_PROVIDER_KEY"},
 "settings": {"temperature": 0.7, "max_steps": 15, "max_tokens": 2000, "timeout_s": 180}}
```

**A different API protocol** (for example Anthropic's Messages API) needs one adapter class implementing
`ModelAdapter.chat()` in `runner/evalrunner/models/` plus one line in `models/__init__.py`.

## Repository layout

```
runner/        Python: run_trial, sandbox, harnesses/, models/, graders/, tests/
tasks/         20 tasks, one folder each
configs/       configurations (JSON) and the judge model (judge.json)
skills/        skill documents the agent can load when a config enables them
judge_validation/  human-labelled judge outputs + validate_judge.py (accuracy, Cohen's kappa)
docs/          DECISIONS.md (why), DESIGN.md, LIMITS.md, EXPERIMENT.md
apps/api, apps/web   NestJS API and Vue UI (coming)
```

## Documentation

- [PLAN.md](PLAN.md): the agreed design and schedule
- [docs/DECISIONS.md](docs/DECISIONS.md): every decision and assumption, with the reason
- [CHANGELOG.md](CHANGELOG.md): what changed in each version
