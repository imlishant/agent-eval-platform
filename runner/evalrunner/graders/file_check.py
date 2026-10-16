"""file_check: inspect a file the agent should have created or changed.

task.yaml:
  - type: file_check
    path: out/config.json
    contains: ["port"]            # each string must appear
    not_contains: ["TODO"]        # none may appear
    regex: ["^## v2\\.4\\.0"]     # each pattern must match (multiline)
    json_fields: {port: 8080}     # file is JSON and each field equals the value

Score = share of checks that pass (partial credit is visible), passed = all pass.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..schema import Grade, Task, Trace


def file_check(spec: dict, trace: Trace, sandbox: Path, task: Task) -> Grade:
    path = sandbox / spec["path"]
    if not path.is_file():
        return Grade("file_check", 0.0, False, f"{spec['path']} does not exist")
    text = path.read_text(errors="replace")
    results: list[tuple[bool, str]] = []

    for s in spec.get("contains", []):
        results.append((s in text, f"contains {s!r}"))
    for s in spec.get("not_contains", []):
        results.append((s not in text, f"does not contain {s!r}"))
    for pattern in spec.get("regex", []):
        results.append((re.search(pattern, text, re.MULTILINE) is not None, f"matches /{pattern}/"))
    if "json_fields" in spec:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            results.append((False, f"valid JSON ({e.msg})"))
        else:
            for key, want in spec["json_fields"].items():
                got = data.get(key, "<missing>") if isinstance(data, dict) else "<not an object>"
                results.append((got == want, f"{key} == {want!r} (got {got!r})"))

    if not results:
        results.append((True, "file exists"))
    passed = sum(ok for ok, _ in results)
    reasoning = "; ".join(("PASS " if ok else "FAIL ") + label for ok, label in results)
    return Grade("file_check", passed / len(results), passed == len(results), reasoning)
