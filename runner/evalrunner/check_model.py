"""Test a model entry before using it: one request with a tool, report what happened.

Usage:  echo '{"provider": ..., "id": ..., "base_url": ..., "api_key_env": ...}' | python -m evalrunner.check_model
Prints {"ok": bool, "latency_ms": int, "tool_calling": bool, "message": str}. Never prints the key.
"""

from __future__ import annotations

import json
import sys
import time

from .isolation import scrub
from .models import ModelOutputError, ProviderError, get_model
from .schema import ModelSpec

TOOL = {"type": "function", "function": {"name": "read_file", "description": "Read a file",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}


def check(spec: ModelSpec) -> dict:
    started = time.time()
    try:
        model = get_model(spec)
        r = model.chat([{"role": "user", "content": "What is in notes.txt? Use the tool."}], [TOOL],
                       temperature=0, max_tokens=300)
    except (ProviderError, ModelOutputError, ValueError) as e:
        return {"ok": False, "latency_ms": int((time.time() - started) * 1000), "tool_calling": False, "message": str(e)[:400]}
    tool_ok = any(c.name == "read_file" for c in r.tool_calls)
    return {"ok": True, "latency_ms": r.latency_ms, "tool_calling": tool_ok,
            "message": "model answered and called the tool" if tool_ok else "model answered but did not call the tool (agents need tool calling)"}


if __name__ == "__main__":
    print(json.dumps(scrub(check(ModelSpec(**json.load(sys.stdin))))))
