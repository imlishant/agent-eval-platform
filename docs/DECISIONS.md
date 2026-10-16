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

## D9 · 2026-10-16 · Spike S2 (Hermes v0.22.2) passed on Gemini; not runnable on local or Groq
- Headless works: `hermes chat -q <prompt> --oneshot --format stream-json --in <sandbox> --provider <name> -m <model> --max-turns N --run-budget S --ignore-rules`.
- Isolation works: `HERMES_HOME=<trial home>` puts config, memories/, skills/, sessions and state.db per trial. Custom providers via `providers:` in that config.yaml (base_url + key_env).
- `stream-json` gives JSONL events: tool_use, tool_result, text, result (with tokens + duration + exit_code) → maps onto our trace schema.
- Memory switch: `memory.memory_enabled` / `user_profile_enabled` in config.yaml; memory files in `$HERMES_HOME/memories/`.
- Safety: in `-q` mode Hermes blocks `execute_code`; we do **not** pass `--yolo` (keeps its dangerous-command approvals on). Agent still has read/write/search/terminal.
- Gemini `gemini-3.1-flash-lite`: solved the probe task, exit 0, 4 tool calls, ~12.7 s.
- **Cost driver:** Hermes's own system prompt ⇒ ~29k input tokens even for a trivial task (baseline harness: ~150). Cross-harness token/cost comparisons include this.
- Local `qwen3:8b`: refused — Hermes requires ≥ 64k context; qwen3:8b has 40k, and a 64k KV cache does not fit in 16 GB alongside the model.
- Groq: 400 on `reasoning_effort`; also its 8k tokens/min limit is below one Hermes request (~29k). Not usable for Hermes.
- Consequence: Hermes experiments run on Gemini free tier. Baseline can run on any provider.

## D10 · 2026-10-16 · Provider for Hermes experiments: Gemini Flash Lite free tier
- Account limits (AI Studio, free tier): `gemini-3.1-flash-lite` and `gemini-3.5-flash-lite` each 15 RPM / 250k TPM / **500 RPD**, separate quotas per model.
  Gemini 2.5/3.x Flash (non-lite): 5 RPM / 20 RPD — unusable. Gemma 4 26B/31B: 30 RPM / 16k TPM / 14.4k RPD.
- Mistral free plan: API keys inactive without upgrade (checked in console) — rejected. Cerebras: now needs a card — rejected.
- Budget: Hermes ≈ 5 calls × ~30k tokens per trial ⇒ TPM-bound at ~1.5 trials/min. E1 (baseline vs Hermes, 120 trials) ≈ 500–600 requests on one model ⇒ may cross the 500 RPD cap ⇒ runs are resumable and may span two quota days.
- Split: E1 on `gemini-3.1-flash-lite`; E2 (Hermes memory on/off) on `gemini-3.5-flash-lite`; judge on `gemma-4-31b-it` (different family from models under test).
- Dev and debugging never spend Gemini quota: use local `qwen3:8b` or Groq.

## D11 · 2026-10-16 · Judge model: gemma-4-26b-a4b-it (not 31b)
- `gemma-4-31b-it` hung (no response in 45–120 s, repeated); `gemma-4-26b-a4b-it` answers in ~2 s with the same free limits (30 RPM / 16k TPM / 14.4k RPD).
- Different model family from every model under test (gpt-oss, qwen, Gemini Flash Lite).
- Judge pass = every rubric criterion met; score = share met. Temperature 0.

## D12 · 2026-10-16 · Judge validation, first pass
- 15 hand-written outputs (5 per judge task: good, wrong fact, missing part, invented feature, borderline), labelled pass/fail.
- Result: accuracy 1.00, Cohen's kappa 1.00 (threshold 0.6). **Provisional**: labels drafted by the agent, awaiting the author's review (`reviewed_by_human`), and the examples are cleaner than real agent output.
- Plan: after the experiment, add 5–10 real agent outputs labelled by the author and re-run. Listed in LIMITS as "judge validated on a small, partly synthetic set".

## D13 · 2026-10-16 · Task set design (20)
- code 8 (unit_tests/file_check), exact 3, skill 3 (made-up house formats + fake internal CLI, so the model cannot know them without the skill), memory 3 (fact in session 1, needed in session 2), judge 3.
- Grader trust: every deterministic task scores 1.0 on its reference solution and 0.0 on an empty run (pytest, 34 cases). unit_tests graders use the task's own copy of the tests, so an agent editing tests cannot fake a pass.
- top-city: data generated so the highest-cost city is not the most frequent one (no shortcut answer).

## D14 · 2026-10-16 · Finding: an agent escaped folder isolation and read the answer key → OS sandbox
- What happened: Hermes, memory off, task `remember-codeword` (needs a fact from session 1). It ran `find /`,
  then `ls -R` on this repo, read `tasks/remember-codeword/reference/files/codeword.txt`, copied it and scored 1.0.
  It also ran `env`, printing API keys into the trace.
- Why it matters: a contaminated score looks exactly like a real one. Every comparison would have been wrong in an
  unknowable direction, and exported traces would have contained secrets.
- Fix (all tested, `tests/test_isolation.py`, each attack re-played):
  1. Every agent process (Hermes, baseline `bash`, and the agent's code during `unit_tests` grading) runs under
     macOS `sandbox-exec`: no read/write of the home folder, this repo, or other trials; only its own trial folder
     plus read-only tool installs. Linux/Docker: separate unprivileged user (Docker step); otherwise every result
     says `isolation: folder-only`, never silent.
  2. Secrets: every result is scrubbed (`[REDACTED:NAME]`) before leaving the runner; Hermes gets only its own key.
  3. `unit_tests` hardening: planted `conftest.py`/pytest config removed; pytest pass also needs a JUnit report
     with >0 tests and 0 failures (so `os._exit(0)` on import cannot pass).
  4. A harness that crashes (no result) is `invalid`, not a 0 for the agent.
- Re-run under the sandbox: same trial scores 0.0 (honest); memory-on version scores 1.0.

## D15 · 2026-10-16 · Hermes inside the sandbox: shared prepared base + per-session homes when memory is off
- Hermes builds a dependency environment per `HERMES_HOME` on first use (needs writes the sandbox denies). One base
  home is prepared once, unsandboxed, at `~/.cache/evalrunner/hermes-base`; each trial links `installs/` to it
  read-only (only lock/lease files writable, so an agent cannot alter the install other trials use).
- Hermes can search its stored past sessions even with `memory_enabled: false` (seen: it found session 1's text in
  its session DB). Our definition of memory off = nothing carries between sessions, so memory off ⇒ a fresh
  Hermes home per session; memory on ⇒ one home per trial.
- Observed cost effect (one task): memory on 50k tokens / score 1.0; memory off 210k tokens / score 0.0.
- Gemini free TPM (250k) can be hit by a single long Hermes trial ⇒ such trials come back `invalid` (HTTP 429)
  and must be retried later by the API; never scored 0.
