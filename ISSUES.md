# Open issues
<!-- open items only; closed ones live in the merge commit that said `Closes <id>` -->

## CHORE-5 · Human review of judge labels + add real agent outputs     [chore · needs-info]  parent: main
- Author reviews judge_validation/labels.json, fixes any label they disagree with, sets reviewed_by_human: true.
- After the experiment: add 5–10 real agent outputs (labelled by the author), re-run validate_judge.py.
- Check: results.json provisional == false, kappa reported in DESIGN.md.

## FEAT-6 · Hermes adapter                                              [feature · ready]  parent: main
- Check: one task end to end with harness=hermes on Gemini; trace has tool_call/tool_result; memory on/off works across 2 sessions.
