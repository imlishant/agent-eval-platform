"""unit_tests: run the task's own tests against the agent's work. Pass = exit code 0.

task.yaml:
  - type: unit_tests
    command: "python -m pytest -q tests"

The tests come from the task folder (tasks/<id>/tests/), copied over the sandbox's tests/
right before grading, so an agent that edits or deletes the tests cannot fake a pass.
Hardening: pytest config files the agent may have planted (conftest.py, pytest.ini, ...) are removed,
the agent's code runs confined, and for pytest a pass also needs a JUnit report with >0 tests and no
failures, so code that just calls os._exit(0) on import cannot pass.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from ..isolation import confine
from ..schema import Grade, Task, Trace

TIMEOUT_S = 60


def unit_tests(spec: dict, trace: Trace, sandbox: Path, task: Task) -> Grade:
    with tempfile.TemporaryDirectory(prefix="grade-") as tmp:
        tmp = str(Path(tmp).resolve())
        work = Path(tmp) / "work"
        shutil.copytree(sandbox, work)
        hidden = task.path / "tests"
        if hidden.is_dir():
            shutil.rmtree(work / "tests", ignore_errors=True)
            shutil.copytree(hidden, work / "tests")
        for planted in PYTEST_CONFIG:
            for f in work.rglob(planted):
                if hidden.is_dir() and (work / "tests") in f.parents:
                    continue  # the task's own test files are trusted
                f.unlink()
        cmd = spec["command"]
        if cmd.startswith("python "):
            cmd = f"{sys.executable} {cmd[len('python '):]}"  # the runner's Python, which has pytest
        report = Path(tmp) / "report.xml"
        if "pytest" in cmd:
            cmd += f" -p no:cacheprovider --junitxml={report}"
        env = {"PATH": os.environ.get("PATH", ""), "HOME": tmp, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            r = subprocess.run(confine(["/bin/sh", "-c", cmd], Path(tmp)), cwd=work, capture_output=True,
                               text=True, timeout=TIMEOUT_S, env=env)
        except subprocess.TimeoutExpired:
            return Grade("unit_tests", 0.0, False, f"tests timed out after {TIMEOUT_S}s")
        ok, why = r.returncode == 0, f"exit code {r.returncode}"
        if ok and "pytest" in cmd:
            ok, why = _report_ok(report)
    tail = (r.stdout + r.stderr).strip().splitlines()[-15:]
    return Grade("unit_tests", 1.0 if ok else 0.0, ok, why + "\n" + "\n".join(tail))


PYTEST_CONFIG = ("conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini", "sitecustomize.py")


def _report_ok(report: Path) -> tuple[bool, str]:
    if not report.exists():
        return False, "exit code 0 but no pytest report was written (process exited early?)"
    root = ET.parse(report).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    tests, failed = int(suite.get("tests", 0)), int(suite.get("failures", 0)) + int(suite.get("errors", 0))
    if tests == 0 or failed:
        return False, f"pytest report: {tests} tests, {failed} failed/errored"
    return True, f"pytest report: {tests} tests passed"
