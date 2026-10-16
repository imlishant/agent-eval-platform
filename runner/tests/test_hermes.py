"""Hermes event mapping, tested offline on recorded stream-json output (no Hermes run, no quota)."""

import json

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
