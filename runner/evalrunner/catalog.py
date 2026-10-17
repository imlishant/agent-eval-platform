"""Print every config and task as JSON, for the API.

Usage:  python -m evalrunner.catalog
The config ID is computed here (Python) only, so the API and the runner can never disagree on it.
"""

from __future__ import annotations

import json
from pathlib import Path

from .harnesses import HARNESSES
from .schema import Config, Task

ROOT = Path(__file__).resolve().parents[2]


def catalog() -> dict:
    configs = []
    for f in sorted((ROOT / "configs").glob("*.json")):
        if f.name in ("judge.json", "prices.json", "models.json"):
            continue
        cfg = Config.from_dict(json.loads(f.read_text()))
        configs.append({"file": f.name, "name": cfg.name, "id": cfg.config_id(), "config": cfg.to_dict()})
    tasks = []
    for f in sorted((ROOT / "tasks").glob("*/task.yaml")):
        t = Task.load(f.parent)
        tasks.append({"id": t.id, "category": t.category, "hash": t.content_hash(), "sessions": len(t.sessions),
                      "graders": [g["type"] for g in t.graders]})
    skills = [{"name": f.stem, "description": f.read_text().splitlines()[0].lstrip("# ").strip()}
              for f in sorted((ROOT / "skills").glob("*.md"))]
    harnesses = [{"id": h.id, "description": h.description, "settings": list(h.settings),
                  "requirements": h.requirements} for h in HARNESSES.values()]
    models = json.loads((ROOT / "configs" / "models.json").read_text())
    return {"configs": configs, "tasks": tasks, "skills": skills, "harnesses": harnesses, "models": models}


if __name__ == "__main__":
    print(json.dumps(catalog()))
