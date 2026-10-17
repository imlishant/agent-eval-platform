"""Baseline loop with a scripted model: deterministic, free, no network."""

from pathlib import Path

import pytest

from evalrunner.harnesses.baseline import BaselineHarness
from evalrunner.models import ModelResponse, ProviderError, ToolCall
from evalrunner.sandbox import trial_dirs
from evalrunner.schema import Config, Task, TrialContext
from test_pipeline import TASK


class ScriptedModel:
    """Returns the queued responses in order and records what it was sent."""

    def __init__(self, script):
        self.script, self.seen = list(script), []

    def chat(self, messages, tools, *, temperature, max_tokens):
        self.seen.append({"messages": [dict(m) for m in messages], "tools": [t["function"]["name"] for t in tools]})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        text, calls = item
        msg = {"role": "assistant", "content": text}
        if calls:
            msg["tool_calls"] = [{"id": c.id, "type": "function", "function": {"name": c.name, "arguments": "{}"}} for c in calls]
        return ModelResponse(text, calls, 10, 5, 1, 1, msg)


def run(script, sessions=None, **settings):
    task = Task.load(TASK)
    if sessions:
        task.sessions = sessions
    cfg = Config.from_dict({"name": "t", "harness": "baseline",
                            "model": {"provider": "openai_compat", "id": "x"}, "settings": settings})
    model = ScriptedModel(script)
    with trial_dirs(task) as (sb, home):
        trace = BaselineHarness(lambda spec: model).run_trial(TrialContext(task, cfg, sb, home))
    return trace, model


def types(trace):
    return [e.type for e in trace.events]


def test_tool_call_then_answer():
    trace, model = run([("", [ToolCall("1", "bash", {"cmd": "tail -n +2 data.csv | wc -l"})]), ("37", [])])
    assert trace.final_answer() == "37"
    result = next(e for e in trace.events if e.type == "tool_result")
    assert "37" in result.payload["output"] and not result.payload["is_error"]
    assert model.seen[1]["messages"][-1]["role"] == "tool"   # tool output was fed back
    assert trace.usage() == {"input_tokens": 20, "output_tokens": 10, "model_calls": 2}


def test_unknown_tool_and_bad_args_are_agent_errors_not_crashes():
    trace, _ = run([("", [ToolCall("1", "delete_everything", {}), ToolCall("2", "bash", {"_raw": "{oops"})]), ("done", [])])
    results = [e.payload for e in trace.events if e.type == "tool_result"]
    assert all(r["is_error"] for r in results)
    assert "unknown tool" in results[0]["output"] and "not valid JSON" in results[1]["output"]


def test_path_escape_is_refused():
    trace, _ = run([("", [ToolCall("1", "read_file", {"path": "../../etc/passwd"})]), ("no", [])])
    r = next(e for e in trace.events if e.type == "tool_result").payload
    assert r["is_error"] and "outside the working folder" in r["output"]


def test_step_limit_recorded():
    loop = [("", [ToolCall(str(i), "bash", {"cmd": "true"})]) for i in range(3)]
    trace, _ = run(loop, max_steps=3)
    err = next(e for e in trace.events if e.type == "error")
    assert err.payload["kind"] == "step_exhaustion"
    assert trace.final_answer() == ""


def test_memory_carries_across_sessions_only_when_on():
    script = [("", [ToolCall("1", "memory_write", {"note": "code word is HERON"})]), ("ok", []), ("HERON", [])]
    trace, model = run(script, sessions=["remember HERON", "what was the code word?"], memory="on")
    assert "memory_write" in types(trace)
    assert "HERON" in model.seen[2]["messages"][0]["content"]          # session 2 system prompt has it
    _, model_off = run([("ok", []), ("?", [])], sessions=["remember HERON", "word?"], memory="off")
    assert "memory_write" not in model_off.seen[0]["tools"]


def test_provider_error_propagates_for_invalid_marking():
    with pytest.raises(ProviderError):
        run([ProviderError("429 after 4 attempts")])


def test_provider_rejected_tool_call_is_an_agent_error_not_infra():
    from evalrunner.models import ModelOutputError
    trace, model = run([ModelOutputError("Failed to parse tool call arguments as JSON"), ("37", [])])
    err = next(e for e in trace.events if e.type == "error")
    assert err.payload["kind"] == "bad_tool_args"
    assert trace.final_answer() == "37"                       # the agent got another step
    assert "rejected" in model.seen[1]["messages"][-1]["content"]
