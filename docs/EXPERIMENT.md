# Experiments

Two real experiments, each changing one axis. Both were started from the UI; every number below comes from the platform's
API, and each can be re-opened in the UI (section "How to check this in the UI").

| | Experiment 4: **skills off vs on** | Experiment 5: **baseline vs Hermes** |
|---|---|---|
| Axis | skills (same harness, same model) | harness (same model, same settings) |
| Model | gpt-oss-20b (Groq) | Gemini 3.1 Flash Lite |
| Tasks × N | 6 × 1 = 12 trials | 17 × 3 = 102 trials (36 invalid: daily quota) |
| Result (score) | **B better, +0.36**, 95% CI [+0.06, +0.69] | **No detectable difference, +0.06**, CI [0.00, +0.18] |
| Cost | B cheaper (−37% tokens) | Hermes **18×** the tokens per trial |
| Section | Part 1 | Part 2 |

Cost formula and figures for both: Part 3.

---

# Part 1 · Experiment 4: do skills help the same agent?

One axis changes: the skills available to the agent. Harness, model, memory, tools, limits and tasks are identical on
both sides.

## 1. Question and hypothesis

**Question.** Does giving the baseline agent three skill documents (a house release-notes format, an internal CLI
manual, a bug-ticket template) make it better, and does it change anything else?

**Hypothesis (written before the run, in the UI):** *"Skills raise the score on the 3 skill tasks and change nothing on
the 3 exact tasks."*

The exact tasks are **controls**: the skills say nothing about counting rows or summing columns, so if their scores move,
something other than the skills is driving the difference.

## 2. Setup

| | Config A (baseline) | Config B (candidate) |
|---|---|---|
| Config ID | `c4c7a5b8c36f` | `3ef0332cbf7f` |
| Harness | `baseline` | `baseline` |
| Model | `openai/gpt-oss-20b` on Groq (free tier) | same |
| **Skills** | **none** | **`bug-ticket`, `deployctl`, `release-notes`** |
| Memory | off | off |
| Tools | bash, read_file, write_file | same |
| Temperature / max steps / max tokens / timeout | 0.7 / 15 / 2000 / 300 s | same |

- **Tasks (6):** skill tasks `house-release-notes`, `register-service`, `bug-ticket`; exact tasks `count-csv-rows`,
  `sum-amounts`, `top-city`. Memory, code and judge tasks were left out: memory is off on both sides, so memory tasks
  could only fail identically, and the question is about skills.
- **Trials:** N = 1 per task and config → 12 trials. (N = 1 keeps this first UI run to ~10 minutes on Groq's free
  8k tokens/min. See section 7 for what that costs in certainty.)
- **Run:** 2026-10-18, code version `76b6e4a-dirty.9bd87438` (all 12 trials, 0 mismatches), isolation `sandbox-exec`,
  0 invalid trials.
- **Configs** are in the repo: `configs/baseline-groq-gpt-oss-20b-c4c7a5.json` and `…-3ef033.json`.

### How it was run (UI)

1. **New experiment.** A: harness `baseline`, model *gpt-oss-20b (Groq)*, memory off, no skills.
2. **A → B**, then in B select the three skill chips. "What changes" shows **skills** only (green).
3. Tasks: keep the **skill** and **exact** categories, deselect code, judge, memory → *6 tasks × 2 configs × 1 = 12 trials*.
4. Type the hypothesis, **Start experiment**, watch the progress bar.

## 3. Results

### Overall (score 0–1)

| | A (no skills) | B (skills) | B − A | 95% CI | Verdict |
|---|---|---|---|---|---|
| **Score** | 0.639 | **1.000** | **+0.361** | [+0.056, +0.694] | **B better** |

The interval excludes 0, so the improvement is unlikely to be noise. It is also wide: with 6 tasks the minimum effect
this experiment could reliably detect is about 0.46 (section 7).

### Per task

| Task | Kind | A | B | B − A |
|---|---|---|---|---|
| house-release-notes | skill | 0.00 | 1.00 | **+1.00** |
| bug-ticket | skill | 0.17 | 1.00 | **+0.83** |
| register-service | skill | 0.67 | 1.00 | **+0.33** |
| count-csv-rows | exact (control) | 1.00 | 1.00 | 0.00 |
| sum-amounts | exact (control) | 1.00 | 1.00 | 0.00 |
| top-city | exact (control) | 1.00 | 1.00 | 0.00 |

3 tasks better, 0 worse, 3 the same. **The hypothesis holds:** every gain is on a skill task and the controls did not
move.

### Quality next to cost and speed (per trial, mean)

| Metric | A | B | B − A | 95% CI |
|---|---|---|---|---|
| Tokens (in + out) | 3,508 | 2,203 | −1,305 | [−3,416, −21] |
| Latency | 3.6 s | 2.2 s | −1.3 s | [−2.7, −0.4] |
| Actual cost | $0 | $0 | $0 | free tier |
| Cost at Claude Opus 5.5 list price | $0.0243 | $0.0166 | −$0.0077 | [−$0.017, +$0.001] |

Skills made the agent **better and cheaper**, which was not in the hypothesis. The trajectories show why: without the
skill, the agent spent steps and tokens searching for a format that does not exist in its folder.

### Why A failed (failure analysis)

| Category | A | B |
|---|---|---|
| `wrong_answer` | 2 | 0 |
| `step_exhaustion` | 1 | 0 |

## 4. Trajectories that explain the difference

**1. `house-release-notes`: A searches and runs out of steps; B reads the skill and finishes in four.**
- **A (trial 61, score 0, `step_exhaustion`, also signals `loop` and `gave_up_early`):** `ls -R` five times, then
  `grep -R "RELEASE_NOTES"`, `"Release Notes"`, `"## Version"`, `"house release-notes"` across the folder and its parent.
  Nothing matches, because the format exists only in the skill. After 15 steps: no file, no answer, 8,629 input tokens.
  Grader: *"RELEASE_NOTES.md does not exist."*
- **B (trial 62, score 1):** first action `use_skill("release-notes")`, then writes
  `>>> RELEASE v2.4.0 | 2026-10-01` / `[ADD] …` / `[FIX] …` / `<<< END`. All 5 format checks pass.

**2. `register-service`: A finds the options but cannot know which one is right.**
- **A (trial 63, score 0.67, `wrong_answer`):** lists the folder, reads the `deployctl` source, sees the tiers
  (gold, silver, bronze) and runs `./deployctl register --svc billing --port 9090 --tier bronze`. Grader:
  *"PASS name billing; PASS port 9090; FAIL tier gold."* The code says which tiers exist; only the skill says that services
  handling money are `gold`.
- **B (trial 64, score 1):** `use_skill("deployctl")`, then `--tier gold`, then reads `registry.json` to confirm.

**3. `bug-ticket`: A writes a good ticket in the wrong template.**
- **A (trial 57, score 0.17, `wrong_answer`):** reads the log and writes a reasonable ticket (`# Bug Ticket: …`,
  `## Summary`). It quotes `AccessDenied` (the one check it passes) but has none of the required lines
  (`Title:`, `Severity: S1–S4`, `### Impact`, `### Repro`, `### Evidence`): 1 of 6 checks.
- **B (trial 58, score 1):** reads the log, `use_skill("bug-ticket")`, writes the exact template with `Severity: S2`.

In all three B trials the trace shows a `skill_used` event before the first write, so the skill was actually used, not
just available.

## 5. Conclusion

For this model and harness, **skills turn tasks that depend on local conventions from failures into passes (+0.36 on
average over 6 tasks, CI [+0.06, +0.69]) without affecting unrelated tasks, and they reduce tokens and latency** because
the agent stops searching for knowledge it does not have. The size of the effect is specific to tasks built to need a
skill (LIMITS: "Skill and memory tasks are built to need the capability"); the direction, and the mechanism visible in
the traces, are the transferable part.

## 6. How to check this in the UI

1. **Runs** → *skills off vs on* (experiment 4).
2. The verdict card shows **+0.361, B better** and the CI chart; **Quality, cost and speed** shows tokens and latency.
3. **Why trials failed** lists `wrong_answer` 2 and `step_exhaustion` 1, all in A.
4. **Per task:** green dots for B everywhere; red for A on `house-release-notes`, amber on `bug-ticket` and
   `register-service`. Click a dot to open the trial: score, grader reasoning, and the full trajectory. Look for the purple
   **Skill** event in B's trials.
5. **Export JSON / CSV** for the raw trials (one row per trial with config, score, failure category, tokens, cost, code version).

## 7. Caveats

- **N = 1 and 6 tasks.** Within-task noise could not be measured here (no repeats). The CI is over 6 tasks and wide; the
  minimum detectable effect was 0.46. Earlier no-skill runs of the same model (experiments 2 and 3) also failed
  `house-release-notes` and `bug-ticket`, but once **passed** `register-service` by picking `gold` without the skill:
  that task is noisy without the skill, and N = 3 would measure how noisy.
- **One model, one harness, free tier.** Whether Hermes or a stronger model gains as much from skills is a separate
  experiment.
- **Skills are made-up conventions here.** In real use, much of a skill's content may already be guessable, so gains would
  be smaller.

# Part 2 · Experiment 5: our baseline loop vs Hermes Agent, same model

## 1. Question and hypothesis

**Question.** With the same model and the same settings, does the Hermes harness (its own tools, prompt, skills and
memory machinery) solve more tasks than our minimal tool-calling loop, and at what cost?

**Hypothesis.** None was written in the UI before this run (the field was left empty), so this experiment is reported as
**exploratory**: the comparison is valid, but there was no prior prediction to confirm or refute. Experiment 4 shows the
intended practice.

## 2. Setup

| | Config A | Config B |
|---|---|---|
| Config ID | `0f96cefbac2a` | `01a1f45d36df` |
| Harness | `baseline` | **`hermes`** (Hermes Agent v0.22.2) |
| Model | `gemini-3.1-flash-lite` (Gemini free tier) | same |
| Memory / skills | off / none | off / none |
| Max steps / timeout | 15 / 300 s | same |

- **Tasks (17):** all except the 3 skill tasks (no skills on either side). Includes the 3 judge tasks (graded by the
  Gemma judge) and the 3 memory tasks (memory off on both sides).
- **Trials:** N = 3 → 102 trials, started 2026-10-18, code version `76b6e4a-dirty.bb24852b` (0 mismatches), isolation
  `sandbox-exec`.
- **36 trials invalid (18 per side):** Gemini's free daily quota ran out during the third round (HTTP 429 "exceeded your
  current quota": 34 trials of round 3, 2 of round 2). Invalid trials are dropped on both sides, so the comparison uses
  **66 valid trials, mostly 2 per task per config** (`write-readme`: 1). They were not retried, by choice: no further runs.

## 3. Results

| Metric (per trial) | A baseline | B Hermes | B − A | 95% CI | Verdict |
|---|---|---|---|---|---|
| **Score** | 0.788 | 0.847 | +0.059 | [0.000, +0.176] | **No detectable difference (could be noise)** |
| Tokens | 4,398 | 79,708 | +75,310 | [+59,270, +91,340] | Hermes much higher |
| Latency | 33.3 s | 40.3 s | +7.0 s | [−1.4, +15.5] | No detectable difference |
| Cost at Opus 5.5 list price | $0.023 | $0.326 | +$0.303 | [+$0.238, +$0.368] | Hermes higher |
| Actual cost | $0 | $0 | – | – | free tier |

- **16 of 17 tasks: identical scores.** 13 tasks solved by both every time; `incident-summary` 0.40 for both;
  `remember-csv-separator` and `remember-staging-host` 0 for both (memory off on both sides, as expected).
- **1 task differs: `remember-codeword`, A 0.00 → B 1.00.** That single task is the whole +0.059 (1/17), and it does not
  survive inspection (next section).
- Minimum detectable effect: 0.126. Noise between repeated runs (within-task SD) 0.033 vs between tasks 0.243: again,
  repeats agree with each other far more than tasks do (consistent with N = 3 being enough).
- Failures: baseline `wrong_answer` 6, `step_exhaustion` 2; Hermes `wrong_answer` 6.

## 4. Trajectories that explain the result

**1. The only "win" is not a fair one: `remember-codeword` with memory off.** Session 1 gives a code word; session 2 asks
for it. With memory off, neither agent should be able to answer from memory.
- **Hermes, trial 86 (score 1): a leak, now fixed.** In session 2 it ran `grep -r "codeword" ~` over its home folder and
  wrote `MARIGOLD-7`. Hermes stores every prompt in its home (`sessions/request_dump_*.json`, logs); with memory off each
  session had a fresh Hermes home, but session 1's home was still readable in the same trial folder. This was a bug in our
  harness adapter, found by reading this trace: **FIX-21** now deletes each session's Hermes home when memory is off, with
  a test that reproduces the leak. This trial's score should not count.
- **Hermes, trial 120 (score 1): legitimate, and informative.** In session 1 it wrote the code word into a file in the
  working folder (`release_code_word.txt`); in session 2 it listed the folder, read the file, and answered. The working
  folder deliberately persists between the sessions of one trial (like a project folder), so this is "memory" through the
  file system rather than through the memory feature. The baseline never did this; it answered from nothing and failed.
- Net: of Hermes's two successes, one was a leak and one was note-taking. The memory tasks measure "can the agent carry a
  fact across sessions by any means", not only the memory feature (now in LIMITS).

**2. Same answer, very different cost: `fix-failing-test`, trial index 0.** Both fixed the bug and passed the tests.
Baseline (trial 73): 4,522 input tokens. Hermes (trial 74): 111,592 input tokens, about 25× more, because its large system
prompt and tool definitions are sent on every model call. On `count-csv-rows` the gap was 5,863 vs 22,827.

## 5. Conclusion

On these 17 tasks with Gemini 3.1 Flash Lite, **Hermes did not solve more tasks than our minimal loop: no detectable
difference (+0.06, CI [0.00, +0.18]), and the one task that differed is explained by a leak (fixed) and by note-taking in
the shared folder.** It used **about 18× the tokens** per trial, with no detectable latency difference. On short, well-
specified tasks, the extra machinery costs a lot and buys nothing measurable; any advantage would have to show on longer
tasks or tasks that need its tools, which this task set does not contain (LIMITS). The experiment also did its other job:
inspecting the one surprising result found an isolation bug in the platform.

## 6. How to check this in the UI

**Runs** → *baseline · gemini-3.1-flash-lite vs hermes · gemini-3.1-flash-lite* (experiment 5). The verdict card shows
+0.059 and the CI touching 0; **Quality, cost and speed** shows the token gap; the progress card shows 36 invalid. In
**Per task**, `remember-codeword` is the only row with a bar; open Hermes's dots to see trials 86 and 120. Dashed red dots
are the quota-limited trials.

## 7. Caveats

- 36 of 102 trials lost to the daily quota → effectively N = 2; within-task agreement was high (SD 0.03), so the loss
  widens the CI less than it would with a noisier model.
- Most tasks were solved by both every time (ceiling): the task set cannot separate two agents that are both good at short
  tasks. A harder task set is the most useful next step.
- No hypothesis was written before the run.
- Hermes brings its own prompt and 58 bundled skills: this compares two whole packages, not two loops (LIMITS).

---

# Part 3 · Cost

### Formula

```
cost = tasks × trials_per_task × Σ_configs ( avg_input_tokens × price_in + avg_output_tokens × price_out )
```

Prices per 1M tokens. **Actual** price for free tiers and local models is $0 (`configs/prices.json`). As a real-world
reference the same tokens are also priced at **Claude Opus 5.5 list price: $4 input / $20 output** (2026-10-06).

### Experiment 4 (skills off vs on)

| Config | Trials | Input tokens | Output tokens | Actual | At Opus 5.5 list price |
|---|---|---|---|---|---|
| A (no skills) | 6 | 17,187 | 3,864 | $0 | $0.146 |
| B (skills) | 6 | 10,286 | 2,934 | $0 | $0.100 |
| **Total** | 12 | | | **$0** | **$0.246** |

Check with the formula, A: 6 × (2,865 × $4/1M + 644 × $20/1M) = 6 × ($0.0115 + $0.0129) = $0.146.

### Experiment 5 (baseline vs Hermes), actual tokens of the 66 valid trials

| Config | Valid trials | Input tokens | Output tokens | Per trial (in / out) | Actual | At Opus 5.5 list price |
|---|---|---|---|---|---|---|
| baseline | 33 | 137,605 | 10,230 | 4,170 / 310 | $0 | $0.755 |
| hermes | 33 | 2,648,760 | 14,174 | 80,265 / 430 | $0 | $10.88 |
| **Total** | 66 | | | | **$0** | **$11.63** |

Per trial at list price: baseline $0.023, Hermes $0.330 (≈ 14×). Hermes's own ~30k-token system prompt, re-sent on every
model call, is most of it. Projected for the full 102 trials (no quota cut): ≈ $18 at list price.

### How to reduce cost

- **Prompt caching.** Most of Hermes's input is the same system prompt every call; the provider already reports much of it
  as cache reads. Priced at cache rates (Opus 5.5 cache read $0.20/1M instead of $4), the Hermes estimate falls by
  roughly an order of magnitude. Our estimate prices cache reads as normal input, so it is an upper bound.
- **Early stopping.** Run trials in rounds; stop when the CI already excludes 0 (or when the remaining trials cannot
  change the verdict). Experiment 4's verdict was clear after one round.
- **Screen on a subset.** Run the cheap categories first (exact, code) and the expensive ones (judge, long Hermes tasks)
  only for configs that pass the screen.
- **Choose N from data.** Within-task SD has been small (0.04); keep N low and spend the budget on more tasks.
- **Cheaper judge.** The judge runs only on 3 tasks and uses a small free model; keep it small, validate it.
- **Do not pay for waiting.** Rate-limit retries cost no tokens; invalid trials are retried later rather than re-run blindly.
