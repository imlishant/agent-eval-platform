"""OS-level confinement for everything the agent runs, plus secret scrubbing.

Why: folder isolation alone is not enough. In testing, an agent with a terminal searched the disk,
found this repo's reference solutions and copied one (and printed API keys with `env`).

macOS: every agent process runs under `sandbox-exec` with a profile that denies reading or writing
the user's home folder, this repository, and other trials' folders, then re-allows only the trial's
own folder and the read-only tool installs it needs (later rules win). Linux/Docker: see LIMITS.md
(the container runs the agent as a separate user; without either, the level is reported as
"folder-only" in every trial result so it is never silent).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL_CACHE = Path.home() / ".cache" / "evalrunner"   # shared, prepared-once tool installs (e.g. Hermes base)
SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.I)
# account identifiers that providers echo in error messages (e.g. Groq 429: "organization `org_…`")
ACCOUNT_IDS = [
    (re.compile(r"\borg_[A-Za-z0-9]{8,}"), "org_[REDACTED]"),
    (re.compile(r"\bprojects/\d{6,}"), "projects/[REDACTED]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
]


def level() -> str:
    return "sandbox-exec" if sys.platform == "darwin" and shutil.which("sandbox-exec") else "folder-only"


def _profile(trial_root: Path) -> str:
    home = Path.home()
    tmp = Path(tempfile.gettempdir()).resolve()
    read_only = [home / ".local", home / ".hermes" / "hermes-agent", home / ".hermes" / "tools",
                 home / ".hermes" / "installs", TOOL_CACHE, home / ".cache" / "uv",
                 REPO / "runner" / ".venv", Path(sys.prefix), Path(sys.base_prefix)]
    q = lambda p: '"' + str(Path(p).resolve()).replace('"', '\\"') + '"'
    return "\n".join([
        "(version 1)",
        "(allow default)",
        f"(deny file-read* file-write* (subpath {q(home)}) (subpath {q(REPO)}))",
        f'(deny file-read* file-write* (regex #"^{re.escape(str(tmp))}/(trial|grade)-"))',
        "(allow file-read-metadata)",  # stat/realpath only: file contents and folder listings stay denied
        "(allow file-read* " + " ".join(f"(subpath {q(p)})" for p in read_only) + ")",
        # Hermes takes locks and leases in its own install state; allow writing only those files, so an
        # agent cannot change the Hermes install that later trials use
        f'(allow file-write* (regex #"^({re.escape(str(TOOL_CACHE.resolve()))}|{re.escape(str((home / ".hermes").resolve()))})/'
        f'(.*\\.lock$|.*/\\.leases(/|$))"))',
        f"(allow file-read* file-write* (subpath {q(trial_root)}))",
    ]) + "\n"


def confine(cmd: list[str], trial_root: Path) -> list[str]:
    """Wrap a command so it can only touch `trial_root` (plus read-only tool installs)."""
    if level() != "sandbox-exec":
        return cmd
    profile = trial_root / "sandbox.sb"
    if not profile.exists():
        profile.write_text(_profile(trial_root))
    return ["sandbox-exec", "-f", str(profile), *cmd]


def secret_values() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if SECRET_NAME.search(k) and len(v) >= 8}


def scrub(obj, secrets: dict[str, str] | None = None):
    """Replace secret values (as [REDACTED:<NAME>]) and account identifiers anywhere in obj (str/list/dict)."""
    secrets = secret_values() if secrets is None else secrets
    if isinstance(obj, str):
        for name, value in secrets.items():
            obj = obj.replace(value, f"[REDACTED:{name}]")
        for pattern, replacement in ACCOUNT_IDS:
            obj = pattern.sub(replacement, obj)
        return obj
    if isinstance(obj, list):
        return [scrub(x, secrets) for x in obj]
    if isinstance(obj, dict):
        return {k: scrub(v, secrets) for k, v in obj.items()}
    return obj
