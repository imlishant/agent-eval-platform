# Decision log

Format: ID · date · decision · why · what we gave up. Newest last. Seed for DESIGN.md and LIMITS.md.

## D0 · 2026-10-16 · Time box: ~4 h build for a ~5 day brief
- Why: author's constraint. Nothing is cut; depth is staged (thin end-to-end first, then deepen).
- Gave up: polish, large N, large label sets.

## D1 · 2026-10-16 · No paid API; one OpenAI-compatible model adapter
- Why: no API credits (Claude Pro does not include API access). Ollama/Groq/Gemini/OpenRouter all expose OpenAI-style chat completions, so provider is a config value.
- Gave up: Anthropic models in the experiment. Registry entry documented, not built (untested code).

## D2 · 2026-10-16 · Local open-weight model (Ollama, qwen3:8b) as the baseline model
- Why: free, offline, fits 16 GB RAM, satisfies PDF's "one open-weight model".
- Gave up: speed (local inference is slow), strength (small model).

## D3 · 2026-10-16 · Hosted free tier as second provider (Groq/Gemini), verified in spike S3
- Why: PDF prefers two providers; hosted is fast enough for 120 trials.
- Gave up: guaranteed quota; limits change. Mitigation: per-provider concurrency, backoff, call cache, resumable runs.

## D4 · 2026-10-16 · Claude Pro subscription not used as a backend
- Why: it is not API access; using it from our own harness is outside its intended use.

## D5 · 2026-10-16 · Experiment axis candidates (final pick after spikes)
- E1 model axis on baseline harness; E2 memory/skill on vs off. Hypothesis written before running.

## D6 · 2026-10-16 · Spike S1 (local) passed
- `qwen3:8b` via Ollama `/v1`: correct tool call + uses tool result. ~9 tok/s, 6–10 s per turn (first call includes load).
- Consequence: local is fine for dev/judge-free runs, but ~1 min+ per trial; pool size 1 for Ollama.

## D7 · 2026-10-16 · Spike S3 (hosted free) passed
- Groq: `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b` all tool-call correctly, <1 s/turn.
  Limits (from response headers): 1000 requests/day and **8000 tokens/min per model** — TPM is the bottleneck for agent loops.
- Gemini (`/v1beta/openai/`): `gemini-3.1-flash-lite`, `gemini-3.5-flash`, `gemma-4-26b-a4b-it` tool-call correctly, 1–2.5 s/turn. No limit headers; measure in pilot.
- Candidate E1 (decide after pilot measures tokens/trial): baseline harness, model axis, e.g. `gpt-oss-20b` vs `gpt-oss-120b` (Groq, same family, size only) or local `qwen3:8b` vs hosted model.
- Judge candidate: `gemini-3.5-flash` (not a model under test).

## D8 · 2026-10-16 · Cost reference uses Anthropic list prices
- Actual spend is $0 (free/local). The cost report also prices the measured tokens at Claude list rates, as the real-world paid equivalent.
  Source: Anthropic pricing table cached 2026-10-06 — Opus 5.5 $4 / $20, Sonnet 5.5 $2 / $10, Haiku 5.5 $0.10 / $0.50 per 1M input / output tokens. Re-check before final report.

## D9 · 2026-10-16 · Spike S2 (Hermes) pending
- Official installer reviewed (installs to ~/.hermes, pinned uv with checksum, adds ~/.local/bin to PATH). Must be run by the user.
