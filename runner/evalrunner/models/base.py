"""The model contract. A new provider = subclass + one entry in models/__init__.py."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ProviderError(Exception):
    """Infrastructure failed, not the agent: the provider (rate limit, 5xx, network) even after
    retries, or the harness program itself crashed. The trial is marked `invalid` and left out
    of the comparison instead of being scored 0.
    """


class ModelOutputError(Exception):
    """The provider rejected what the MODEL produced (e.g. a tool call with invalid JSON arguments).

    This is an agent mistake, not an infra failure: the harness records it as `bad_tool_args`,
    tells the model, and the step counts. Retrying the trial instead would hide the mistake and
    inflate the score of the model that makes it.
    """


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict   # parsed JSON; {"_raw": text} if the model sent invalid JSON


@dataclass
class ModelResponse:
    text: str
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    attempts: int                 # 1 = no retries were needed
    waited_ms: int = 0            # time spent waiting out rate limits before retries (not the agent's speed)
    assistant_message: dict = field(default_factory=dict)  # append this to the conversation as-is


class ModelAdapter(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], tools: list[dict], *,
             temperature: float, max_tokens: int) -> ModelResponse:
        """One model request. Raises ProviderError when retries are exhausted."""
