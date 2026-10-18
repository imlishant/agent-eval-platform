# AGENTS.md

## Project
Agent Evals Platform — take-home assignment (Applied AI Engineer).  
Evaluate any AI harness × model and answer: did the agent improve, and how sure are we?

## Stack
- `apps/api` — NestJS, TypeScript, SQLite (via better-sqlite3)
- `apps/web` — Vue 3, TypeScript, Vite
- `runner/` — Python 3.11+: harness workers, graders, sandbox isolation
- `configs/` — JSON config files (ID = content hash)
- `tasks/` — one folder per task (`task.yaml`, fixtures, tests, reference)
- `judge_validation/` — `labels.json` + `validate_judge.py`
- `docs/` — `DESIGN.md`, `LIMITS.md`, `EXPERIMENT.md`
- One container (Node + Python), SQLite file volume, `docker compose up`

## Key decisions (see PLAN.md §2)
- Models: no paid API. One OpenAI-compatible adapter; local Ollama `qwen3:8b` + hosted free tier (Groq/Gemini). See PLAN.md §2
- No Redis, no Postgres, no LiteLLM proxy
- N = 3 trials; 20 tasks; paired bootstrap for CIs; failure analysis included
- Config ID = SHA of JSON content; git is version history

## Commands
| Area | Command | Proves |
|---|---|---|
| API | `cd apps/api && npm run test` | unit + integration tests |
| API dev | `cd apps/api && npm run start:dev` | server starts |
| Web dev | `cd apps/web && npm run dev` | UI compiles and serves |
| Web build | `cd apps/web && npm run build` | production build passes (API then serves it on :3000) |
| Runner tests | `cd runner && python -m pytest` | graders + harnesses |
| Grader self-check | `cd runner && python -m pytest tests/test_graders.py` | each grader correct |
| Judge validation | `cd judge_validation && python validate_judge.py` | kappa ≥ 0.6 |
| Full stack | `docker compose up --build` | everything from clean clone |

## Hard rules
- `change-flow: on` — branch freely, commit; merge/push need user approval.
- **Keep every branch, forever.** Never delete a merged branch (local or remote). Push every branch to `origin` when it is created and after each commit, so GitHub shows the full history of work. Merge with `--no-ff`.
- Never push secrets or API keys; `.env` is gitignored.
- Adding a harness or model = writing one adapter + one dict/registry entry. Never change platform core for this.
- Do not call `docker compose up` in CI without a `--build` clean run verified first.
- Run experiments of record from a dedicated git worktree; never edit the repo while an experiment runs (trials execute the working tree).
- Any bug found while working: stop, open an issue, fix on its own `fix/<id>` branch (change-flow); never inside a `feat/` commit.
- Closed issues move to `ISSUES-CLOSED.md` (append-only); decisions go to `docs/DECISIONS.md`.
- `PLAN.md` is the agreed design; propose changes before diverging.

## Doc map (read on demand, not up front)
| When touching… | Read |
|---|---|
| Architecture / data model | `docs/DESIGN.md` |
| Assumptions and known limits | `docs/LIMITS.md` |
| The comparison experiment | `docs/EXPERIMENT.md` |
| Full implementation plan | `PLAN.md` |
| Harness / model adapter interfaces | `PLAN.md §4` |
| Task format | `PLAN.md §7` and `tasks/README.md` (when it exists) |
| Statistics method | `PLAN.md §8` |
| Why a decision was made | `docs/DECISIONS.md` |
