"""Run one trial and print the result as JSON on stdout.

Usage:  python -m evalrunner.run_trial trial.json
trial.json: {"task_dir": "...", "config": {...}, "trial_index": 0}

This is the only thing the API calls. Contract: stdout is exactly one JSON object.
"""

from __future__ import annotations

import json
import sys
import time

from .graders import run_graders
from .harnesses import get_harness
from .sandbox import trial_dirs
from .schema import Config, Task, TrialContext


def run(spec: dict) -> dict:
    task = Task.load(spec["task_dir"])
    config = Config.from_dict(spec["config"])
    harness = get_harness(config.harness)
    started = time.time()

    with trial_dirs(task) as (sandbox, home):
        ctx = TrialContext(task, config, sandbox, home, spec.get("trial_index", 0))
        trace = harness.run_trial(ctx)
        grades = run_graders(task.graders, trace, sandbox)

    score = sum(g.score for g in grades) / len(grades) if grades else 0.0
    return {
        "status": "done",
        "task_id": task.id,
        "task_hash": task.content_hash(),
        "config_id": config.config_id(),
        "harness_version": harness.version,
        "trial_index": ctx.trial_index,
        "score": score,
        "passed": all(g.passed for g in grades),
        "grades": [g.__dict__ for g in grades],
        "usage": trace.usage(),
        "latency_ms": int((time.time() - started) * 1000),
        "trace": trace.to_list(),
    }


def main() -> None:
    with open(sys.argv[1]) as f:
        spec = json.load(f)
    print(json.dumps(run(spec)))


if __name__ == "__main__":
    main()
