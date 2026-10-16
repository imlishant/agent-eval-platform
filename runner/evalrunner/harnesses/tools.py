"""Tools the baseline agent can call. Every tool is confined to the trial's folders.

Each tool returns (output_text, is_error). Errors are returned to the model, not raised,
so a bad tool call is a visible agent mistake in the trace, not a crash.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ..isolation import confine

MAX_OUTPUT = 4000
BASH_TIMEOUT_S = 30


def _inside(sandbox: Path, path: str) -> Path:
    p = (sandbox / path).resolve()
    if not p.is_relative_to(sandbox.resolve()):
        raise ValueError(f"path '{path}' is outside the working folder")
    return p


def bash(sandbox: Path, home: Path, args: dict) -> tuple[str, bool]:
    cmd = args.get("cmd") or args.get("command")
    if not isinstance(cmd, str):
        return "missing required argument 'cmd'", True
    # runner's Python first on PATH, so `python -m pytest` works the same for agent and grader
    path = os.path.dirname(sys.executable) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin")
    env = {"PATH": path, "HOME": str(home), "LANG": "C.UTF-8"}
    try:
        r = subprocess.run(confine(["/bin/sh", "-c", cmd], sandbox.parent), cwd=sandbox, env=env,
                           capture_output=True, text=True, timeout=BASH_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return f"command timed out after {BASH_TIMEOUT_S}s", True
    out = (r.stdout + r.stderr)[-MAX_OUTPUT:]
    return f"exit code {r.returncode}\n{out}", r.returncode != 0


def read_file(sandbox: Path, home: Path, args: dict) -> tuple[str, bool]:
    try:
        p = _inside(sandbox, args["path"])
        return p.read_text()[:MAX_OUTPUT], False
    except (KeyError, ValueError, OSError, UnicodeDecodeError) as e:
        return f"error: {e}", True


def write_file(sandbox: Path, home: Path, args: dict) -> tuple[str, bool]:
    try:
        p = _inside(sandbox, args["path"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(args["content"])
        return f"wrote {len(args['content'])} chars to {args['path']}", False
    except (KeyError, ValueError, OSError, TypeError) as e:
        return f"error: {e}", True


TOOL_FUNCS = {"bash": bash, "read_file": read_file, "write_file": write_file}

TOOL_SCHEMAS = {
    "bash": {"description": "Run a shell command in the working folder. Returns exit code and output.",
             "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}},
    "read_file": {"description": "Read a text file from the working folder.",
                  "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    "write_file": {"description": "Create or overwrite a text file in the working folder.",
                   "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                                  "required": ["path", "content"]}},
    "memory_write": {"description": "Save a note to your long-term memory. It will be shown to you in future sessions.",
                     "parameters": {"type": "object", "properties": {"note": {"type": "string"}}, "required": ["note"]}},
    "use_skill": {"description": "Load the full instructions of one of your skills by name.",
                  "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
}


def schema(name: str) -> dict:
    return {"type": "function", "function": {"name": name, **TOOL_SCHEMAS[name]}}
