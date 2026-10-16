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
