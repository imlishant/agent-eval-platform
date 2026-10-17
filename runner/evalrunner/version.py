"""Which code a trial ran on: `<git short sha>` or `<sha>-dirty.<hash of the uncommitted diff>`.

Computed per trial (not once per experiment), because a long experiment runs on whatever is in the
working tree at the time: if the code changes mid-run, trials disagree with the experiment's version
and the API flags them. The API computes the experiment's version the same way (runner.service.ts).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def code_version() -> str:
    if os.environ.get("CODE_SHA"):  # e.g. in Docker, where there is no .git
        return os.environ["CODE_SHA"]
    try:
        git = lambda *a: subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True, check=True).stdout
        sha = git("rev-parse", "--short", "HEAD").strip()
        status = git("status", "--porcelain")
        if not status.strip():
            return sha
        diff = git("diff", "HEAD")
        return f"{sha}-dirty.{hashlib.sha256((status + diff).encode()).hexdigest()[:8]}"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
