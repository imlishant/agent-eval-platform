"""End-to-end with the mock harness: no model, no cost."""

import json
import subprocess
import sys
from pathlib import Path

from evalrunner.run_trial import run
from evalrunner.schema import Config

ROOT = Path(__file__).resolve().parents[2]
TASK = ROOT / "tasks" / "count-csv-rows"


def mock_config(behavior):
    return {"name": f"mock-{behavior}", "harness": "mock",
            "model": {"provider": "none", "id": "none"},
            "settings": {"extra": {"behavior": behavior}}}


def test_mock_solve_scores_one():
    r = run({"task_dir": str(TASK), "config": mock_config("solve")})
    assert r["score"] == 1.0 and r["passed"]
    assert r["trace"][-1]["type"] == "final_answer"


def test_mock_fail_scores_zero():
    r = run({"task_dir": str(TASK), "config": mock_config("fail")})
    assert r["score"] == 0.0 and not r["passed"]
    assert "expected '37'" in r["grades"][0]["reasoning"]


def test_config_id_ignores_name_but_not_content():
    a = Config.from_dict(mock_config("solve"))
    b = Config.from_dict({**mock_config("solve"), "name": "renamed"})
    c = Config.from_dict(mock_config("fail"))
    assert a.config_id() == b.config_id()
    assert a.config_id() != c.config_id()


def test_cli_prints_one_json_object(tmp_path):
    spec = tmp_path / "trial.json"
    spec.write_text(json.dumps({"task_dir": str(TASK), "config": mock_config("solve")}))
    out = subprocess.run([sys.executable, "-m", "evalrunner.run_trial", str(spec)],
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out)["score"] == 1.0


def test_each_trial_records_the_code_version_it_ran_on():
    from evalrunner.version import code_version
    r = run({"task_dir": str(TASK), "config": mock_config("solve")})
    assert r["code_version"] == code_version() and r["code_version"] != "unknown"
