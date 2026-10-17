"""Run one trial and print the result as JSON on stdout.

Usage:  python -m evalrunner.run_trial trial.json
trial.json: {"task_dir": "...", "config": {...}, "trial_index": 0}

This is the only thing the API calls. Contract: stdout is exactly one JSON object.
"""

from __future__ import annotations

import json
import sys
import time

from .failures import classify
from .graders import run_graders
from .harnesses import get_harness
from .isolation import level, scrub
from .models import ProviderError
from .sandbox import trial_dirs
from .schema import Config, Task, TrialContext
from .version import code_version


def run(spec: dict) -> dict:
    task = Task.load(spec["task_dir"])
    config = Config.from_dict(spec["config"])
    harness = get_harness(config.harness)
    started = time.time()

    meta = {"task_id": task.id, "task_hash": task.content_hash(), "config_id": config.config_id(),
            "harness_version": harness.version, "trial_index": spec.get("trial_index", 0),
            "isolation": level(), "code_version": code_version()}

    with trial_dirs(task) as (sandbox, home):
        ctx = TrialContext(task, config, sandbox, home, meta["trial_index"])
        try:
            trace = harness.run_trial(ctx)
            grades = run_graders(task.graders, trace, sandbox, task)  # judge can hit the provider too
        except ProviderError as e:
            # infra failure: not the agent's fault, so no score; left out of comparisons
            return {**meta, "status": "invalid", "error": str(e), "score": None, "passed": None,
                    "grades": [], "usage": {}, "latency_ms": int((time.time() - started) * 1000),
                    "trace": []}

    score = sum(g.score for g in grades) / len(grades) if grades else 0.0
    wall_ms = int((time.time() - started) * 1000)
    waited_ms = sum(e.payload.get("waited_ms", 0) for e in trace.events if e.type == "model_call")
    return {
        **meta,
        "status": "done",
        "score": score,
        "passed": all(g.passed for g in grades),
        "grades": [g.__dict__ for g in grades],
        "failure": classify(trace, grades),
        "usage": trace.usage(),
        "latency_ms": wall_ms - waited_ms,  # the agent's time; rate-limit waits are our quota, not its speed
        "wall_ms": wall_ms,
        "rate_limit_wait_ms": waited_ms,
        "trace": trace.to_list(),
    }


def main() -> None:
    with open(sys.argv[1]) as f:
        spec = json.load(f)
    print(json.dumps(scrub(run(spec))))  # no API key ever leaves the runner


if __name__ == "__main__":
    main()
