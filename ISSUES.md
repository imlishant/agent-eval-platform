# Open issues
<!-- open items only; closed ones move to ISSUES-CLOSED.md with their merge hash -->

## CHORE-5 · Human review of judge labels + add real agent outputs     [chore · needs-info]  parent: main
- Author reviews judge_validation/labels.json, fixes any label they disagree with, sets reviewed_by_human: true.
- After the experiment: add 5–10 real agent outputs (labelled by the author), re-run validate_judge.py.
- Check: results.json provisional == false, kappa reported in DESIGN.md.

## FEAT-11 · Failure analysis: categories from the trace                [feature · in-progress]  parent: main
- Categories (PDF): wrong tool, hallucinated tool args, gave up early, loop / step exhaustion, grader disagreement (+ timeout).
- Check: unit tests per rule on synthetic traces; Compare page shows counts per config; Trial page shows the category.
- Branch: feat/failure-analysis

## CHORE-8 · Linux/Docker isolation                                     [chore · ready]  parent: main
- In Docker, run agent processes as a separate unprivileged user that cannot read tasks/*/reference or tests.
- Check: isolation attack tests pass inside the container.

## FIX-16 · Provider account IDs stored in trial errors and exports      [bug · in-progress]  parent: main
- Repro: experiment 1, trial 8 error: Groq 429 message contains "organization `org_…`"; stored in trials.error, shown in UI, exported to CSV/JSON.
- Check: run_trial output and API-stored errors contain no org_/account IDs (test with the real message shape).
- Branch: fix/16-scrub-account-ids

## FIX-17 · Experiment code can change mid-run (trials run on the working tree)   [bug · ready]  parent: main
- Repro: experiment 2: switching to fix/16 while it ran made 2 trials run without failures.py (failure_category null).
  experiments.code_sha is taken once at creation, so this is invisible in results.
- Check: each trial records the code version it ran on; Compare flags trials whose version differs from the
  experiment's. Operational rule in README/LIMITS: run experiments of record from a dedicated git worktree.
- Branch: fix/17-code-version-per-trial

