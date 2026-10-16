"""exact_match: the agent's final answer must equal `expected` (after trimming).

task.yaml:
  - type: exact_match
    expected: "37"
    case_sensitive: false   # optional, default false
    session: 2              # optional, default = last answer of the trial
"""

from __future__ import annotations

from pathlib import Path

from ..schema import Grade, Task, Trace


def exact_match(spec: dict, trace: Trace, sandbox: Path, task: Task) -> Grade:
    expected = str(spec["expected"]).strip()
    got = trace.final_answer(spec.get("session")).strip()
    if not spec.get("case_sensitive", False):
        expected_cmp, got_cmp = expected.lower(), got.lower()
    else:
        expected_cmp, got_cmp = expected, got
    ok = got_cmp == expected_cmp
    return Grade("exact_match", 1.0 if ok else 0.0, ok,
                 f"expected {expected!r}, got {got[:200]!r}")
