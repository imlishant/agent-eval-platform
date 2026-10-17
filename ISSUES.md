# Open issues
<!-- open items only; closed ones live in the merge commit that said `Closes <id>` -->

## CHORE-5 · Human review of judge labels + add real agent outputs     [chore · needs-info]  parent: main
- Author reviews judge_validation/labels.json, fixes any label they disagree with, sets reviewed_by_human: true.
- After the experiment: add 5–10 real agent outputs (labelled by the author), re-run validate_judge.py.
- Check: results.json provisional == false, kappa reported in DESIGN.md.

## FEAT-9 · UI (Vue 3): Run, Compare, Trial pages                       [feature · ready]  parent: main
- Check: define/pick configs, start run with progress; Compare shows verdict + CI + per-task deltas + cost/latency/tokens + export; click a failed trial → full trace and grader reasoning.
- Branch: feat/web-ui

## CHORE-8 · Linux/Docker isolation                                     [chore · ready]  parent: main
- In Docker, run agent processes as a separate unprivileged user that cannot read tasks/*/reference or tests.
- Check: isolation attack tests pass inside the container.
