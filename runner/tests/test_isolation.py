"""Attacks an agent could make, each of which must fail. Written after a real Hermes trial
read the repo's reference solution and printed API keys (DECISIONS D14)."""

import sys
from pathlib import Path

import pytest

from evalrunner.graders.unit_tests import unit_tests
from evalrunner.harnesses.tools import bash
from evalrunner.isolation import REPO, level, scrub
from evalrunner.sandbox import trial_dirs
from evalrunner.schema import Task, Trace

TASK = Task.load(REPO / "tasks" / "fix-failing-test")
isolated = pytest.mark.skipif(level() == "folder-only", reason="needs the macOS sandbox or Linux as root (Docker)")
DENIED = ("Operation not permitted", "Permission denied")


@isolated
def test_agent_cannot_read_reference_solutions_or_home():
    with trial_dirs(TASK) as (sb, home):
        out, err = bash(sb, home, {"cmd": f"cat {REPO}/tasks/fix-failing-test/reference/files/src/stats.py"})
        assert err and any(d in out for d in DENIED)
        if level() == "sandbox-exec":  # in Docker the runner's HOME is /root, already unreadable
            out, err = bash(sb, home, {"cmd": f"ls {Path.home()}"})
            assert err and any(d in out for d in DENIED)


@isolated
def test_agent_cannot_see_other_trials():
    with trial_dirs(TASK) as (sb1, h1), trial_dirs(TASK) as (sb2, h2):
        (sb2 / "secret.txt").write_text("other trial")
        out, err = bash(sb1, h1, {"cmd": f"cat {sb2}/secret.txt"})
        assert err and "other trial" not in out


def test_agent_can_still_work_in_its_own_folder_and_run_python():
    with trial_dirs(TASK) as (sb, home):
        out, err = bash(sb, home, {"cmd": "echo hi > note.txt && cat note.txt && python -c 'import pytest; print(42)'"})
        assert not err and "hi" in out and "42" in out


def grade_with(files: dict) -> object:
    with trial_dirs(TASK) as (sb, home):
        for name, body in files.items():
            (sb / name).parent.mkdir(parents=True, exist_ok=True)
            (sb / name).write_text(body)
        return unit_tests({"command": "python -m pytest -q tests"}, Trace(), sb, TASK)


def test_planted_conftest_cannot_fake_a_pass():
    hack = "import pytest\n@pytest.hookimpl(tryfirst=True)\ndef pytest_runtest_call(item):\n    pass\n" \
           "def pytest_collection_modifyitems(items):\n    items.clear()\n"
    assert not grade_with({"conftest.py": hack}).passed


def test_exit_zero_on_import_cannot_fake_a_pass():
    assert not grade_with({"src/stats.py": "import os\nos._exit(0)\n"}).passed


def test_real_fix_still_passes():
    fixed = (REPO / "tasks/fix-failing-test/reference/files/src/stats.py").read_text()
    g = grade_with({"src/stats.py": fixed})
    assert g.passed, g.reasoning


def test_scrub_removes_secret_values_everywhere(monkeypatch):
    monkeypatch.setenv("FAKE_API_KEY", "sk-test-1234567890")
    out = scrub({"trace": [{"payload": {"output": "GEMINI=x FAKE_API_KEY=sk-test-1234567890"}}]})
    assert "sk-test-1234567890" not in str(out) and "[REDACTED:FAKE_API_KEY]" in str(out)


def test_scrub_removes_account_ids_from_provider_errors():
    # shape of a real Groq 429 message (ID made up)
    msg = ("RateLimitError after 4 attempts: Error code: 429 - Rate limit reached for model `openai/gpt-oss-120b` "
           "in organization `org_01abcdefghij0123456789` service tier `on_demand`; contact ops@example.com, "
           "projects/123456789012")
    out = scrub({"status": "invalid", "error": msg}, secrets={})["error"]
    assert "org_01abcdefghij" not in out and "org_[REDACTED]" in out
    assert "ops@example.com" not in out and "123456789012" not in out
    assert "Rate limit reached" in out                       # the useful part stays
