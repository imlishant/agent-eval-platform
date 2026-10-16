# Open issues
<!-- open items only; closed ones live in the merge commit that said `Closes <id>` -->

## FEAT-1 · Runner core: schemas, sandbox, mock harness, exact grader      [feature · in-progress]  parent: main
- Goal: `python -m evalrunner.run_trial` runs 1 task with the mock harness and prints {trace, grades, score} JSON.
- Check: pytest — mock "solve" scores 1, mock "fail" scores 0, sandbox is fresh per trial.
- Branch: feat/runner-core

## FEAT-2 · Baseline harness + OpenAI-compatible model adapter               [feature · ready]  parent: main
- Check: real model (Groq/local) solves the sample task; trace has model_call/tool_call/tool_result; 429 retried.

## FEAT-3 · Model provider for Hermes experiments                              [chore · needs-info]  parent: main
- Gemini 2.5 Flash/Flash-Lite free = 20 requests/day: too low for 120 trials. Candidates: Mistral free tier; other Gemini rows (3.x, Gemma).
