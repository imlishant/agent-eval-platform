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
