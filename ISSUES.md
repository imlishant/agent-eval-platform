# Open issues
<!-- open items only; closed ones move to ISSUES-CLOSED.md with their merge hash -->

## CHORE-5 · Human review of judge labels + add real agent outputs     [chore · needs-info]  parent: main
- Author reviews judge_validation/labels.json, fixes any label they disagree with, sets reviewed_by_human: true.
- After the experiment: add 5–10 real agent outputs (labelled by the author), re-run validate_judge.py.
- Check: results.json provisional == false, kappa reported in DESIGN.md.

## CHORE-8 · Linux/Docker isolation                                     [chore · ready]  parent: main
- In Docker, run agent processes as a separate unprivileged user that cannot read tasks/*/reference or tests.
- Check: isolation attack tests pass inside the container.

## FIX-24 · Hermes leak test depends on the machine having a prepared Hermes base      [bug · in-progress]  parent: main
- Repro: in a fresh container, tests/test_hermes.py::test_memory_off_session_2_cannot_read_session_1 fails with
  "could not prepare Hermes base home": the fake hermes binary cannot prepare the base; on the dev Mac the real base
  already existed, so the test passed by accident.
- Check: the test uses its own temporary prepared base; passes on the Mac and inside the container.
- Branch: fix/24-hermes-test-base

