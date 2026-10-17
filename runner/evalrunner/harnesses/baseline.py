"""Baseline harness: a plain tool-calling loop we wrote ourselves.

Per session:  ask model -> run the tools it asked for -> feed results back -> repeat,
until it answers without a tool call (final answer) or hits max_steps / timeout.

Skills: names + one-line descriptions go in the system prompt; the model calls
        use_skill(name) to load the full text (logged as `skill_used`).
Memory: HOME/memory.md. If memory is "on", it is loaded at each session start
        (`memory_read`) and the model can append via memory_write (`memory_write`).
        Sessions within one trial share HOME; trials never do.
"""

from __future__ import annotations

import time
from pathlib import Path

from ..models import ModelOutputError, get_model
from ..schema import Trace, TrialContext
from . import tools as T
from .base import HarnessAdapter

SKILLS_DIR = Path(__file__).resolve().parents[3] / "skills"

SYSTEM = """You are an agent working inside a folder on a computer. Use the tools to inspect \
and change files. Work step by step. When the task is complete, reply with your final answer \
as plain text and no tool call."""


def load_skill(name: str) -> tuple[str, str]:
    """skills/<name>.md: first line is a one-line description, the rest is the instructions."""
    text = (SKILLS_DIR / f"{name}.md").read_text()
    desc = text.splitlines()[0].lstrip("# ").strip()
    return desc, text


class BaselineHarness(HarnessAdapter):
    id = "baseline"
    version = "1"
    description = "Our own minimal tool-calling loop: bash, read_file, write_file; skills on request; memory file."

    def __init__(self, model_factory=get_model):
        self.model_factory = model_factory  # swapped for a scripted model in tests

    def run_trial(self, ctx: TrialContext) -> Trace:
        s = ctx.config.settings
        model = self.model_factory(ctx.config.model)
        trace = Trace()
        deadline = time.time() + s.timeout_s
        memory_file = ctx.home_dir / "memory.md"
        memory_on = s.memory == "on"

        tool_names = [t for t in s.tools if t in T.TOOL_FUNCS]
        if memory_on:
            tool_names.append("memory_write")
        if s.skills:
            tool_names.append("use_skill")
        tool_schemas = [T.schema(n) for n in tool_names]

        for session_no, prompt in enumerate(ctx.task.sessions, start=1):
            trace.session = session_no
            system = SYSTEM
            if s.skills:
                lines = [f"- {n}: {load_skill(n)[0]}" for n in s.skills]
                system += "\n\nYou have these skills. Call use_skill(name) to read one before relying on it:\n" + "\n".join(lines)
            if memory_on:
                notes = memory_file.read_text() if memory_file.exists() else ""
                trace.add("memory_read", chars=len(notes), content=notes)
                system += "\n\nYour memory from earlier sessions:\n" + (notes or "(empty)")

            messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
            trace.add("message", role="user", text=prompt)
            answer = None

            for step in range(1, s.max_steps + 1):
                if time.time() > deadline:
                    trace.add("error", kind="timeout", message=f"trial exceeded {s.timeout_s}s")
                    break
                try:
                    resp = model.chat(messages, tool_schemas, temperature=s.temperature,
                                      max_tokens=s.max_tokens)  # ProviderError propagates: infra failure
                except ModelOutputError as e:
                    # the model produced an invalid tool call that the provider refused: the agent's mistake
                    trace.add("error", kind="bad_tool_args", message=str(e))
                    messages.append({"role": "user", "content": "Your last tool call was rejected because its "
                                     "arguments were not valid JSON for the tool's schema. Try again."})
                    continue
                trace.add("model_call", step=step, input_tokens=resp.input_tokens,
                          output_tokens=resp.output_tokens, latency_ms=resp.latency_ms,
                          attempts=resp.attempts, waited_ms=resp.waited_ms)
                messages.append(resp.assistant_message)
                if resp.text:
                    trace.add("message", role="assistant", text=resp.text)
                if not resp.tool_calls:
                    answer = resp.text
                    break
                for call in resp.tool_calls:
                    trace.add("tool_call", id=call.id, name=call.name, args=call.arguments)
                    output, is_error = self._run_tool(call.name, call.arguments, ctx, trace,
                                                      tool_names, memory_file)
                    trace.add("tool_result", id=call.id, name=call.name, output=output, is_error=is_error)
                    messages.append({"role": "tool", "tool_call_id": call.id, "content": output})
            else:
                trace.add("error", kind="step_exhaustion", message=f"no final answer after {s.max_steps} steps")

            trace.add("final_answer", text=answer or "")
            if answer is None and time.time() > deadline:
                break  # no time left for later sessions
        return trace

    def _run_tool(self, name, args, ctx, trace, allowed, memory_file) -> tuple[str, bool]:
        if name not in allowed:
            return f"error: unknown tool '{name}'. Available: {', '.join(allowed)}", True
        if "_raw" in args:
            return f"error: arguments were not valid JSON: {args['_raw'][:200]}", True
        if name == "memory_write":
            note = str(args.get("note", "")).strip()
            with memory_file.open("a") as f:
                f.write(note + "\n")
            trace.add("memory_write", note=note)
            return "saved to memory", False
        if name == "use_skill":
            skill = str(args.get("name", ""))
            if skill not in ctx.config.settings.skills:
                return f"error: no skill named '{skill}'", True
            trace.add("skill_used", name=skill)
            return load_skill(skill)[1], False
        return T.TOOL_FUNCS[name](ctx.sandbox_dir, ctx.home_dir, args)
