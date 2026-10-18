# Open issues
<!-- open items only; closed ones move to ISSUES-CLOSED.md with their merge hash -->

## CHORE-5 · Human review of judge labels + add real agent outputs     [chore · needs-info]  parent: main
- Author reviews judge_validation/labels.json, fixes any label they disagree with, sets reviewed_by_human: true.
- After the experiment: add 5–10 real agent outputs (labelled by the author), re-run validate_judge.py.
- Check: results.json provisional == false, kappa reported in DESIGN.md.

## CHORE-8 · Linux/Docker isolation                                     [chore · ready]  parent: main
- In Docker, run agent processes as a separate unprivileged user that cannot read tasks/*/reference or tests.
- Check: isolation attack tests pass inside the container.

## DOCS-20 · Deliverables: README, DESIGN, LIMITS, EXPERIMENT (+ cost)      [chore · in-progress]  parent: main
- README: setup, running an experiment from the UI, adding a model / harness / task.
- docs/DESIGN.md: architecture, adapter interfaces, data model, isolation + reproducibility, graders + validation, statistics + choice of N.
- docs/LIMITS.md: where conclusions should not be trusted.
- docs/EXPERIMENT.md: experiment 4 (skills off vs on): hypothesis, setup, results with CI, trajectories, conclusion, cost.
- Written in a separate worktree (../assignment-docs) because experiment 5 is running on the main working tree.
- Branch: docs/deliverables

