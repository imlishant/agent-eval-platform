"""One synthetic trace per failure rule, plus precedence and the pass case."""

from evalrunner.failures import classify
from evalrunner.schema import Grade, Trace

FAIL = [Grade("exact_match", 0.0, False, "wrong")]
PASS = [Grade("exact_match", 1.0, True, "ok")]


def trace(*steps):
    t = Trace()
    t.add("message", role="user", text="do it")
    for kind, payload in steps:
        t.add(kind, **payload)
    return t


def call(name="bash", **args):
    return ("tool_call", {"name": name, "args": args})


def result(output="ok", is_error=False, name="bash"):
    return ("tool_result", {"name": name, "output": output, "is_error": is_error})


ANSWER = ("final_answer", {"text": "42"})


def test_passed_trial_has_no_category():
    assert classify(trace(call(cmd="ls"), result(), ANSWER), PASS)["category"] is None


def test_timeout():
    t = trace(call(cmd="ls"), result(), ("error", {"kind": "timeout", "message": "x"}), ("final_answer", {"text": ""}))
    assert classify(t, FAIL)["category"] == "timeout"


def test_step_exhaustion_baseline_and_hermes_wording():
    t = trace(call(cmd="a"), result(), ("error", {"kind": "step_exhaustion", "message": "x"}), ("final_answer", {"text": ""}))
    assert classify(t, FAIL)["category"] == "step_exhaustion"
    h = trace(call(cmd="a"), result(), ("final_answer", {"text": "I ran out of steps for this turn (15 tool calls)"}))
    assert classify(h, FAIL)["category"] == "step_exhaustion"


def test_loop_same_call_three_times():
    t = trace(*[s for _ in range(3) for s in (call(cmd="cat x"), result())], ANSWER)
    assert classify(t, FAIL)["category"] == "loop"


def test_bad_tool_args_from_provider_or_tool():
    t = trace(("error", {"kind": "bad_tool_args", "message": "Failed to parse"}), call(cmd="ls"), result(), ANSWER)
    assert classify(t, FAIL)["category"] == "bad_tool_args"
    t2 = trace(call(), result("missing required argument 'cmd'", True), ANSWER)
    assert classify(t2, FAIL)["category"] == "bad_tool_args"


def test_wrong_tool():
    t = trace(call("delete_everything"), result("error: unknown tool 'delete_everything'", True), call(cmd="ls"), result(), ANSWER)
    assert classify(t, FAIL)["category"] == "wrong_tool"


def test_grader_disagreement():
    grades = [Grade("unit_tests", 1.0, True, "ok"), Grade("file_check", 0.0, False, "still contains get_usr")]
    t = trace(call(cmd="a"), result(), call(cmd="b"), result(), ANSWER)
    assert classify(t, grades)["category"] == "grader_disagreement"


def test_gave_up_early_no_tool_used_or_no_answer():
    assert classify(trace(ANSWER), FAIL)["category"] == "gave_up_early"
    assert classify(trace(call(cmd="ls"), result(), ("final_answer", {"text": ""})), FAIL)["category"] == "gave_up_early"


def test_wrong_answer_is_the_default():
    t = trace(call(cmd="wc -l data.csv"), result("38"), ANSWER)
    out = classify(t, FAIL)
    assert out["category"] == "wrong_answer" and out["signals"] == []


def test_precedence_keeps_all_signals():
    t = trace(*[s for _ in range(3) for s in (call(cmd="x"), result())],
              ("error", {"kind": "step_exhaustion", "message": "x"}), ("final_answer", {"text": ""}))
    out = classify(t, FAIL)
    assert out["category"] == "step_exhaustion" and {"loop", "gave_up_early"} <= set(out["signals"])
