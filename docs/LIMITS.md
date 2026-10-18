# Known limits

Where this platform's conclusions should **not** be trusted, or only with care. Each item says what the limit is, how it
can mislead, and what we do about it. Evidence and dates are in [DECISIONS.md](DECISIONS.md).

## Statistics and task set

- **20 tasks detect only large effects.** The confidence interval is over tasks, so its width is driven by how many tasks
  there are. With 6 tasks (experiment 4) the minimum detectable effect was 0.46 on a 0–1 score; with all 20 tasks expect
  roughly 0.15–0.25. Smaller real improvements will show up as "no detectable difference". The UI prints the minimum
  detectable effect next to every verdict for this reason. "No difference" means "no difference larger than that".
- **N = 3 is chosen for quota, not optimised.** Measured within-task noise was small (SD 0.04 vs 0.18 between tasks),
  which supports few repeats, but that was measured on two models over 8 tasks. A less deterministic model or harness
  needs more trials; check the within-task SD on each comparison.
- **The percentile bootstrap slightly under-covers** with few tasks: in simulation, the 95% interval contained the true
  "no difference" in 88–99% of experiments. Treat borderline intervals (an end close to 0) as inconclusive.
- **Scores average graders with partial credit.** A `file_check` that passes 4 of 6 checks scores 0.67. Averages of
  partial credit are easier to move than pass rates; the per-task table and the pass/fail status are shown so both readings
  are available.
- **No correction for multiple comparisons.** Score, tokens, latency and two costs each get their own 95% CI. Running many
  experiments and reporting the one that "worked" will find false wins.
- **Task categories are small (3 tasks each for skill, memory, judge, exact).** A per-category conclusion ("memory
  helps on memory tasks") rests on three tasks; treat it as illustrative, not measured.

## Tasks and graders

- **Tasks were written by one author** (with an AI assistant), with known reference solutions. They reflect what that
  author thought was representative; they are short (1–15 steps) and synthetic. Results say little about long,
  open-ended work.
- **Contamination.** Tasks were written for this project and the skill tasks use made-up formats, which reduces the
  chance that a model memorised them. It does not remove it: CSV counting, FizzBuzz, slugify and pagination bugs are
  common in training data, so the code and exact tasks may overstate general ability. The repo is public; future models
  may train on it.
- **Memory tasks can be solved without the memory feature.** The working folder persists between the two sessions of a
  trial (like a project folder), so an agent can write the fact to a file in session 1 and read it in session 2. Hermes
  did exactly that in experiment 5. The memory tasks therefore measure "carries a fact across sessions by any means".
- **Ceiling effect.** In experiment 5 both agents solved 13 of 17 tasks every time. Short, well-specified tasks cannot
  separate two capable agents; harder or longer tasks are needed to compare harnesses.
- **Skill and memory tasks are built to need the capability.** They show *whether* a skill or memory can be used, not how
  much it helps on real work. A large effect on these tasks is expected by design.
- **`wrong_answer` is a broad failure bucket.** "Did not know the house format" and "made an arithmetic error" both land
  there. Finer causes would need per-task metadata.

## The LLM judge

- **Validated on 15 examples written for the purpose, labels not yet human-reviewed.** Accuracy 1.00 and kappa 1.00 are
  provisional and almost certainly optimistic: the examples are cleaner than real agent output. Real agent outputs
  labelled by the author still have to be added (open issue CHORE-5).
- **Biases not controlled for:** length (longer answers can satisfy more criteria), phrasing, and the judge's own
  knowledge. The judge is a different model family from the models under test, which removes self-preference, not the
  rest. Temperature 0 makes it repeatable, not correct.
- **Rubric criteria are yes/no and written by the task author**; a criterion like "no facts absent from the source" is
  hard for any judge to check exhaustively.
- Only 3 of 20 tasks use the judge, so its errors move the headline number little; they move per-task conclusions on
  those three a lot.

## Models and providers

- **Free tiers, not the models that would be used in production.** Experiments use Gemini Flash Lite, gpt-oss on Groq and
  a local 8B model. Conclusions about these models do not transfer to frontier models.
- **Rate limits shape what can be run.** Gemini free: 500 requests/day/model, 250k tokens/min; Groq free: 8k tokens/min.
  Rate-limited trials are retried and, if still failing, marked `invalid` and dropped from both sides. If invalid trials
  cluster on one kind of task (e.g. the longest ones), the comparison is biased toward short tasks; the invalid count is
  shown for this reason.
- **Hosted models change silently.** A provider can update the model behind the same id; results carry the date and
  model id, but a re-run months later may not match.
- **Provider quirks can look like agent behaviour.** Example found: Groq rejects malformed tool-call JSON with an HTTP
  400 instead of returning it; this is now counted as the agent's `bad_tool_args`, but other providers may differ.
- **Latency is noisy.** It excludes our own rate-limit waits, but includes provider queueing and network time. Hermes
  reports one total per session and retries internally, so its latency can include waiting we cannot see.

## Harness-specific quirks (cross-harness comparisons include these differences)

- **Hermes brings its own ~30k-token system prompt and 58 bundled skills** on every call; our skills are added on top.
  "Hermes vs baseline" therefore compares two whole packages (prompt, tools, skills), not only the loop. Its token use is
  much higher by design (about 22× the baseline's input tokens per trial in the partial data of experiment 5).
- **Hermes has no temperature setting**; baseline uses 0.7. The UI hides settings a harness does not use, but the
  sampling difference is part of any Hermes vs baseline comparison.
- **Memory is implemented differently.** Baseline: a `memory.md` file loaded into the prompt, written by a tool. Hermes:
  its own memory files and tools, plus searchable session history. Memory "off" for Hermes = a fresh Hermes home per
  session, because with memory disabled it could still search the previous session's transcript.
- **Hermes needs ≥ 64k context**, so it cannot run on the local 8B model; Hermes and baseline can only be compared on
  models both support.
- **A memory-off leak affected experiment 5.** Hermes writes every prompt into its home folder; with memory off, session 1's
  home stayed readable from session 2 and one trial used it (trial 86). Fixed after the run (FIX-21: the home is deleted
  after each session). Experiment 5's one differing task is reported with this caveat; other harnesses that keep
  transcripts on disk need the same care.
- **Hermes can create skills** during a run; skills and memory are reset per trial, so this cannot leak between trials,
  but it can help within a trial.
- **Tool sets differ.** Baseline has three tools; Hermes has many (terminal, search, file tools, memory, and more).
  In single-query mode Hermes blocks `execute_code`; we do not use `--yolo`.

## Isolation and reproducibility

- **Two isolation mechanisms.** macOS: `sandbox-exec` profile. Docker (Linux, as root): each trial's agent runs as its own
  unprivileged user ID with a mode-700 trial folder; answer keys are root-only. Elsewhere trials run with folder isolation
  only and record `isolation: folder-only`, which is not enough against an agent with a terminal (one copied a reference
  answer in testing).
- **In Docker, agents share a group that can write the prepared Hermes base** (Hermes needs lock files there), so a
  malicious agent could alter the Hermes install used by later trials. The macOS profile allows only lock/lease files.
- **Docker was verified on one machine** (OrbStack, Apple Silicon, arm64). An x86-64 host builds the same Dockerfile but was
  not tested; the native module (better-sqlite3) and Hermes install are the parts most likely to differ.
- **Ollama inside Docker** is reached at `host.docker.internal`; the pre-registered local model uses `localhost` and needs a
  model entry with the other base URL.
- **The sandbox allows network access** (the agent needs the model API). An agent could reach the internet with its
  terminal; none of the tasks rewards that, but it is not prevented.
- **Experiments run on the working tree.** If the code changes during a run, trials disagree with the experiment's code
  version; Compare warns, but the results of those trials are still mixed in. Run experiments of record from a
  dedicated git worktree that nobody edits.
- **Model outputs are not reproducible**, only the conditions are (config snapshot, task hash, code version, harness
  version). Re-running gives a new sample, not the same answers.

## Cost figures

- **Actual spend is $0** (free tiers, local model). The "reference cost" prices the same token counts at Claude Opus 5.5
  list prices ($4 / $20 per 1M input / output tokens, as of 2026-10-06). It shows scale, not what Claude would actually
  do: a different model would use a different number of tokens and steps. Cached input is priced as normal input, which
  overstates Hermes's cost (much of its prompt is cache reads).
