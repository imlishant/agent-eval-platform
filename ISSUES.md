# Open issues
<!-- open items only; closed ones live in the merge commit that said `Closes <id>` -->

## CHORE-5 · Human review of judge labels + add real agent outputs     [chore · needs-info]  parent: main
- Author reviews judge_validation/labels.json, fixes any label they disagree with, sets reviewed_by_human: true.
- After the experiment: add 5–10 real agent outputs (labelled by the author), re-run validate_judge.py.
- Check: results.json provisional == false, kappa reported in DESIGN.md.

## FEAT-7 · API: NestJS + SQLite, experiments, worker pool, retries of invalid trials, stats, export   [feature · ready]  parent: main
- Check: create experiment via API → trials run (pool per provider) → paired bootstrap CI + per-task deltas → JSON/CSV export; stats unit tests (hand example, no-difference simulation).
- Branch: feat/api-stats

## CHORE-8 · Linux/Docker isolation                                     [chore · ready]  parent: main
- In Docker, run agent processes as a separate unprivileged user that cannot read tasks/*/reference or tests.
- Check: isolation attack tests pass inside the container.
