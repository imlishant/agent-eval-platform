# PROJECT_STATE.md

## Status
No code written yet. Plan agreed (`PLAN.md`). Ready to start.

## Current objective
Build the Agent Evals Platform per `PLAN.md`, within a ~4-hour time box.

## Next action
Follow `PLAN.md §13` build order:
1. **Shared schemas** — trace event, config, task types (TypeScript + Python dataclasses)
2. **Runner + sandbox + mock harness** — `runner/run_trial.py`, `runner/sandbox.py`, mock adapter
3. **Baseline harness** — plain tool-calling loop with Anthropic SDK
4. **Graders + tasks + grader tests** — 20 tasks, deterministic + judge graders
5. **Hermes adapter** — spike first; decide if it goes in the experiment
6. **API + stats** — NestJS, SQLite, subprocess pool, paired bootstrap, export
7. **UI** — Vue 3: Run, Compare, Trial pages
8. **Docker** — Dockerfile + compose, README, DESIGN.md

## Cut order if behind schedule
failure analysis → Hermes in experiment → judge tasks to 2 → config dropdown (use CLI flag)

## Blocked on
Nothing. API key needed at runtime (set in `.env`).
