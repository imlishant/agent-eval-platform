"""Check the LLM judge against human labels: accuracy and Cohen's kappa.

Usage:  cd runner && uv run python ../judge_validation/validate_judge.py
Each item in labels.json is one agent output with a human pass/fail label. The judge grades the
same output with the task's rubric; judge "pass" = every criterion met. kappa >= 0.6 = judge
trusted; below that, judge-graded tasks are flagged "low trust" (PLAN §6).
"""

import importlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load_env(path: Path) -> None:
    """Read KEY=value lines from the repo's .env (as the API does), without overriding the environment."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env(ROOT / ".env")
sys.path.insert(0, str(ROOT / "runner"))
from evalrunner.schema import Task  # noqa: E402

judge = importlib.import_module("evalrunner.graders.llm_judge")
KAPPA_OK = 0.6


def cohens_kappa(a: list[bool], b: list[bool]) -> float:
    """Agreement beyond chance: (observed - expected) / (1 - expected)."""
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def main() -> None:
    items = json.loads((HERE / "labels.json").read_text())
    unreviewed = [i["id"] for i in items if not i.get("reviewed_by_human")]
    if unreviewed:
        print(f"WARNING: items {unreviewed} are drafts not yet confirmed by a human; results are provisional.\n")

    rows = []
    for item in items:
        task = Task.load(ROOT / "tasks" / item["task_id"])
        spec = next(g for g in task.graders if g["type"] == "llm_judge")
        ctx = {n: (task.path / "fixtures" / n).read_text() for n in spec.get("context_files", [])}
        g = judge.judge_text("\n".join(task.sessions), item["output"], spec["rubric"], ctx)
        human = item["label"] == "pass"
        rows.append({"id": item["id"], "task_id": item["task_id"], "human": human, "judge": g.passed,
                     "judge_score": g.score, "agree": human == g.passed, "judge_reasoning": g.reasoning})
        print(f"#{item['id']:>2} {item['task_id']:<17} human={'pass' if human else 'fail'} "
              f"judge={'pass' if g.passed else 'fail'} ({g.score:.2f}) {'ok' if human == g.passed else 'DISAGREE'}")

    human = [r["human"] for r in rows]
    judged = [r["judge"] for r in rows]
    acc = sum(r["agree"] for r in rows) / len(rows)
    kappa = cohens_kappa(human, judged)
    verdict = "TRUSTED" if kappa >= KAPPA_OK else "LOW TRUST"
    print(f"\naccuracy {acc:.2f}  kappa {kappa:.2f}  -> judge {verdict} (threshold {KAPPA_OK})")
    (HERE / "results.json").write_text(json.dumps(
        {"accuracy": acc, "kappa": kappa, "verdict": verdict, "n": len(rows),
         "provisional": bool(unreviewed), "items": rows}, indent=2))


if __name__ == "__main__":
    main()
