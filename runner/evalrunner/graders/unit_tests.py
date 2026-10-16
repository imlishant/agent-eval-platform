"""unit_tests: run the task's own tests against the agent's work. Pass = exit code 0.

task.yaml:
  - type: unit_tests
    command: "python -m pytest -q tests"

The tests come from the task folder (tasks/<id>/tests/), copied over the sandbox's tests/
right before grading, so an agent that edits or deletes the tests cannot fake a pass.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ..schema import Grade, Task, Trace

TIMEOUT_S = 60


def unit_tests(spec: dict, trace: Trace, sandbox: Path, task: Task) -> Grade:
    with tempfile.TemporaryDirectory(prefix="grade-") as tmp:
        work = Path(tmp) / "work"
        shutil.copytree(sandbox, work)
        hidden = task.path / "tests"
        if hidden.is_dir():
            shutil.rmtree(work / "tests", ignore_errors=True)
            shutil.copytree(hidden, work / "tests")
        cmd = spec["command"]
        if cmd.startswith("python "):
            cmd = f"{sys.executable} {cmd[len('python '):]}"  # the runner's Python, which has pytest
        try:
            r = subprocess.run(cmd, shell=True, cwd=work, capture_output=True, text=True,
                               timeout=TIMEOUT_S, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        except subprocess.TimeoutExpired:
            return Grade("unit_tests", 0.0, False, f"tests timed out after {TIMEOUT_S}s")
    ok = r.returncode == 0
    tail = (r.stdout + r.stderr).strip().splitlines()[-15:]
    return Grade("unit_tests", 1.0 if ok else 0.0, ok, f"exit code {r.returncode}\n" + "\n".join(tail))
