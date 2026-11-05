"""Short-term memory collector: captures trace events during a session.

No LLM calls — just filters and stores relevant events from the trace.
"""

from __future__ import annotations

from ..schema import Trace, TraceEvent
from .schema import MemoryStore, STMEntry

CAPTURED_TYPES = {"tool_call", "tool_result", "message", "error", "final_answer"}


def collect_stm(trace: Trace, session: int, store: MemoryStore) -> list[STMEntry]:
    """Extract STM entries from a trace for the given session and persist them."""
    entries = []
    for ev in trace.events:
        if ev.session != session or ev.type not in CAPTURED_TYPES:
            continue
        content = _format_event(ev)
        if not content:
            continue
        entries.append(STMEntry(seq=ev.seq, session=session, type=ev.type, content=content, ts=ev.ts))
    if entries:
        store.append_stm_batch(entries)
    return entries


def _format_event(ev: TraceEvent) -> str:
    p = ev.payload
    if ev.type == "tool_call":
        name = p.get("name", "unknown")
        args = p.get("args", {})
        if isinstance(args, dict):
            args_str = ", ".join(f"{k}={repr(v)[:80]}" for k, v in args.items())
        else:
            args_str = str(args)[:200]
        return f"tool_call: {name}({args_str})"
    if ev.type == "tool_result":
        name = p.get("name", "unknown")
        output = str(p.get("output", ""))[:300]
        err = " [ERROR]" if p.get("is_error") else ""
        return f"tool_result: {name}{err} -> {output}"
    if ev.type == "message":
        role = p.get("role", "")
        text = p.get("text", "")[:500]
        if role == "user" and text:
            return f"user: {text}"
        if role == "assistant" and text:
            return f"assistant: {text}"
        return ""
    if ev.type == "error":
        return f"error ({p.get('kind', 'unknown')}): {p.get('message', '')[:300]}"
    if ev.type == "final_answer":
        text = p.get("text", "")[:500]
        return f"final_answer: {text}" if text else ""
    return ""
