# Open issues
<!-- open items only; closed ones move to ISSUES-CLOSED.md with their merge hash -->

## CHORE-5 · Human review of judge labels + add real agent outputs     [chore · needs-info]  parent: main
- Author reviews judge_validation/labels.json, fixes any label they disagree with, sets reviewed_by_human: true.
- After the experiment: add 5–10 real agent outputs (labelled by the author), re-run validate_judge.py.
- Check: results.json provisional == false, kappa reported in DESIGN.md.

## CHORE-8 · Linux/Docker isolation                                     [chore · ready]  parent: main
- In Docker, run agent processes as a separate unprivileged user that cannot read tasks/*/reference or tests.
- Check: isolation attack tests pass inside the container.

## FIX-21 · Hermes memory OFF leaks session 1 into session 2 (prompts stored in its home)   [bug · in-progress]  parent: main
- Repro: experiment 5, trial 86 (hermes, memory off, remember-codeword): session 2 ran `grep -r codeword ~` and wrote
  MARIGOLD-7. Hermes stores every prompt in its home (sessions/request_dump_*.json, spawn-ledger.json, logs/agent.log);
  memory off gives each session a fresh home, but session 1's home stays readable inside the same trial folder.
- Check: test with a fake hermes binary: in session 2 no other Hermes home exists; fails on the old code.
- Branch: fix/21-hermes-memory-off-leak

