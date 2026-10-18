"""OS-level confinement for everything the agent runs, plus secret scrubbing.

Why: folder isolation alone is not enough. In testing, an agent with a terminal searched the disk,
found this repo's reference solutions and copied one (and printed API keys with `env`).

macOS: every agent process runs under `sandbox-exec` with a profile that denies reading or writing
the user's home folder, this repository, and other trials' folders, then re-allows only the trial's
own folder and the read-only tool installs it needs (later rules win).

Linux as root (the Docker image): every agent process drops to an unprivileged user ID of its own
(one per trial, from the runner's PID, which is unique while the trial runs) via `setpriv`. The trial
folder is chown'ed to that ID with mode 700, so trials cannot read each other, and the answer keys
(`tasks/`, `judge_validation/`) are root-only in the image. A shared group gives write access to the
prepared Hermes base only.

Anything else: the level is reported as "folder-only" in every trial result, so it is never silent.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# shared, prepared-once tool installs (e.g. the Hermes base); overridable for the Docker image
TOOL_CACHE = Path(os.environ.get("EVAL_TOOL_CACHE", Path.home() / ".cache" / "evalrunner"))
AGENT_UID_BASE = 20000   # Linux: agent user IDs are AGENT_UID_BASE + (runner pid % 10000)
AGENT_GID = 20000        # shared group: may write the prepared Hermes base, nothing else
SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.I)
# account identifiers that providers echo in error messages (e.g. Groq 429: "organization `org_…`")
ACCOUNT_IDS = [
    (re.compile(r"\borg_[A-Za-z0-9]{8,}"), "org_[REDACTED]"),
    (re.compile(r"\bprojects/\d{6,}"), "projects/[REDACTED]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
]


def level() -> str:
    if sys.platform == "darwin" and shutil.which("sandbox-exec"):
        return "sandbox-exec"
    if sys.platform.startswith("linux") and os.geteuid() == 0 and shutil.which("setpriv"):
        return "unprivileged-user"
    return "folder-only"


def agent_uid() -> int:
    return AGENT_UID_BASE + os.getpid() % 10000


def _give_to_agent(root: Path) -> None:
    """Make the trial folder belong to this trial's agent ID only (mode 700 on folders)."""
    uid = agent_uid()
    for dirpath, dirnames, filenames in os.walk(root):
        os.chown(dirpath, uid, AGENT_GID, follow_symlinks=False)
        os.chmod(dirpath, 0o700)
        for name in filenames:
            os.chown(os.path.join(dirpath, name), uid, AGENT_GID, follow_symlinks=False)
        for name in dirnames:
            os.chown(os.path.join(dirpath, name), uid, AGENT_GID, follow_symlinks=False)


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
    lvl = level()
    if lvl == "unprivileged-user":
        _give_to_agent(trial_root)
        return ["setpriv", f"--reuid={agent_uid()}", f"--regid={AGENT_GID}", "--clear-groups", "--", *cmd]
    if lvl != "sandbox-exec":
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
