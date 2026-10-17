"""Scripted fake agent: no model, no cost. Proves the pipeline and the graders.

settings.extra["behavior"]:
  "solve" - copy reference/files/* into the sandbox and answer with reference/answer.txt
  "fail"  - do nothing and answer "I don't know"
"""

from __future__ import annotations

import shutil

from ..schema import Trace, TrialContext
from .base import HarnessAdapter


class MockHarness(HarnessAdapter):
    id = "mock"
    version = "1"
    description = "Scripted fake agent, no model, no cost: for testing the pipeline. settings.extra.behavior = solve | fail."
    settings = ()

    def run_trial(self, ctx: TrialContext) -> Trace:
        trace = Trace()
        behavior = ctx.config.settings.extra.get("behavior", "solve")
        ref = ctx.task.path / "reference"

        for i, prompt in enumerate(ctx.task.sessions, start=1):
            trace.session = i
            trace.add("message", role="user", text=prompt)
            if behavior == "solve":
                files = ref / "files"
                if files.is_dir():
                    for f in files.rglob("*"):
                        if f.is_file():
                            dest = ctx.sandbox_dir / f.relative_to(files)
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy(f, dest)
                            trace.add("tool_call", name="write_file", args={"path": str(dest.relative_to(ctx.sandbox_dir))})
                            trace.add("tool_result", name="write_file", output="ok", is_error=False)
                answer_file = ref / "answer.txt"
                answer = answer_file.read_text().strip() if answer_file.exists() else "done"
            else:
                answer = "I don't know"
            trace.add("final_answer", text=answer)
        return trace
