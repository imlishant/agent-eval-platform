"""Per-trial isolation: a fresh temp folder for work and a fresh HOME.

Nothing is shared between trials, so one trial cannot see another's files or memory.
Folder isolation alone is not enough (agents can read the whole disk), so every agent process
is also confined by isolation.confine() to the trial root, i.e. sandbox.parent.
"""

from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .schema import Task


@contextmanager
def trial_dirs(task: Task, keep: bool = False) -> Iterator[tuple[Path, Path]]:
    root = Path(tempfile.mkdtemp(prefix=f"trial-{task.id}-")).resolve()
    sandbox, home = root / "sandbox", root / "home"
    fixtures = task.path / "fixtures"
    if fixtures.is_dir():
        shutil.copytree(fixtures, sandbox)
    else:
        sandbox.mkdir()
    home.mkdir()
    try:
        yield sandbox, home
    finally:
        if not keep:
            shutil.rmtree(root, ignore_errors=True)
