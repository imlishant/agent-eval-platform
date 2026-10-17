"""One adapter for every OpenAI-compatible endpoint: Ollama, Groq, Gemini, OpenRouter, OpenAI.

The provider is just data in the config: base_url + model id + name of the key env var.
"""

from __future__ import annotations

import json
import os
import random
import re
import time

import openai

from ..schema import ModelSpec
from .base import ModelAdapter, ModelOutputError, ModelResponse, ProviderError, ToolCall

# provider messages meaning "the model generated an invalid tool call" (seen on Groq; similar on others)
BAD_GENERATION = re.compile(r"tool call|tool_use_failed|failed_generation|function call|arguments as JSON", re.I)
RETRYABLE = (openai.RateLimitError, openai.APIConnectionError,
             openai.APITimeoutError, openai.InternalServerError)
MAX_ATTEMPTS = 4
MAX_WAIT_S = 65  # Gemini per-minute quotas can need close to a minute


class OpenAICompatAdapter(ModelAdapter):
    def __init__(self, spec: ModelSpec, sleep=time.sleep):
        key = os.environ.get(spec.api_key_env, "") if spec.api_key_env else "not-needed"
        if spec.api_key_env and not key:
            raise ProviderError(f"env var {spec.api_key_env} is not set")
        # max_retries=0: we retry ourselves so attempts are counted in the trace
        self.client = openai.OpenAI(base_url=spec.base_url, api_key=key,
                                    max_retries=0, timeout=120)
        self.model = spec.id
        self.sleep = sleep

    def chat(self, messages, tools, *, temperature, max_tokens) -> ModelResponse:
        kwargs = dict(model=self.model, messages=messages, temperature=temperature,
                      max_tokens=max_tokens)
        if tools:
            kwargs["tools"] = tools
        waited = 0.0
        for attempt in range(1, MAX_ATTEMPTS + 1):
            started = time.time()
            try:
                r = self.client.chat.completions.create(**kwargs)
                break
            except RETRYABLE as e:
                if attempt == MAX_ATTEMPTS:
                    raise ProviderError(f"{type(e).__name__} after {attempt} attempts: {e}") from e
                pause = _wait_seconds(e, attempt)
                waited += pause
                self.sleep(pause)
            except openai.BadRequestError as e:
                if BAD_GENERATION.search(str(e.message)):
                    raise ModelOutputError(str(e.message)[:500]) from e  # the agent's mistake
                raise ProviderError(f"HTTP {e.status_code}: {e.message}") from e
            except openai.APIStatusError as e:  # other 4xx: retrying will not help
                raise ProviderError(f"HTTP {e.status_code}: {e.message}") from e

        msg = r.choices[0].message
        calls = [ToolCall(tc.id, tc.function.name, _parse_args(tc.function.arguments))
                 for tc in (msg.tool_calls or [])]
        return ModelResponse(
            text=msg.content or "",
            tool_calls=calls,
            input_tokens=getattr(r.usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(r.usage, "completion_tokens", 0) or 0,
            latency_ms=int((time.time() - started) * 1000),
            attempts=attempt,
            waited_ms=int(waited * 1000),
            # keep provider extras (e.g. Gemini thought signatures) so the next turn is valid
            assistant_message=_replayable(msg.model_dump(exclude_none=True)),
        )


def _replayable(m: dict) -> dict:
    """Only fields every provider accepts back. Gemini thought signatures live inside
    tool_calls[].extra_content, so they survive; provider-only fields like `reasoning` do not."""
    return {k: v for k, v in m.items() if k in ("role", "content", "tool_calls")}


def _parse_args(raw: str | None) -> dict:
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {"_raw": raw}
    except json.JSONDecodeError:
        return {"_raw": raw}


def _wait_seconds(err: Exception, attempt: int) -> float:
    """Honour the provider's retry-after if given, else exponential backoff with jitter."""
    resp = getattr(err, "response", None)
    header = resp.headers.get("retry-after") if resp is not None else None
    try:
        if header:
            return min(float(header) + random.uniform(0, 1), MAX_WAIT_S)
    except ValueError:
        pass
    return min(2 ** attempt + random.uniform(0, 1), MAX_WAIT_S)
