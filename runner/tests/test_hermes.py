"""Hermes event mapping, tested offline on recorded stream-json output (no Hermes run, no quota)."""

import json
from pathlib import Path

import pytest

from evalrunner.harnesses.hermes import HermesHarness
from evalrunner.models import ProviderError
from evalrunner.schema import Trace


def events(*evs):
    return "\n".join(json.dumps(e) for e in evs)


INIT = {"type": "system", "subtype": "init", "model": "m"}


def mapped(stdout, stderr=""):
    trace = Trace()
    HermesHarness._map_events(None, stdout, stderr, trace)
    return trace


def test_tool_calls_text_and_tokens_are_mapped():
    t = mapped(events(INIT,
        {"type": "tool_use", "name": "terminal", "input": {"command": "wc -l data.csv"}},
        {"type": "tool_result", "name": "terminal", "output": "38", "is_error": False},
        {"type": "text", "text": "37"},
        {"type": "result", "exit_code": 0, "text": "37", "duration_ms": 900,
         "tokens": {"input": 100, "output": 5, "cache_read": 50}}))
    assert [e.type for e in t.events] == ["tool_call", "tool_result", "message", "model_call", "final_answer"]
    assert t.final_answer() == "37"
    assert t.usage() == {"input_tokens": 150, "output_tokens": 5, "model_calls": 1}


def test_rate_limit_is_infra_failure_not_agent_failure():
    with pytest.raises(ProviderError):
        mapped(events(INIT, {"type": "result", "exit_code": 2, "error": "HTTP 429: quota exceeded", "tokens": {}}))


def test_agent_level_error_is_recorded_and_scores_as_no_answer():
    t = mapped(events(INIT, {"type": "result", "exit_code": 1, "error": "model returned no text", "tokens": {}}))
    assert any(e.type == "error" and e.payload["kind"] == "agent" for e in t.events)
    assert t.final_answer() == ""


def test_crash_without_result_is_invalid():
    with pytest.raises(ProviderError, match="crashed"):
        mapped("Traceback: something broke", stderr="ImportError")


def test_memory_off_session_2_cannot_read_session_1(tmp_path, monkeypatch):
    """Experiment 5 found a leak: Hermes stores every prompt in its home, and with memory off session 1's home
    stayed readable from session 2. A fake hermes binary records its prompt like Hermes does and reports which
    Hermes homes it can see under HOME. No model call, no quota."""
    from evalrunner.harnesses.hermes import HermesHarness
    from evalrunner.isolation import REPO
    from evalrunner.sandbox import trial_dirs
    from evalrunner.schema import Config, Task, TrialContext

    # outside pytest's private tmp: in Docker the agent runs as an unprivileged user and must be able to execute it,
    # like the real Hermes install under /opt
    import tempfile
    bindir = Path(tempfile.mkdtemp(prefix="fakehermes-"))
    bindir.chmod(0o755)
    fake = bindir / "hermes"
    fake.write_text(
        '#!/bin/sh\n'
        'if [ "$1" = "--version" ]; then echo "Hermes Agent v0.0.0"; exit 0; fi\n'
        'mkdir -p "$HERMES_HOME/sessions"; printf "%s" "$3" > "$HERMES_HOME/sessions/request_dump.json"\n'
        'seen=$(grep -rl MARIGOLD "$HOME" 2>/dev/null | grep -v "^$HERMES_HOME" | wc -l | tr -d " ")\n'
        'printf \'{"type":"result","exit_code":0,"text":"other_files_with_secret=%s","tokens":{}}\\n\' "$seen"\n')
    fake.chmod(0o755)
    monkeypatch.setenv("HERMES_BIN", str(fake))
    # own prepared base, so the test does not depend on this machine's real Hermes setup
    import evalrunner.harnesses.hermes as hermes_mod
    base = tmp_path / "hermes-base"
    (base / "installs").mkdir(parents=True)
    monkeypatch.setattr(hermes_mod, "BASE_HOME", base)

    task = Task.load(REPO / "tasks" / "remember-codeword")
    cfg = Config.from_dict({"name": "t", "harness": "hermes",
                            "model": {"provider": "openai_compat", "id": "m", "base_url": "http://localhost:9"},
                            "settings": {"memory": "off", "timeout_s": 60}})
    with trial_dirs(task) as (sb, home):
        trace = HermesHarness().run_trial(TrialContext(task, cfg, sb, home))
    assert trace.final_answer(session=2) == "other_files_with_secret=0"
