# Open issues
<!-- open items only; closed ones move to ISSUES-CLOSED.md with their merge hash -->

## CHORE-5 · Human review of judge labels + add real agent outputs     [chore · needs-info]  parent: main
- Author reviews judge_validation/labels.json, fixes any label they disagree with, sets reviewed_by_human: true.
- After the experiment: add 5–10 real agent outputs (labelled by the author), re-run validate_judge.py.
- Check: results.json provisional == false, kappa reported in DESIGN.md.

## CHORE-8 · Linux/Docker isolation                                     [chore · ready]  parent: main
- In Docker, run agent processes as a separate unprivileged user that cannot read tasks/*/reference or tests.
- Check: isolation attack tests pass inside the container.

## FIX-23 · apps/api package-lock.json out of sync with package.json      [bug · in-progress]  parent: main
- Repro: `npm ci` (clean install, as in the Docker build) fails: "lock file's @emnapi/wasi-threads@1.2.1 does not satisfy 1.2.3",
  missing @emnapi/core, @emnapi/runtime. Stale since the NestJS 12 -> 11 pin (D16); local `npm install` tolerated it.
- Check: `npm ci` succeeds on a clean copy with npm 11 (local) and npm 10 (node:22 image).
- Branch: fix/23-api-lockfile

