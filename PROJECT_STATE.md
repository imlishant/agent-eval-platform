# PROJECT_STATE.md

## Status
v0.5.0. Runner, mock/baseline/hermes harnesses, OpenAI-compatible model adapter, 4 graders, 20 tasks, judge validation (provisional), OS sandbox (macOS) + secret scrubbing. 65 pytest passing. Branch: feat/api-stats.

## Current objective
Build the Agent Evals Platform per `PLAN.md`, all PDF deliverables, free providers only.

## Next action
FEAT-7 (API + stats) → UI → failure analysis → experiments (Gemini quota: see DECISIONS D10, D15) → docs → Docker (CHORE-8).

## Needs from the user
- Review judge_validation/labels.json (CHORE-5).
- Install Docker Desktop/OrbStack before the Docker step.

## Blocked on
Nothing.
