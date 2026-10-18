# Project State

_Last updated: 2026-10-18 (end of session) by Claude Code (claude-opus-5-5)_

## Current objective
Agent Evals Platform per `PLAN.md` (v2): every PDF deliverable, free providers only. Version 0.9.0; history in `CHANGELOG.md`, progress table in `README.md`, every decision in `docs/DECISIONS.md` (D1–D20).

## Completed
- Platform v0.10.1: runner, harnesses (mock, baseline, hermes), model adapter + registry, 4 graders, 20 tasks, failure analysis,
  OS sandbox, API + stats + export, UI (Runs, New experiment A/B builders, Compare, Trial, Models & harnesses). 80 pytest, 15 jest.
- Deliverable docs: README, docs/DESIGN.md, docs/LIMITS.md, docs/EXPERIMENT.md (experiment 4 skills off vs on: B better
  +0.36; experiment 5 baseline vs Hermes: no detectable difference, Hermes ~18× tokens; cost section with actuals).
- FIX-21 (Hermes memory-off leak) found while inspecting experiment 5, fixed.

## In progress
- Nothing half-done. Branch: main. API may still run on :3000 (`pkill -f "node dist/main.js"`).
- Open issues: CHORE-5 (author reviews judge labels). Docker done and verified (v0.11.0).

## Blocked / open questions
- Author decision: no more experiments (stated 2026-10-18).
- Optional: commit JSON/CSV exports of experiments 4 and 5 to `results/` (data/ is gitignored), offered, not answered.
- Agent-system repo: `main` with change-flow fix CF-3 merged locally, not pushed (ask).

## Next action
Remaining PDF items: judge label review (CHORE-5, `judge_validation/labels.json`, then
`cd runner && uv run python ../judge_validation/validate_judge.py`), video by the author.
Run the app: `docker compose up --build` (or native, see README). Native DB holds experiments 1-5; Docker volume is separate.

## Gotchas
- Gemini free tier: 500 requests/day/model, 250k tokens/min; one Hermes trial ≈ 30k tokens/call → TPM 429s come back `invalid`, retried with backoff; `POST /api/experiments/:id/retry-invalid` after the daily reset. Groq: 8k tokens/min (slow, ~1 trial/min). gemma-4-31b hangs; use 26b.
- Never edit the repo while an experiment runs: trials execute the working tree (FIX-17 flags mismatches).
- Hermes inside sandbox-exec needs the prepared base at `~/.cache/evalrunner/hermes-base` (built automatically once); no `--yolo`. Memory off = fresh Hermes home per session.
- NestJS 12 is ESM-only (breaks Jest) → pinned 11. openai SDK 3.x uses `httpx2`.
- Check jest's "Test Suites:" line, not only "Tests:" (a non-compiling suite is silently absent from the count).
- change-flow: any bug found mid-feature → issue + `fix/<id>` branch from where the bug lives, before editing. Keep and push every branch.
