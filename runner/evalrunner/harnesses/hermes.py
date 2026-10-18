"""Hermes Agent (Nous Research) as a harness, run headless as a subprocess.

Per trial:  HERMES_HOME = <trial home>/.hermes, holding a config.yaml we write (provider, model,
            memory switch), our enabled skills, and whatever memory Hermes saves. Nothing is shared
            with the user's ~/.hermes or with other trials.
Per session: one `hermes chat -q <prompt> --oneshot --format stream-json` process. Sessions of the same
            trial share HERMES_HOME, so memory carries over only when memory is on.
Trace:      Hermes prints JSON events (tool_use, tool_result, text, result); we map them onto our
            schema. Memory writes are found by diffing $HERMES_HOME/memories before and after a session.

Quirks (see docs/LIMITS.md): Hermes has its own large system prompt (~29k tokens) and 58 bundled
skills that are always present; it has no temperature setting; it needs a model with >= 64k context.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import yaml

from ..isolation import AGENT_GID, TOOL_CACHE, confine, level
from ..models import ProviderError
from ..schema import Trace, TrialContext
from .base import HarnessAdapter

SKILLS_DIR = Path(__file__).resolve().parents[3] / "skills"
# Hermes builds a dependency environment per HERMES_HOME on first use, which needs write access the
# sandbox denies. So one base home is prepared once, unsandboxed, and every trial links to its installs.
BASE_HOME = TOOL_CACHE / "hermes-base"
PROVIDER_NAME = "eval-provider"
# provider-side failures: retrying later may succeed, so the trial is invalid rather than failed
PROVIDER_ERROR = re.compile(r"HTTP (429|5\d\d)|rate.?limit|quota|timed? ?out connecting|connection (error|refused)", re.I)


def hermes_bin() -> str:
    found = os.environ.get("HERMES_BIN") or shutil.which("hermes") or str(Path.home() / ".local/bin/hermes")
    if not Path(found).exists():
        raise ProviderError("hermes CLI not found; install it or set HERMES_BIN")
    return found


class HermesHarness(HarnessAdapter):
    id = "hermes"
    version = "1"
    description = "Hermes Agent (Nous Research), run headless: its own tools, skills, memory and large system prompt."
    settings = ("skills", "memory", "max_steps", "timeout_s")  # no temperature; tools are Hermes's own
    requirements = "Needs a model with at least 64k context and a high token-per-minute limit (~30k tokens per call)."

    def __init__(self) -> None:
        self.bin = hermes_bin()
        out = subprocess.run([self.bin, "--version"], capture_output=True, text=True, timeout=60).stdout
        if not (BASE_HOME / "installs").is_dir():
            BASE_HOME.mkdir(parents=True, exist_ok=True)
            subprocess.run([self.bin, "chat", "-q", "hi", "--oneshot", "-Q"], capture_output=True, timeout=900,
                           env={**os.environ, "HERMES_HOME": str(BASE_HOME)})  # syncs deps; the model call itself may fail
            if not (BASE_HOME / "installs").is_dir():
                raise ProviderError(f"could not prepare Hermes base home at {BASE_HOME}")
        if level() == "unprivileged-user":
            # agents (one user ID per trial, shared group) need to take locks/leases in the prepared base
            for dirpath, _dirs, files in os.walk(BASE_HOME):
                os.chown(dirpath, 0, AGENT_GID, follow_symlinks=False)
                os.chmod(dirpath, 0o775)
                for f in files:
                    path = os.path.join(dirpath, f)
                    if not os.path.islink(path):
                        os.chown(path, 0, AGENT_GID)
                        os.chmod(path, os.stat(path).st_mode | 0o060)  # group read + write (lock files)
        m = re.search(r"v(\d+\.\d+\.\d+)", out)
        self.version = f"1+hermes-{m.group(1) if m else 'unknown'}"

    def run_trial(self, ctx: TrialContext) -> Trace:
        s, model = ctx.config.settings, ctx.config.model
        memory_on = s.memory == "on"
        # minimal env: only this provider's key, so `env` inside the agent cannot reveal other secrets
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(ctx.home_dir), "LANG": "C.UTF-8"}
        if model.api_key_env:
            env[model.api_key_env] = os.environ.get(model.api_key_env, "")
        trace = Trace()
        deadline = time.time() + s.timeout_s

        for session_no, prompt in enumerate(ctx.task.sessions, start=1):
            trace.session = session_no
            trace.add("message", role="user", text=prompt)
            # memory on: one Hermes home for the whole trial (memories + session history carry over).
            # memory off: a fresh home per session; Hermes can search its stored past sessions even with
            # memory disabled, so a shared home would leak session 1 into session 2.
            home = ctx.home_dir / (".hermes" if memory_on else f".hermes-s{session_no}")
            self._prepare_home(home, ctx)
            env["HERMES_HOME"] = str(home)
            before = _snapshot(home / "memories")
            if memory_on and any(before.values()):
                trace.add("memory_read", files=sorted(k for k, v in before.items() if v),
                          content="\n".join(v for v in before.values() if v))

            remaining = int(deadline - time.time())
            if remaining <= 5:
                trace.add("error", kind="timeout", message=f"trial exceeded {s.timeout_s}s")
                trace.add("final_answer", text="")
                break
            cmd = [self.bin, "chat", "-q", prompt, "--oneshot", "--format", "stream-json",
                   "--in", str(ctx.sandbox_dir), "--provider", PROVIDER_NAME, "-m", model.id,
                   "--max-turns", str(s.max_steps), "--run-budget", str(remaining)]
            try:
                proc = subprocess.run(confine(cmd, ctx.sandbox_dir.parent), cwd=ctx.sandbox_dir, env=env, capture_output=True,
                                      text=True, timeout=remaining + 30)
            except subprocess.TimeoutExpired:
                trace.add("error", kind="timeout", message=f"hermes did not exit within {remaining + 30}s")
                trace.add("final_answer", text="")
                break

            self._map_events(proc.stdout, proc.stderr, trace)
            for name, text in _snapshot(home / "memories").items():
                old = before.get(name, "")
                if text != old:
                    trace.add("memory_write", file=name, note=text[len(old):] if text.startswith(old) else text)
            if not memory_on:
                # Hermes writes every prompt into its home (sessions/, logs/, spawn-ledger.json). With memory off,
                # a later session must not be able to read them, so this session's home goes now (FIX-21).
                shutil.rmtree(home, ignore_errors=True)
        return trace

    def _prepare_home(self, home: Path, ctx: TrialContext) -> None:
        s, model = ctx.config.settings, ctx.config.model
        if home.exists():
            return
        home.mkdir(parents=True)
        if not (home / "installs").exists():
            (home / "installs").symlink_to(BASE_HOME / "installs")  # read-only inside the sandbox
        provider = {"base_url": model.base_url}
        if model.api_key_env:
            provider["key_env"] = model.api_key_env
        config = {
            "model": {"default": model.id, "provider": PROVIDER_NAME},
            "providers": {PROVIDER_NAME: provider},
            "memory": {"memory_enabled": s.memory == "on", "user_profile_enabled": s.memory == "on"},
        }
        (home / "config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
        for name in s.skills:  # our skill docs in Hermes's format: skills/<name>/SKILL.md with frontmatter
            text = (SKILLS_DIR / f"{name}.md").read_text()
            desc = text.splitlines()[0].lstrip("# ").strip()
            dest = home / "skills" / name / "SKILL.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(f"---\nname: {name}\ndescription: {json.dumps(desc)}\n---\n\n{text}")

    def _map_events(self, stdout: str, stderr: str, trace: Trace) -> None:
        texts: list[str] = []
        final = None
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                trace.add("error", kind="harness_output", message=line[:500])
                continue
            kind = ev.get("type")
            if kind == "tool_use":
                trace.add("tool_call", name=ev.get("name"), args=ev.get("input", {}))
                if ev.get("name") in ("skill_view", "skill_load", "skills"):
                    trace.add("skill_used", name=json.dumps(ev.get("input", {}))[:200])
            elif kind == "tool_result":
                trace.add("tool_result", name=ev.get("name"), output=str(ev.get("output", ""))[:4000],
                          is_error=bool(ev.get("is_error")))
            elif kind == "text":
                texts.append(ev.get("text", ""))
            elif kind == "result":
                final = ev
        if texts:
            trace.add("message", role="assistant", text="".join(texts).strip())
        if final is None:  # hermes itself failed to run: infra, not the agent's fault
            raise ProviderError(f"hermes crashed (no result event): {stderr.strip()[-600:]}")
        tok = final.get("tokens") or {}
        trace.add("model_call", input_tokens=tok.get("input", 0) + tok.get("cache_read", 0),
                  output_tokens=tok.get("output", 0), cache_read_tokens=tok.get("cache_read", 0),
                  latency_ms=final.get("duration_ms", 0), attempts=1, aggregated=True)
        err = final.get("error")
        if final.get("exit_code", 0) != 0 and err:
            if PROVIDER_ERROR.search(err):
                raise ProviderError(f"hermes: {err}")
            trace.add("error", kind="agent", message=err)
        trace.add("final_answer", text=final.get("text", "") if not err else "")


def _snapshot(folder: Path) -> dict[str, str]:
    if not folder.is_dir():
        return {}
    return {str(p.relative_to(folder)): p.read_text(errors="replace")
            for p in sorted(folder.rglob("*")) if p.is_file()}
