"""Grader registry. A grader takes (spec from task.yaml, trace, sandbox dir, task) and returns a Grade.
A new grader type = one function + one line here."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..schema import Grade, Task, Trace
from .exact_match import exact_match
from .file_check import file_check
from .llm_judge import llm_judge
from .unit_tests import unit_tests

GraderFn = Callable[[dict, Trace, Path, Task], Grade]

GRADERS: dict[str, GraderFn] = {
    "exact_match": exact_match,
    "file_check": file_check,
    "unit_tests": unit_tests,
    "llm_judge": llm_judge,
}


def run_graders(specs: list[dict], trace: Trace, sandbox: Path, task: Task) -> list[Grade]:
    grades = []
    for spec in specs:
        fn = GRADERS.get(spec["type"])
        if fn is None:
            grades.append(Grade(spec["type"], 0.0, False, f"unknown grader type '{spec['type']}'"))
            continue
        grades.append(fn(spec, trace, sandbox, task))
    return grades
