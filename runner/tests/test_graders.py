"""Grader self-check (PLAN §6). For every task with deterministic graders:
  reference solution (mock "solve") must score 1.0, doing nothing (mock "fail") must score 0.0.
If both hold, the grader is correct on the known answer AND can tell success from failure."""

import importlib
from pathlib import Path

import pytest

from evalrunner.graders.file_check import file_check
from evalrunner.models import ModelResponse
from evalrunner.run_trial import run
from evalrunner.schema import Task, Trace

judge_mod = importlib.import_module("evalrunner.graders.llm_judge")  # module, not the same-named function
TASKS = sorted((Path(__file__).resolve().parents[2] / "tasks").glob("*/task.yaml"))
DETERMINISTIC = [p.parent for p in TASKS
                 if all(g["type"] != "llm_judge" for g in Task.load(p.parent).graders)]


def mock(behavior):
    return {"name": behavior, "harness": "mock", "model": {"provider": "none", "id": "none"},
            "settings": {"extra": {"behavior": behavior}}}


def test_task_set_shape():
    cats = [Task.load(p.parent).category for p in TASKS]
    assert len(TASKS) >= 20
    assert {c: cats.count(c) for c in set(cats)} == {"code": 8, "exact": 3, "skill": 3, "memory": 3, "judge": 3}


@pytest.mark.parametrize("task_dir", DETERMINISTIC, ids=lambda p: p.name)
def test_reference_scores_one(task_dir):
    r = run({"task_dir": str(task_dir), "config": mock("solve")})
    assert r["score"] == 1.0, [g["reasoning"] for g in r["grades"]]


@pytest.mark.parametrize("task_dir", DETERMINISTIC, ids=lambda p: p.name)
def test_doing_nothing_scores_zero(task_dir):
    r = run({"task_dir": str(task_dir), "config": mock("fail")})
    assert r["score"] == 0.0, [g["reasoning"] for g in r["grades"]]


def test_file_check_gives_partial_credit(tmp_path):
    (tmp_path / "f.txt").write_text("alpha beta")
    g = file_check({"path": "f.txt", "contains": ["alpha", "gamma"]}, Trace(), tmp_path, None)
    assert g.score == 0.5 and not g.passed and "FAIL contains 'gamma'" in g.reasoning


class FakeJudge:
    def __init__(self, text):
        self.text = text

    def chat(self, messages, tools, *, temperature, max_tokens):
        assert temperature == 0
        return ModelResponse(self.text, [], 1, 1, 1, 1, {})


@pytest.mark.parametrize("reply,score,ok", [
    ('{"criteria":[{"id":1,"met":true,"reason":"a"},{"id":2,"met":false,"reason":"b"}]}', 0.5, True),
    ('<thought>hmm</thought> Sure! {"criteria":[{"id":1,"met":true},{"id":2,"met":true}]}', 1.0, True),
    ('{"criteria":[{"id":1,"met":true}]}', 0.0, False),   # wrong number of verdicts
    ('I think it is fine.', 0.0, False),                   # not JSON
])
def test_judge_parsing(monkeypatch, reply, score, ok):
    monkeypatch.setattr(judge_mod, "get_model", lambda spec: FakeJudge(reply))
    g = judge_mod.judge_text("task", "output", ["c1", "c2"], {})
    assert g.score == score
    assert ("not valid JSON" not in g.reasoning) == ok
