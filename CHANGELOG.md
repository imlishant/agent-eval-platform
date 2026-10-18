# Changelog

Versions follow `0.<milestone>.<patch>` until the first complete release (1.0.0 = every PDF deliverable done).
Each entry names the branch it came from; all branches are kept on GitHub.

## [Unreleased]
- Video (by the author).

## [0.11.0] - 2026-10-18 · Docker (`feat/docker`)
- `docker compose up --build`: one container (API, UI, runner, Hermes Agent), data in a volume, `.env` optional.
- Linux isolation: each trial's agent runs as its own unprivileged user ID (setpriv), trial folder mode 700, answer keys
  root-only; reported as `isolation: unprivileged-user`.
- Verified from a fresh clone: API + UI up, 80 runner tests pass inside the container, real trials for both harnesses.
- Fixed on the way: `fix/22` validate_judge loads .env; `fix/23` stale api lock file (npm 11); `fix/24` Hermes test
  depended on machine state; group write on the Hermes base lock files.

## [0.10.1] - 2026-10-18 · Experiment 5 results and a memory-off fix (`fix/21-…`, `docs/experiment-5`)
- docs/EXPERIMENT.md now holds both experiments: baseline vs Hermes on Gemini 3.1 Flash Lite (17 tasks, N = 3, 66 valid
  trials): no detectable difference (+0.06, CI [0.00, +0.18]); Hermes used ~18× the tokens. Cost section uses actual tokens.
- `fix/21-hermes-memory-off-leak`: with memory off, each session's Hermes home is deleted when the session ends; found by
  inspecting experiment 5's only differing task.
- LIMITS: memory tasks can be solved by note-taking in the shared folder; ceiling effect; the leak.

## [0.10.0] - 2026-10-18 · Deliverable documents (`docs/deliverables`)
- README rewritten: setup, running an experiment from the UI step by step, reading results, adding a model / harness / task.
- docs/DESIGN.md: architecture, adapter interfaces, data model, isolation and reproducibility, graders and their
  validation, statistical method and the choice of N (measured within- vs between-task SD).
- docs/LIMITS.md: where conclusions should not be trusted (task-set size, judge, contamination, providers, harness quirks).
- docs/EXPERIMENT.md: experiment 4, skills off vs on (+0.36, 95% CI [+0.06, +0.69], B better; controls unchanged),
  trajectories, conclusion, and the cost formula with actual ($0) and Opus 5.5 list-price figures.
- Configs of experiments 4 and 5 committed so they can be reproduced.

## [0.9.0] - 2026-10-18 · Simpler UI (`feat/ui-config-builder`)
- New experiment page: A and B each built from harness × model × memory × skills; "What changes" shows the axes.
- Models & harnesses page: add an OpenAI-compatible model and test it from the UI; harness list with how to add one.
- Home is the runs list. `fix/19-stale-experiment-status`: finished experiments no longer listed as running.

## [0.8.0] - 2026-10-18 · Failure analysis (`feat/failure-analysis`)
- Failed trials get a category from their trace (timeout, step_exhaustion, loop, bad_tool_args, wrong_tool,
  grader_disagreement, gave_up_early, wrong_answer); counts per config on Compare, category + signals on Trial.
- `fix/16-scrub-account-ids`: provider account IDs no longer stored, exported or logged.
- `fix/17-code-version-per-trial`: each trial records its code version; Compare warns on mismatch.
- `chore/12-retro-issue-records`: ISSUES-CLOSED.md, with honest records of 4 earlier fixes that skipped the flow.

## [0.7.0] - 2026-10-18 · UI (`feat/web-ui`)
- Vue 3 UI: Run (define a config, start an experiment, shows which axes differ), Compare (verdict, CI chart,
  quality next to tokens/latency/cost, per-task deltas, clickable trials, export), Trial (grader reasoning, full
  trajectory by session). Light and dark.
- `POST /api/configs`: configs defined in the UI are saved as files and validated by the runner.
- Fixed (DECISIONS D17): bad tool calls rejected by the provider are agent errors, not infra; no verdict below
  5 tasks; latency excludes rate-limit waits.

## [0.6.0] - 2026-10-18 · API, scheduler, statistics, export (`feat/api-stats`)
- NestJS API over SQLite: experiments, trials, events, grades, config snapshots.
- Scheduler with one concurrency lane per provider; invalid trials retried with backoff, then marked invalid.
- Paired bootstrap over tasks (seeded): per-task deltas, 95% CI, verdict with "could be noise" message, minimum
  detectable effect; same for cost (actual and Claude-list-price reference), tokens and latency.
- JSON and CSV export. Tests: hand-computed example, invalid-pair dropping, no-difference coverage simulation,
  end-to-end experiment through the real runner.

## [0.5.0] - 2026-10-16 · Hermes harness and OS-level isolation (`feat/hermes-adapter`)
- `hermes` harness: headless Hermes Agent per session, JSON events mapped to our trace, memory reads/writes from
  file diffs, skills installed per trial, memory off = fresh Hermes home per session.
- Found and fixed: an agent escaped folder isolation and copied a reference answer (DECISIONS D14).
  Agent processes now run under an OS sandbox; secrets scrubbed from results; unit_tests grader hardened;
  harness crashes are `invalid`, not scored.

## [0.4.0] - 2026-10-16 · Graders and task set (`feat/graders-tasks`)
- Graders: `file_check` (contains / regex / JSON fields, partial credit), `unit_tests` (uses the task's own tests),
  `llm_judge` (yes/no rubric, temperature 0, reason per criterion).
- 20 tasks: 8 code, 3 exact answer, 3 skill-sensitive, 3 memory-sensitive (two sessions), 3 judge-graded.
- Grader self-check: every deterministic task scores 1.0 on its reference solution and 0.0 on an empty run.
- Judge validation: 15 labelled outputs, accuracy and Cohen's kappa (provisional until labels are human-reviewed).
- Judge model: `gemma-4-26b-a4b-it` (DECISIONS D11).
- README and this changelog (`docs/readme-changelog`).

## [0.3.0] - 2026-10-16 · Runner, baseline harness, model adapter (`feat/runner-core`)
- Shared schemas (config, task, trace, grade); config ID = hash of content.
- Per-trial isolation: fresh sandbox folder and private HOME.
- `mock` harness (no model) and `baseline` harness (tool-calling loop with bash, read_file, write_file; skills; memory).
- `openai_compat` model adapter for any OpenAI-compatible endpoint; retries with backoff; exhausted retries mark the trial `invalid`.
- `exact_match` grader; `run_trial` CLI that prints one JSON result.

## [0.2.0] - 2026-10-16 · Provider and Hermes spikes (`feat/spikes`)
- Verified tool calling on local `qwen3:8b`, Groq and Gemini free tiers; measured rate limits.
- Verified Hermes Agent headless with a per-trial `HERMES_HOME` (DECISIONS D6–D10).

## [0.1.0] - 2026-10-16 · Plan (`chore/replan-free-providers`)
- Plan v2 built from the assignment PDF; free providers only; decision log started.
