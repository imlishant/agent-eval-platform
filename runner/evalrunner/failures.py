"""Failure analysis: put each failed trial into one category, from its trace and grades alone.

Rule-based on purpose: every category points at concrete events, so a person can check it in the
trial view. Rules are checked in order; the first match is the category, every match is kept as a signal.

  timeout             the trial hit its time limit
  step_exhaustion     the agent used all its steps without finishing
  loop                the same tool call (name + arguments) repeated 3+ times
  bad_tool_args       the agent called a tool with invalid or missing arguments (hallucinated args)
  wrong_tool          the agent called a tool that does not exist
  grader_disagreement two graders on the same trial disagree (one passes, one fails)
  gave_up_early       the agent answered without using any tool (a guess), or gave no answer at all
  wrong_answer        it finished normally, but the result is wrong
"""

from __future__ import annotations

import json
import re
from collections import Counter

from .schema import Grade, Trace

CATEGORIES = ["timeout", "step_exhaustion", "loop", "bad_tool_args", "wrong_tool",
              "grader_disagreement", "gave_up_early", "wrong_answer"]

BAD_ARGS = re.compile(r"not valid JSON|missing required argument|invalid argument|validation failed|"
                      r"required property|unexpected keyword", re.I)
UNKNOWN_TOOL = re.compile(r"unknown tool|no such tool|tool .* not found|not a valid tool", re.I)
OUT_OF_STEPS = re.compile(r"ran out of steps|max(imum)?[ -]turns|iteration (limit|budget)", re.I)


def classify(trace: Trace, grades: list[Grade]) -> dict:
    """{'category': str | None, 'signals': [str, ...]}. category is None when the trial passed."""
    events = trace.events
    errors = [e.payload for e in events if e.type == "error"]
    calls = [e.payload for e in events if e.type == "tool_call"]
    results = [e.payload for e in events if e.type == "tool_result"]
    answers = [e.payload.get("text", "") for e in events if e.type == "final_answer"]
    signals: list[str] = []

    if any(e.get("kind") == "timeout" for e in errors):
        signals.append("timeout")
    if any(e.get("kind") == "step_exhaustion" for e in errors) or any(OUT_OF_STEPS.search(a) for a in answers):
        signals.append("step_exhaustion")
    repeats = Counter(f"{c.get('name')}:{json.dumps(c.get('args'), sort_keys=True)}" for c in calls)
    if repeats and max(repeats.values()) >= 3:
        signals.append("loop")
    if any(e.get("kind") == "bad_tool_args" for e in errors) or \
            any(r.get("is_error") and BAD_ARGS.search(str(r.get("output", ""))) for r in results):
        signals.append("bad_tool_args")
    if any(r.get("is_error") and UNKNOWN_TOOL.search(str(r.get("output", ""))) for r in results):
        signals.append("wrong_tool")
    if len({g.passed for g in grades}) > 1:
        signals.append("grader_disagreement")
    if not calls or not any(a.strip() for a in answers):
        signals.append("gave_up_early")

    passed = bool(grades) and all(g.passed for g in grades)
    if passed:
        return {"category": None, "signals": signals}
    for cat in CATEGORIES:
        if cat in signals:
            return {"category": cat, "signals": signals}
    return {"category": "wrong_answer", "signals": signals}
