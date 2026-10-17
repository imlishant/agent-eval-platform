# Agent Evals Platform — Implementation Plan (v2)

Context for any agent: this is the agreed plan. Follow it; propose changes before diverging.
Keep everything simple: the author must explain every part on a live call and change it on request.
v2 re-planned after reading the PDF line by line and learning that no paid API credits are available.

## 1. The assignment in one paragraph

Build a platform that evaluates an AI agent = harness (loop, tools, skills, memory, prompts) + model, and answers: when we change the harness or model, did it get better, worse, or stay the same, and how sure are we? Stack: NestJS API, Vue 3 + TypeScript UI, Python allowed for harness workers. Runs with one command (`docker compose up`), keys in `.env`. Graded on: eval method and honest statistics, clean adapters, trace detail, engineering quality, and judgment (stated assumptions and limits).

The PDF time box is ~5 days. We do **all of it** in ~4 hours of focused build by (a) building thin end-to-end first and deepening, (b) letting the agent write the code while the author reads, runs and decides, (c) running experiments in the background while writing docs. Nothing is dropped; what is cut is *depth* (§12).

## 2. Key decisions (full reasoning in `docs/DECISIONS.md`)

| # | Decision | Why |
|---|---|---|
| D1 | **No paid API.** Models via one OpenAI-compatible adapter; provider = base URL + key env var + model id (config values). | No credits. Ollama, Groq, Gemini, OpenRouter all speak this protocol, so one adapter covers all. |
| D2 | **Local open-weight model** via Ollama (`qwen3:8b`, fits 16 GB) is the always-available model. | Satisfies PDF: "one open-weight model". Free, offline, no rate limits. |
| D3 | **Hosted free-tier model** (Groq and/or Gemini AI Studio, no card) as second provider. | PDF prefers "two providers"; also far faster than local for 120 trials. |
| D4 | Anthropic is **a registry entry only if credits exist**; not built or claimed otherwise. | Untested code is worse than none. Shows the adapter point. |
| D5 | SQLite file, API-managed subprocess pool, no Redis/Postgres/LiteLLM. | Fewer moving parts to explain. |
| D6 | Configs = JSON in repo, ID = hash of canonical content; git = history. | Reproducibility is a hash, not a database feature. |
| D7 | Tasks = folders in repo. | Diff-able, reviewable. |
| D8 | One stats method: paired bootstrap over tasks (+ McNemar-style flip count reported for binary tasks). | PDF accepts bootstrap. |
| D9 | N = 3 trials; reasoning documented; trial-level variance reported so reader sees noise. | Time/rate-limit bound; honest. |
| D10 | Develop natively; Docker last, tested once from a clean clone. | Docker not installed yet. |
| D11 | Claude Pro subscription is **not** used as an eval backend. | Subscription auth is not an API; using it in our own harness is outside its terms. |

## 3. Architecture

```
Vue UI  →  NestJS API  →  SQLite file
                │
                └── spawns: python -m runner.run_trial <trial.json>
                     1. temp dir (sandbox) + own HOME, copy task fixtures
                     2. harness adapter (baseline | hermes | mock) using model adapter
                     3. graders
                     4. prints {trace, grades, usage} JSON on stdout
                   API parses and saves in one transaction
```

- Pool size is **per provider** (local Ollama: 1; hosted: 2–4) to respect memory and rate limits.
- Retry: provider errors (429, 5xx, network) retried 3× with exponential backoff + jitter. Still failing → trial `invalid`, excluded from comparison, count shown.
- Agent timeout / step limit / wrong answer → real result, score 0, reason saved (these are *agent* failures, not infra failures).
- Resumable: re-running an experiment skips trials already `done`; model calls are cached by hash of (model, messages, params) in a `call_cache` table so daily-quota interruptions don't waste work. Cache is **disabled for the experiment of record** unless noted, because caching hides trial-to-trial variance; it is used for dev and for retries of the same trial only.
- Docker: one container (Node + Python), serves API and built UI, one volume for SQLite.

### Repo layout
```
apps/api        NestJS (experiments, trials, stats, export, pool)
apps/web        Vue 3 + TS (Run, Compare, Trial pages)
runner/         Python: run_trial.py, sandbox.py, harnesses/, models/, graders/, tests/
tasks/<id>/     task.yaml, fixtures/, tests/, reference/ (solution)
configs/        *.json
judge_validation/  labels.json + validate_judge.py
docs/           DESIGN.md, LIMITS.md, EXPERIMENT.md, DECISIONS.md
docker-compose.yml, Dockerfile, .env.example, README.md
```

## 4. Interfaces

### Model adapter (Python) — "adding a model = config/registry entry"
```python
class ModelAdapter:
    def chat(self, messages, tools, *, temperature, max_tokens) -> ModelResponse:
        # ModelResponse: text, tool_calls[], usage{input,output}, latency_ms, raw_id
        ...
```
- `openai_compat` adapter: `base_url`, `api_key_env`, `model_id` come from the config's `model` block. Covers Ollama, Groq, Gemini, OpenRouter, OpenAI.
- `anthropic` adapter: only if credits exist (D4).
- Price table `models.json`: provider/model → $/1M in/out tokens (0 for free/local, with the *list price equivalent* also stored so cost formula is still meaningful).

### Harness adapter (Python) — "adding a harness = one class + one dict entry"
```python
class HarnessAdapter:
    id: str
    version: str
    def run_trial(self, ctx: TrialContext) -> Trace:  # must not raise on agent failure
        ...
# TrialContext: sessions[list of prompts], sandbox_dir, home_dir,
#   model {provider, base_url, id, api_key_env}, settings {skills[], memory: "off"|"on",
#   tools[], temperature, max_steps, max_tokens, timeout_s}
```
Harnesses:
- `mock` — scripted trace, no model calls (free pipeline testing, used in CI).
- `baseline` — plain tool-calling loop using a ModelAdapter. Tools: bash, read_file, write_file. Skills = markdown added to system prompt; a `skill_used` event is logged when the model calls `use_skill(name)`. Memory = `memory.md` in home_dir + `memory_write` tool, loaded at session start (`memory_read` event).
- `hermes` — verified in spike S2 (see DECISIONS D9): `HERMES_HOME=<trial home> hermes chat -q <prompt> --oneshot --format stream-json --in <sandbox> --provider <name> -m <model> --max-turns N --run-budget S --ignore-rules`. Provider defined in the trial's `config.yaml` (`providers:` base_url + key_env). Skills copied into `$HERMES_HOME/skills`; memory via `memory.memory_enabled`. JSONL events → trace. Memory writes detected by diffing `$HERMES_HOME/memories/` per session. No `--yolo`. Needs a model with ≥64k context ⇒ runs on Gemini, not local qwen3:8b or Groq.

### Trace event (shared schema)
```json
{"seq": 3, "session": 1, "type": "tool_call", "ts": 1729000000.1,
 "payload": {"name": "bash", "args": {"cmd": "pytest"}}}
```
Types: `message`, `model_call` (tokens, latency), `tool_call`, `tool_result`, `memory_read`, `memory_write`, `skill_used`, `error`, `final_answer`.

### Config file
```json
{"name": "baseline-qwen3-8b-local", "harness": "baseline",
 "model": {"provider": "openai_compat", "base_url": "http://localhost:11434/v1",
           "api_key_env": null, "id": "qwen3:8b"},
 "settings": {"skills": [], "memory": "off", "tools": ["bash","read_file","write_file"],
              "temperature": 0.7, "max_steps": 20, "max_tokens": 4000, "timeout_s": 180}}
```
Config ID = sha256 of canonical JSON (sorted keys, `name` excluded). Trials store config ID **and** the inlined config + harness version + task hash + code SHA, so any result is reproducible.

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
Memory tasks have 2 sessions. Judge tasks have a `rubric` list of yes/no criteria.

## 5. Data model (SQLite)
- `configs`: id (hash), json, harness_version, created_at
- `experiments`: id, name, hypothesis, config_a, config_b, task_ids, task_set_hash, n_trials, code_sha, created_at, status
- `trials`: id, experiment_id, task_id, config_id, trial_index, status (pending/running/done/invalid), score, input_tokens, output_tokens, cost_usd, latency_ms, attempts, error
- `events`: trial_id, seq, session, type, payload_json
- `grades`: trial_id, grader, score, passed, reasoning
- `call_cache`: key, response_json (dev / retry only)

## 6. Graders
- Deterministic: `exact_match`, `file_check` (exists, contains/regex/JSON fields), `unit_tests` (run command in sandbox, pass = exit 0).
- Every deterministic task has a reference solution (must score 1) and an empty run (must score 0), asserted in pytest — proves the grader is correct and discriminating.
- `llm_judge`: rubric of yes/no criteria, score = share met, temperature 0, reasoning per criterion; judge model differs from the tested model where possible; position/length bias noted in LIMITS.
- Judge validation: 15 outputs hand-labelled pass/fail in `judge_validation/labels.json`, deliberately including borderline and verbose-but-wrong cases. Script reports accuracy and Cohen's kappa. kappa < 0.6 → judge tasks flagged "low trust" in UI and excluded from the headline number (shown separately).
- Grader disagreement (stretch category in PDF): where a task has a deterministic *and* judge grader, disagreement is recorded as a failure category.

## 7. Task set (20, every PDF grader type covered)
| Group | Count | Grader | Separates configs? |
|---|---|---|---|
| File/code (fix test, write file with fields, CSV transform) | 8 | unit_tests / file_check | model size |
| Exact-answer tool tasks | 3 | exact_match | model size |
| Skill-sensitive (skill describes house format or fake internal CLI) | 3 | file_check | skill on/off |
| Memory-sensitive (2 sessions; fact given in session 1, needed in 2) | 3 | file_check | memory on/off |
| Judge-graded (summary, README, policy reply) | 3 | llm_judge | model size |

Tasks are custom (not from public benchmarks) to reduce contamination. Difficulty is tuned so a 4–8B model neither scores 0 nor 1 on all (checked in a pilot with N=1).

## 8. Statistics (paired bootstrap)
1. Per task and config: mean score over N trials.
2. Per task: `delta = mean_B − mean_A`. Show every delta.
3. Mean delta over tasks. CI: resample tasks with replacement 10,000×, recompute, take 2.5/97.5 percentiles.
4. CI contains 0 → UI shows "No detectable difference (could be noise)". Also show minimum detectable effect ≈ 1.43 × CI half-width (80% power, two-sided 5%; see DECISIONS D16).
5. Same treatment for cost, tokens, latency.
6. Invalid trials: drop that task-trial pair from both configs; show count.
7. Why N=3: between-task variance usually exceeds within-task variance, so more tasks help more than more trials; a pilot measures both (§11) and we report the measured within-task SD to justify N after the fact.
8. Tests: hand-computed small example; no-difference simulation (CI contains 0 ≈ 95% of the time); known-large-effect simulation (CI excludes 0).

## 9. UI (3 pages)
- Run: define/pick config A and B (form that writes a config JSON, shows its hash), task set, N → start; progress bar, live invalid count.
- Compare: overall delta + CI + verdict, per-task delta table, cost/latency/tokens, invalid count, export JSON/CSV.
- Trial: event timeline (messages, tool calls/results, memory, skills), grades with reasoning, score, failure category.

## 10. Failure analysis (PDF stretch — included, rule-based from trace)
- step limit hit → `step_exhaustion`
- tool error from bad args → `bad_tool_args`
- unknown tool name → `wrong_tool`
- final answer early + failed grade → `gave_up_early`
- same tool call repeated 3+ times → `loop`
- deterministic fail vs judge pass (or reverse) → `grader_disagreement`
Compare page shows failure-category counts per config.

## 11. Experiments
- **E1 (primary, experiment of record):** same model (Gemini free tier), **two harnesses**: `baseline` vs `hermes`. This is the PDF's "same model in two harnesses" axis and exercises the required harness. 20 tasks × 3 trials × 2 configs = 120 trials. Hypothesis written *before* running.
- **E2 (memory axis):** `hermes` memory on vs off on the memory/skill task subset (PDF's own example).
- **E3 (cheap, if quota allows):** `baseline` model axis on Groq (`gpt-oss-20b` vs `gpt-oss-120b`) or local `qwen3:8b`.
- Exact Gemini model picked after reading the account's limits (aistudio.google.com/rate-limit) and the pilot's tokens/trial.
- **Pilot (N=1, few tasks):** measure token use, latency, within-task variance → informs cost formula and N justification.
- Report: hypothesis, setup, N, CI, per-task deltas, 2–3 inspected trajectories, conclusion.
- Cost formula: `tasks × trials × configs × (avg_in_tokens × price_in + avg_out_tokens × price_out)`. Free/local → actual spend $0, plus **list-price equivalent** and wall-clock time. Reduce cost by: call caching, early stopping when CI excludes 0 after N=2, screening on a task subset, cheaper judge.

## 12. Schedule (≈4 hours; every deliverable present; depth deepens in passes)
| Time | Work | Checkpoint |
|---|---|---|
| 0:00–0:20 | Setup: uv/py3.13, Ollama + `qwen3:8b`, free keys, Hermes install spike (S1–S3) | Local model answers; Hermes answers one prompt |
| 0:20–0:50 | Schemas, sandbox, runner, mock harness, 1 task, exact grader | 1 task graded end to end (mock) |
| 0:50–1:20 | `openai_compat` adapter + baseline harness (tools, skills, memory, retries) | Real model solves the task, trace saved |
| 1:20–1:50 | All graders + 20 tasks + reference/empty tests + judge + labels | Grader tests pass; judge kappa printed |
| 1:50–2:20 | API: experiments, pool, retries, stats + tests, export, failure rules | Compare via API |
| 2:20–2:50 | UI: Run, Compare, Trial | Click failed trial, see trace |
| 2:50–3:10 | Hermes adapter (from spike) | Hermes trial graded |
| 3:10–3:40 | Run E1/E2 in background; write DESIGN, LIMITS, EXPERIMENT while running | Results saved |
| 3:40–4:00 | Docker, README (add task/harness/model), video script | `docker compose up` works from clean clone |

Honest caveat: wall-clock is bounded by local inference speed and free-tier quotas, not by coding. If a run is still going at 4:00, the experiment finishes in the background and the docs get final numbers after. The cut order from v1 is **removed**; the fallback is "less depth", not "missing deliverable": fewer judge-labelled examples (15→10), shorter rubrics, simpler UI styling.

## 13. Spikes (do first; they decide the plan, ≤10 min each)
- **S1 Local model:** install Ollama, pull `qwen3:8b`, make one tool-calling request via `/v1`. Measure tokens/sec and whether tool calls parse. *Fail →* try another model tag.
- **S2 Hermes:** install, run `hermes chat --oneshot -q "..." --provider custom --base-url http://localhost:11434/v1`, with HOME overridden. Confirm: per-trial isolation, memory off switch, token usage visible, exit codes. *Fail →* document precisely why; keep adapter stub + mock-backed test.
- **S3 Hosted free tier:** create a Groq and/or Gemini key; one call; read actual rate/daily limits from the console. *Fail →* E1 becomes two local model sizes.

## 14. Requirement traceability (PDF → plan)
| PDF requirement | Where satisfied |
|---|---|
| Hermes required + 2nd harness | §4 `hermes`, `baseline`, `mock` |
| 2 providers or 1 open-weight; common interface | D1–D3, §4 model adapter |
| New harness/model = adapter only | §4; demonstrated in README + DESIGN |
| Deterministic + judge graders; judge validated | §6 |
| Configs harness×model×settings, versioned | §4 config, D6 |
| N trials, isolation, timeouts/retries/partial failure | §3 |
| CIs + paired test, per-task deltas, noise message, cost/latency/tokens | §8, §9 |
| Full trajectory inspection | §4 trace, §9 Trial page |
| Failure analysis (stretch) | §10 |
| One command, `.env` | D10, Docker |
| ≥20 tasks, some discriminating | §7 |
| Persist + export | §5, §9 |
| Document every assumption | `docs/DECISIONS.md`, `docs/LIMITS.md` |
| README, design doc, limits, cost, experiment, video | §11, doc map in `AGENTS.md` |

## 15. Assumptions and known limits (seed for LIMITS.md)
- Small open-weight models are weak at multi-step tool use; absolute scores are low and the platform's claims are about *differences*, not capability.
- Free-tier quotas and model versions change; results carry the date and model id; hosted free models can be updated silently by the provider (reproducibility risk).
- Local and hosted models differ in serving stack (quantization), so cross-provider comparisons include that difference.
- Skills and memory work differently in Hermes and baseline; cross-harness comparisons include that.
- 20 tasks only detect large differences; N=3 gives coarse within-task means.
- Judge model is small; bias toward length/position possible; validated on 15 labels only.
- Tasks and labels written by one author; contamination reduced, not eliminated.
- Temp-dir isolation, not container-per-trial; a malicious agent could escape (documented, acceptable for a local eval tool).
- Hermes can edit its own skills; skills and memory reset per trial.

## 16. One-line answers for the call
- Harness adapter: one Python class with `run_trial()` returning the standard trace.
- Model adapter: base URL + model id + key env var; one adapter speaks every OpenAI-compatible provider.
- Isolation: fresh temp dir and HOME per trial.
- Judge: yes/no rubric, checked against my own labels with kappa.
- Stats: per-task deltas, bootstrap over tasks for the CI; CI containing 0 = noise.
- Why free models: no credits; the platform is provider-agnostic, so swapping in a paid model is a config change.
