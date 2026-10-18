# Open issues
<!-- open items only; closed ones move to ISSUES-CLOSED.md with their merge hash -->

## CHORE-5 · Human review of judge labels + add real agent outputs     [chore · needs-info]  parent: main
- Author reviews judge_validation/labels.json, fixes any label they disagree with, sets reviewed_by_human: true.
- After the experiment: add 5–10 real agent outputs (labelled by the author), re-run validate_judge.py.
- Check: results.json provisional == false, kappa reported in DESIGN.md.

## CHORE-8 · Docker (`docker compose up`) with agent isolation           [chore · in-progress]  parent: main
- In Docker, run agent processes as a separate unprivileged user that cannot read tasks/*/reference or tests.
- Check: isolation attack tests pass inside the container.

## FIX-22 · validate_judge.py fails: does not load .env                     [bug · in-progress]  parent: main
- Repro: `cd runner && uv run python ../judge_validation/validate_judge.py` → ProviderError "env var GEMINI_API_KEY is not set"
  (the API loads .env itself; the script did not, and the README did not say to).
- Check: the script loads the repo's .env when present; run as documented, it reaches the judge.
- Branch: fix/22-validate-judge-env

