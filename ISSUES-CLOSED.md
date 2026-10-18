# Closed issues
<!-- append-only. Each entry: what, branch, merge commit, evidence. Entries marked "flow skipped" are
     retroactive records of fixes that landed on a feature branch instead of their own fix/ branch. -->

## PLAN-2 · Re-plan for free providers                      [chore · closed]
- Branch: chore/replan-free-providers · merge 4476f38 · Evidence: PLAN.md v2, .env verified gitignored.

## SPIKE-1 · Provider and Hermes spikes                      [chore · closed]
- Branch: feat/spikes · merge 9bc3f9b · Evidence: DECISIONS D6–D9.

## FEAT-3 · Provider for Hermes experiments                  [chore · closed]
- Commit 1970c4a on feat/runner-core · Evidence: DECISIONS D10 (account rate-limit screenshots).

## FEAT-1 · Runner core                                      [feature · closed]
- Branch: feat/runner-core · merge bcfddfb · Evidence: pytest, mock trial end to end.

## FEAT-2 · Baseline harness + model adapter                 [feature · closed]
- Branch: feat/runner-core · merge bcfddfb · Evidence: 14 pytest; real trial 1.0 on Groq and local.

## FEAT-4 · Graders + 20 tasks + judge validation            [feature · closed]
- Branch: feat/graders-tasks · merge fa1f802 · Evidence: 54 pytest; validate_judge kappa 1.00 (provisional).

## FIX-13 · Judge model gemma-4-31b hangs                     [bug · closed · flow skipped]
- Fix landed in feature commit 8e74a00 on feat/graders-tasks (config switch to gemma-4-26b-a4b-it), not on its own fix/ branch.
- Evidence: 31b no response in 45–120 s (curl), 26b ~2 s; DECISIONS D11.

## FEAT-6 · Hermes adapter                                   [feature · closed]
- Branch: feat/hermes-adapter · merge (see "Merge feat/hermes-adapter") · Evidence: 65 pytest.

## FIX-14 · Agent escapes folder isolation; secrets in traces; crashes scored as 0   [bug · closed · flow skipped]
- Found while verifying the Hermes adapter; the bug was in runner code already on main. Fix landed in feature
  commit e982f11 on feat/hermes-adapter, mixed with the adapter, not on its own fix/ branch.
- Evidence: tests/test_isolation.py replays each attack and fails with the sandbox disabled; DECISIONS D14.

## FEAT-7 · API: experiments, scheduler, stats, export       [feature · closed]
- Branch: feat/api-stats · merge a093b62 · Evidence: 9 jest + 65 pytest; live HTTP experiment.

## FIX-10 · Provider-rejected tool calls treated as infra failures   [bug · closed · flow skipped]
- Code on main (runner-core). Fix commit 792afdf is separate but sits on feat/web-ui, not its own fix/ branch.
- Evidence: new tests in test_models.py and test_baseline.py; DECISIONS D17.1.

## FIX-15 · Verdict from fewer than 5 tasks; latency includes rate-limit waits   [bug · closed · flow skipped]
- Code on main (api-stats, runner). Fix was mixed into feature commit f5df1e6 on feat/web-ui.
- Evidence: stats.spec.ts (too few tasks), test_models.py (waited_ms); DECISIONS D17.2–3.

## FEAT-9 · UI                                               [feature · closed]
- Branch: feat/web-ui · merge (see "Merge feat/web-ui") · Evidence: build + screenshots of all pages, light and dark.

## CHORE-12 · Retroactive issue records                      [chore · closed]
- Branch: chore/12-retro-issue-records · this file. From now on: the stop-trigger in change-flow (agent-system CF-3).

## FEAT-11 · Failure analysis: categories from the trace                [feature · closed]  parent: main
- Categories (PDF): wrong tool, hallucinated tool args, gave up early, loop / step exhaustion, grader disagreement (+ timeout).
- Check: unit tests per rule on synthetic traces; Compare page shows counts per config; Trial page shows the category.
- Branch: feat/failure-analysis
- Branch feat/failure-analysis · Evidence: 79 pytest (one test per rule), 12 jest; experiment 3: every failed trial categorised.

## FIX-16 · Provider account IDs stored in trial errors and exports      [bug · closed]  parent: main
- Repro: experiment 1, trial 8 error: Groq 429 message contains "organization `org_…`"; stored in trials.error, shown in UI, exported to CSV/JSON.
- Check: run_trial output and API-stored errors contain no org_/account IDs (test with the real message shape).
- Branch: fix/16-scrub-account-ids
- Branch fix/16-scrub-account-ids · merge 9ab6c6f · Evidence: test with real 429 shape fails before, passes after.

## FIX-17 · Experiment code can change mid-run (trials run on the working tree)   [bug · closed]  parent: main
- Repro: experiment 2: switching to fix/16 while it ran made 2 trials run without failures.py (failure_category null).
  experiments.code_sha is taken once at creation, so this is invisible in results.
- Check: each trial records the code version it ran on; Compare flags trials whose version differs from the
  experiment's. Operational rule in README/LIMITS: run experiments of record from a dedicated git worktree.
- Branch: fix/17-code-version-per-trial
- Branch fix/17-code-version-per-trial · Evidence: jest mismatch 0 then 1; experiment 3 all trials on 63b8c0c, mismatch 0.

## FEAT-18 · Simpler UI: A/B config builders, model registry, harness list   [feature · closed]  parent: main
- A and B each choose harness × model × settings independently; configs saved automatically (content-hash ID kept).
- Models page: add an OpenAI-compatible model from the UI and test the connection; harnesses listed with what they support and how to add one (code).
- Home = runs list; new experiment on its own page; advanced settings folded.
- Check: create an experiment from two built configs end to end (API test); screenshots of every page, light + dark.
- Branch: feat/ui-config-builder
- Branch feat/ui-config-builder · Evidence: 79 pytest, 15 jest, web build; screenshots of Runs, New experiment, Models & harnesses (light + dark).

## FIX-19 · Runs list shows "running" for finished experiments              [bug · closed]  parent: main
- Repro: experiment 1 (32/32 finished, 1 invalid) listed as "running" on Home; status only updates when the experiment itself is opened (get()).
- Check: list() reports done for every experiment with no pending/running trials (API test).
- Branch: fix/19-stale-experiment-status
- Branch fix/19-stale-experiment-status · Evidence: test fails before, passes after.

## DOCS-20 · Deliverables: README, DESIGN, LIMITS, EXPERIMENT (+ cost)      [chore · closed]  parent: main
- README: setup, running an experiment from the UI, adding a model / harness / task.
- docs/DESIGN.md: architecture, adapter interfaces, data model, isolation + reproducibility, graders + validation, statistics + choice of N.
- docs/LIMITS.md: where conclusions should not be trusted.
- docs/EXPERIMENT.md: experiment 4 (skills off vs on): hypothesis, setup, results with CI, trajectories, conclusion, cost.
- Written in a separate worktree (../assignment-docs) because experiment 5 is running on the main working tree.
- Branch: docs/deliverables
- Evidence: no private data in docs (grep), all internal links resolve, retry/lane/grader claims checked against code; numbers from the API for experiments 1, 4, 5.

## FIX-21 · Hermes memory OFF leaks session 1 into session 2 (prompts stored in its home)   [bug · closed]  parent: main
- Repro: experiment 5, trial 86 (hermes, memory off, remember-codeword): session 2 ran `grep -r codeword ~` and wrote
  MARIGOLD-7. Hermes stores every prompt in its home (sessions/request_dump_*.json, spawn-ledger.json, logs/agent.log);
  memory off gives each session a fresh home, but session 1's home stays readable inside the same trial folder.
- Check: test with a fake hermes binary: in session 2 no other Hermes home exists; fails on the old code.
- Branch: fix/21-hermes-memory-off-leak
- Branch fix/21-hermes-memory-off-leak · Evidence: fake-hermes test fails before (secret visible in session 2), passes after; 80 pytest.

## FIX-22 · validate_judge.py fails: does not load .env                     [bug · closed]  parent: main
- Repro: `cd runner && uv run python ../judge_validation/validate_judge.py` → ProviderError "env var GEMINI_API_KEY is not set"
  (the API loads .env itself; the script did not, and the README did not say to).
- Check: the script loads the repo's .env when present; run as documented, it reaches the judge.
- Branch: fix/22-validate-judge-env
- Branch fix/22-validate-judge-env · Evidence: before = the author's run (ProviderError); after = same command with GEMINI_API_KEY unset in the shell: judge runs, 15 items, accuracy 1.00, kappa 1.00.

## FIX-23 · apps/api package-lock.json out of sync with package.json      [bug · closed]  parent: main
- Repro: `npm ci` (clean install, as in the Docker build) fails: "lock file's @emnapi/wasi-threads@1.2.1 does not satisfy 1.2.3",
  missing @emnapi/core, @emnapi/runtime. Stale since the NestJS 12 -> 11 pin (D16); local `npm install` tolerated it.
- Check: `npm ci` succeeds on a clean copy with npm 11 (local) and npm 10 (node:22 image).
- Branch: fix/23-api-lockfile
- Branch fix/23-api-lockfile · Evidence: npm ci on a clean copy: before fails (npm 11 and 10); after passes with npm 11.6.2 locally and in node:22 with npm 11.6.2. Lock is npm-11 format; package.json now declares engines npm >= 11. 15 jest pass.

## FIX-24 · Hermes leak test depends on the machine having a prepared Hermes base      [bug · closed]  parent: main
- Repro: in a fresh container, tests/test_hermes.py::test_memory_off_session_2_cannot_read_session_1 fails with
  "could not prepare Hermes base home": the fake hermes binary cannot prepare the base; on the dev Mac the real base
  already existed, so the test passed by accident.
- Check: the test uses its own temporary prepared base; passes on the Mac and inside the container.
- Branch: fix/24-hermes-test-base
- Branch fix/24-hermes-test-base · Evidence: before, fails in a fresh container (no prepared base; then fake binary not executable by the unprivileged agent); after, 80/80 on the Mac and 80/80 inside the container.

## CHORE-8 · Docker (`docker compose up`) with agent isolation           [chore · closed]  parent: main
- In Docker, run agent processes as a separate unprivileged user that cannot read tasks/*/reference or tests.
- Check: isolation attack tests pass inside the container.
- Branch feat/docker · Evidence: fresh clone of feat/docker, `docker compose up --build`: health ok, UI 200, isolation unprivileged-user, 80/80 pytest in container; real trials: baseline (Groq) 1.0, Hermes (Gemini 3.5 Flash Lite) 1.0, both unprivileged-user.
