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

## D16 · 2026-10-18 · API design (NestJS 11 + better-sqlite3)
- NestJS 11.2.7, not 12: v12 is ESM-only and Jest (ts-jest, CommonJS) cannot load it; 11 is the mature line.
- better-sqlite3 (as planned); Node's built-in `node:sqlite` works but is still marked experimental.
- Config IDs come only from the Python runner (`evalrunner.catalog`), so API and runner can never disagree on a hash.
  The full config JSON is snapshotted into the `configs` table when an experiment is created.
- Scheduler: in-process, polls every 500 ms; **one lane per provider** with its own limit (Ollama 1, Gemini 1,
  Groq 2, mock 4; max 4 total). Trials are created interleaved (A and B per task and trial index) so a quota
  cut-off leaves both sides equally covered. Restart-safe: `running` → `pending` on boot; results saved in one
  transaction.
- Invalid trials: retried up to 3 attempts with 60 s × attempt backoff (free-tier quotas reset per minute);
  then `invalid`; `POST /experiments/:id/retry-invalid` requeues them (e.g. after the daily quota resets).
- Stats as PLAN §8 (seeded bootstrap over tasks, 10,000 resamples). **Change from PLAN:** minimum detectable effect
  = (1.96 + 0.84)/1.96 × CI half-width ≈ 1.43 × half-width (80% power, two-sided 5%), not "2 × half-width",
  which overstated it. Also reported: within-task SD (noise between repeated runs) and between-task SD, to justify N.
- Coverage check (test): 300 simulated no-difference experiments (20 tasks × 3 trials) → CI contains 0 in
  88–99% of them (percentile bootstrap slightly under-covers with 20 tasks; noted in LIMITS).
- Cost: actual (free = $0, `configs/prices.json`) and reference (same tokens at Claude Opus 5.5 list price).

## D17 · 2026-10-18 · Three measurement bugs found by looking at a live run in the UI
1. **Provider-rejected tool calls were treated as infra failures.** Groq returns HTTP 400 "Failed to parse tool call
   arguments as JSON" when the *model* writes bad tool arguments. Marking that `invalid` and retrying hid the mistake
   and inflated the weaker model's score (it got re-rolled until it succeeded). Now: `bad_tool_args` agent error in
   the trace, the model is told, the step counts. (`ModelOutputError`.)
2. **Verdicts from too few tasks.** With 2 finished tasks the bootstrap can only take ~3 values, yet the UI showed
   "B lower" for latency. Now no verdict below 5 finished tasks ("too few tasks to judge").
3. **Latency included our rate-limit waits.** A trial with 1.3 s of model time showed 8.0 s because of Groq quota
   back-off. Trial latency now excludes retry waits (`rate_limit_wait_ms` recorded separately; `wall_ms` kept).
   Hermes's internal retries are not visible to us, so Hermes latency may still include some waiting (LIMITS).
- Lesson for DESIGN.md: inspecting real trials is part of validating the platform, not only the agents.

## D18 · 2026-10-18 · Failure analysis: rule-based, from the trace only
- Categories (PDF list + timeout + wrong_answer): timeout, step_exhaustion, loop (same call 3+ times),
  bad_tool_args, wrong_tool, grader_disagreement, gave_up_early (no tool used / no answer), wrong_answer.
- First matching rule = the category; every match is kept as a signal (a passed trial can still carry signals,
  e.g. experiment 3: csv-region-totals passed after recovering from a bad tool call).
- Why rules, not an LLM: each category points at concrete trace events a person can check; no extra cost or judge bias.
- Limit: wrong_answer is a broad bucket (e.g. skill tasks failed because the house format was unknown). A finer
  "missing knowledge" category would need task metadata; noted in LIMITS.

## D19 · 2026-10-18 · Two more fixes, done through the fix/ branch flow
- FIX-16: provider account IDs (Groq org ID in 429 messages) were stored, shown, exported and logged → scrubbed in
  runner output, API errors and logs.
- FIX-17: a running experiment executes the working tree; switching branches mid-run silently changed the code under
  experiment 2. Each trial now records `code_version`; Compare warns when it differs from the experiment's.
  Operational rule: run experiments of record from a dedicated, untouched git worktree.

## D20 · 2026-10-18 · UI: build A and B from harness × model × settings; models are data, harnesses are code
- The user found the first UI too complex. Now: Runs (home), New experiment (two builders side by side, "A → B"
  copy, "What changes" names the axes and warns when 0 or >1 differ), Models & harnesses.
- Configs built in the UI are saved automatically as `configs/<harness>-<model>-<id6>.json`; identical content reuses
  the existing file (same ID), so versioning by content hash is unchanged.
- Only the settings a harness uses are sent (Hermes has no temperature), so an unused knob never creates a fake axis.
  Same default time budget for every harness (an earlier default silently made baseline vs Hermes a 2-axis comparison).
- Models: `configs/models.json` registry; add from the UI and test with one real tool-calling request; keys stay in
  `.env` and only the variable NAME is stored (a key-looking value is rejected).
- Harnesses: cannot be added from the UI by design: a harness is an adapter (code), which is what the PDF asks to show.
  The page lists each harness, the settings it uses, its requirements, and the steps to add one.

## D21 · 2026-10-18 · Experiment 5 (baseline vs Hermes) and what its one surprise revealed
- 17 tasks × N = 3 on Gemini 3.1 Flash Lite; 36 of 102 trials lost to the daily free quota (dropped on both sides).
  Result: no detectable difference (+0.06, CI [0.00, +0.18]); Hermes ~18× tokens per trial.
- The only differing task (remember-codeword, memory off) was explained by inspection: one Hermes trial read session 1's
  prompt from Hermes's stored request dumps (a leak in our adapter → FIX-21: delete each session's home when memory is
  off), the other wrote the code word to a file in the working folder (legitimate; memory tasks measure "carry a fact
  across sessions by any means").
- No re-run, by the author's choice (no more experiments): the write-up reports the result with these caveats.
- Lesson: a single surprising per-task result is worth reading in the trace before believing it.
