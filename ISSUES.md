# Open issues
<!-- open items only; closed ones move to ISSUES-CLOSED.md with their merge hash -->

## CHORE-5 · Human review of judge labels + add real agent outputs     [chore · needs-info]  parent: main
- Author reviews judge_validation/labels.json, fixes any label they disagree with, sets reviewed_by_human: true.
- After the experiment: add 5–10 real agent outputs (labelled by the author), re-run validate_judge.py.
- Check: results.json provisional == false, kappa reported in DESIGN.md.

## CHORE-8 · Linux/Docker isolation                                     [chore · ready]  parent: main
- In Docker, run agent processes as a separate unprivileged user that cannot read tasks/*/reference or tests.
- Check: isolation attack tests pass inside the container.

## FEAT-18 · Simpler UI: A/B config builders, model registry, harness list   [feature · in-progress]  parent: main
- A and B each choose harness × model × settings independently; configs saved automatically (content-hash ID kept).
- Models page: add an OpenAI-compatible model from the UI and test the connection; harnesses listed with what they support and how to add one (code).
- Home = runs list; new experiment on its own page; advanced settings folded.
- Check: create an experiment from two built configs end to end (API test); screenshots of every page, light + dark.
- Branch: feat/ui-config-builder

