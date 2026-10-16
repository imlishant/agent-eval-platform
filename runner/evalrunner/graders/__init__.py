"""Grader registry. A grader takes (spec from task.yaml, trace, sandbox dir) and returns a Grade."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..schema import Grade, Trace
from .exact_match import exact_match

GraderFn = Callable[[dict, Trace, Path], Grade]

GRADERS: dict[str, GraderFn] = {
    "exact_match": exact_match,
}


def run_graders(specs: list[dict], trace: Trace, sandbox: Path) -> list[Grade]:
    grades = []
    for spec in specs:
        fn = GRADERS.get(spec["type"])
        if fn is None:
            grades.append(Grade(spec["type"], 0.0, False, f"unknown grader type '{spec['type']}'"))
            continue
        grades.append(fn(spec, trace, sandbox))
    return grades
