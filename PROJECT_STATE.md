# PROJECT_STATE.md

## Status
Planning complete (PLAN.md v2). No runner code yet. Branch: `chore/replan-free-providers` (not merged, not pushed).

## Current objective
Build the Agent Evals Platform per `PLAN.md`, ~4 h time box, all PDF deliverables, free providers only.

## Next action
Run spikes PLAN.md §13: S1 Ollama+qwen3:8b tool call, S2 Hermes headless, S3 free hosted key (Groq/Gemini).
Then PLAN.md §12 order: schemas → runner/mock → baseline → graders+tasks → API/stats → UI → Hermes → experiments → docs/Docker.

## Needs from the user
- Install Ollama (`brew install ollama`, or ollama.com) and approve pulling `qwen3:8b` (~5 GB).
- Create a free Groq and/or Google AI Studio key (no card); put in `.env` (gitignored).
- Install Docker Desktop/OrbStack before the last hour.

## Blocked on
Nothing for planning. Experiments need spikes S1/S3.
