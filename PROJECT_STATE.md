# Project State

_Last updated: 2026-10-18 by Claude Code (claude-opus-5-5)_

## Current objective
Agent Evals Platform per `PLAN.md` (v2): every PDF deliverable, free providers only. Version 0.9.0; history in `CHANGELOG.md`, progress table in `README.md`, every decision in `docs/DECISIONS.md` (D1–D20).

## Completed
- Runner (sandbox + OS confinement, mock/baseline/hermes harnesses, OpenAI-compatible model adapter, 4 graders, 20 tasks, failure analysis, secret + account-ID scrubbing, per-trial code version). 79 pytest.
- API (NestJS 11 + SQLite): experiments from saved configs or UI drafts, per-provider scheduler, retries → invalid, paired bootstrap stats, export, model registry + connection test. 15 jest (2 suites).
- UI (Vue 3): Runs, New experiment (A/B builders), Compare, Trial, Models & harnesses. Screenshot-verified light + dark.
- Judge (gemma-4-26b) validated on 15 drafted labels: kappa 1.00, **provisional** (CHORE-5).

## In progress
- Branch `feat/experiment` (= main, nothing committed yet). Next: the experiment of record.
- Open issues (ISSUES.md): CHORE-5 (user reviews judge labels), CHORE-8 (Docker isolation).
- API server may still be running on :3000 from this session (`pkill -f "node dist/main.js"` to stop). Local DB `data/evals.db` holds demo experiments 1–3 (Groq), not results of record.

## Blocked / open questions
- User to confirm experiment plan (proposed below) or adjust it in the builder.
- User to review `judge_validation/labels.json` (set `reviewed_by_human: true`).
- Agent-system repo (`~/development/agent-system`): `main` merged locally with change-flow fix CF-3, **not pushed** — ask user.

## Next action
Experiment of record, from a dedicated worktree (`git worktree add ../evals-run main`), API started there:
E1 baseline vs hermes on `gemini-3.1-flash-lite`, all 20 tasks, N=3 (120 trials); E2 hermes memory off vs on on
`gemini-3.5-flash-lite`, memory + skill tasks. Write the hypothesis first. Then `docs/EXPERIMENT.md` (cost formula
with actual $0 + Opus 5.5 list-price equivalent, 2–3 trajectories), `docs/DESIGN.md`, `docs/LIMITS.md`, Docker
(CHORE-8: agent as unprivileged user), video script.

## Gotchas
- Gemini free tier: 500 requests/day/model, 250k tokens/min; one Hermes trial ≈ 30k tokens/call → TPM 429s come back `invalid`, retried with backoff; `POST /api/experiments/:id/retry-invalid` after the daily reset. Groq: 8k tokens/min (slow, ~1 trial/min). gemma-4-31b hangs; use 26b.
- Never edit the repo while an experiment runs: trials execute the working tree (FIX-17 flags mismatches).
- Hermes inside sandbox-exec needs the prepared base at `~/.cache/evalrunner/hermes-base` (built automatically once); no `--yolo`. Memory off = fresh Hermes home per session.
- NestJS 12 is ESM-only (breaks Jest) → pinned 11. openai SDK 3.x uses `httpx2`.
- Check jest's "Test Suites:" line, not only "Tests:" (a non-compiling suite is silently absent from the count).
- change-flow: any bug found mid-feature → issue + `fix/<id>` branch from where the bug lives, before editing. Keep and push every branch.
