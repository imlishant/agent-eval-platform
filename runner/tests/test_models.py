"""Retry policy of the OpenAI-compatible adapter, with a fake client (no network)."""

import httpx2 as httpx
import openai
import pytest

from evalrunner.models import ProviderError
from evalrunner.models.openai_compat import MAX_ATTEMPTS, OpenAICompatAdapter
from evalrunner.schema import ModelSpec


def rate_limit():
    req = httpx.Request("POST", "http://x")
    return openai.RateLimitError("slow down", response=httpx.Response(429, request=req, headers={"retry-after": "2"}), body=None)


def bad_request():
    req = httpx.Request("POST", "http://x")
    return openai.BadRequestError("bad", response=httpx.Response(400, request=req), body=None)


class FakeCompletions:
    def __init__(self, outcomes):
        self.outcomes, self.calls = list(outcomes), 0

    def create(self, **kw):
        self.calls += 1
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return o


def adapter(outcomes):
    waits = []
    a = OpenAICompatAdapter(ModelSpec("openai_compat", "m", "http://x"), sleep=waits.append)
    fake = FakeCompletions(outcomes)
    a.client = type("C", (), {"chat": type("Ch", (), {"completions": fake})()})()
    return a, fake, waits


def ok_response():
    from openai.types.chat import ChatCompletion
    return ChatCompletion.model_validate({
        "id": "1", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "hi", "reasoning": "secret"}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}})


def test_retries_rate_limit_then_succeeds_and_counts_attempts():
    a, fake, waits = adapter([rate_limit(), rate_limit(), ok_response()])
    r = a.chat([], [], temperature=0, max_tokens=10)
    assert r.text == "hi" and r.attempts == 3 and fake.calls == 3
    assert all(2 <= w <= 3 for w in waits)                 # honoured retry-after: 2
    assert r.waited_ms == int(sum(waits) * 1000)           # waiting is reported, so latency can exclude it
    assert "reasoning" not in r.assistant_message          # provider-only field dropped


def test_gives_up_after_max_attempts():
    a, fake, _ = adapter([rate_limit()] * MAX_ATTEMPTS)
    with pytest.raises(ProviderError):
        a.chat([], [], temperature=0, max_tokens=10)
    assert fake.calls == MAX_ATTEMPTS


def test_does_not_retry_bad_request():
    a, fake, _ = adapter([bad_request()])
    with pytest.raises(ProviderError):
        a.chat([], [], temperature=0, max_tokens=10)
    assert fake.calls == 1


def test_bad_tool_call_from_model_is_not_retried_and_not_infra():
    from evalrunner.models import ModelOutputError
    req = httpx.Request("POST", "http://x")
    err = openai.BadRequestError("Failed to parse tool call arguments as JSON",
                                 response=httpx.Response(400, request=req), body=None)
    a, fake, _ = adapter([err])
    with pytest.raises(ModelOutputError):
        a.chat([], [], temperature=0, max_tokens=10)
    assert fake.calls == 1
