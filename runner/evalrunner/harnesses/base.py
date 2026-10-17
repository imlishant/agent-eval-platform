"""The harness contract. A new harness = subclass + one entry in harnesses/__init__.py."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..schema import Trace, TrialContext


class HarnessAdapter(ABC):
    id: str
    version: str
    description: str = ""
    # which config settings this harness actually uses (the UI greys out the rest)
    settings: tuple[str, ...] = ("skills", "memory", "tools", "temperature", "max_steps", "max_tokens", "timeout_s")
    requirements: str = ""

    @abstractmethod
    def run_trial(self, ctx: TrialContext) -> Trace:
        """Run every session of ctx.task in ctx.sandbox_dir.

        Must not raise when the *agent* fails (wrong answer, step limit, timeout):
        record an `error` event and return the trace. Raise only for infra problems
        (provider down, bad config) so the runner can retry or mark the trial invalid.
        """
