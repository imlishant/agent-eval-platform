"""llm_judge: a model grades the agent's output against a yes/no rubric.

task.yaml:
  - type: llm_judge
    target_file: summary.md            # what to grade (omit = the final answer)
    context_files: [incident.md]       # source material the judge may check facts against
    rubric:
      - "States that the root cause was an expired TLS certificate."
      - "Does not invent facts that are not in incident.md."

Score = share of criteria met; passed = all met. Temperature 0. The judge model is set in
configs/judge.json and should differ from the models under test. Trust in this grader comes
from judge_validation/ (agreement with human labels, Cohen's kappa).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from ..models import get_model
from ..schema import Grade, ModelSpec, Task, Trace

JUDGE_CONFIG = Path(os.environ.get("JUDGE_CONFIG", Path(__file__).resolve().parents[3] / "configs" / "judge.json"))

PROMPT = """You are grading an AI agent's work. Judge each criterion strictly and independently.

TASK GIVEN TO THE AGENT:
{task}
{context}
OUTPUT TO GRADE:
<<<
{output}
>>>

CRITERIA:
{criteria}

Reply with JSON only, no other text, in exactly this shape:
{{"criteria": [{{"id": 1, "met": true, "reason": "one short sentence"}}, ...]}}"""


def judge_text(task_text: str, output: str, rubric: list[str], context: dict[str, str]) -> Grade:
    """Grade `output` against `rubric`. Separate from llm_judge() so validate_judge.py can call it."""
    cfg = json.loads(JUDGE_CONFIG.read_text())
    model = get_model(ModelSpec(**cfg["model"]))
    ctx = "".join(f"\nSOURCE FILE {name}:\n<<<\n{body}\n>>>\n" for name, body in context.items())
    criteria = "\n".join(f"{i}. {c}" for i, c in enumerate(rubric, start=1))
    prompt = PROMPT.format(task=task_text, context=ctx, output=output or "(empty)", criteria=criteria)
    resp = model.chat([{"role": "user", "content": prompt}], [], temperature=0,
                      max_tokens=cfg.get("max_tokens", 1500))

    verdicts = _parse(resp.text, len(rubric))
    if verdicts is None:
        return Grade("llm_judge", 0.0, False, f"judge reply was not valid JSON: {resp.text[:300]!r}")
    met = sum(v["met"] for v in verdicts)
    lines = [f"{'MET' if v['met'] else 'NOT MET'} - {c} ({v['reason']})" for c, v in zip(rubric, verdicts)]
    return Grade("llm_judge", met / len(rubric), met == len(rubric), "\n".join(lines))


def llm_judge(spec: dict, trace: Trace, sandbox: Path, task: Task) -> Grade:
    if "target_file" in spec:
        f = sandbox / spec["target_file"]
        output = f.read_text(errors="replace") if f.is_file() else ""
    else:
        output = trace.final_answer()
    if not output.strip():
        return Grade("llm_judge", 0.0, False, "nothing to grade: output is empty or missing")
    context = {name: (task.path / "fixtures" / name).read_text() for name in spec.get("context_files", [])}
    return judge_text("\n".join(task.sessions), output, spec["rubric"], context)


def _parse(text: str, n: int) -> list[dict] | None:
    """Take the last {...} block (some models think out loud first); need one verdict per criterion."""
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        return None
    try:
        items = json.loads(text[start:end + 1])["criteria"]
        verdicts = [{"met": bool(i["met"]), "reason": str(i.get("reason", ""))} for i in items]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return verdicts if len(verdicts) == n else None
