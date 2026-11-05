"""Warm-start builder: decides what memory to inject into a session's context.

Logic:
  - Episodes >= 5 and semantic.json exists → use semantic summary
  - Episodes 1..4 → use up to 3 most recent episode summaries
  - No episodes (session 1) → empty string
"""

from __future__ import annotations

from .schema import MemoryStore

MAX_RECENT_EPISODES = 3


def build_warmstart(store: MemoryStore, current_session: int) -> str:
    """Return the text to inject into the agent's context as memory."""
    sem = store.load_semantic()
    episode_count = store.episode_count()

    if episode_count >= 5 and sem is not None:
        return _format_semantic(sem)

    if episode_count > 0:
        return _format_recent_episodes(store, episode_count)

    return ""


def _format_semantic(sem) -> str:
    lines = ["[Memory — consolidated from recent sessions]"]
    if sem.key_facts:
        lines.append("\nKey facts:")
        for f in sem.key_facts:
            lines.append(f"  - {f}")
    if sem.insights:
        lines.append("\nInsights:")
        for i in sem.insights:
            lines.append(f"  - {i}")
    if sem.patterns:
        lines.append("\nPatterns:")
        for p in sem.patterns:
            lines.append(f"  - {p}")
    return "\n".join(lines)


def _format_recent_episodes(store: MemoryStore, episode_count: int) -> str:
    episodes = store.all_episodes()
    recent = episodes[-MAX_RECENT_EPISODES:]
    lines = [f"[Memory — last {len(recent)} session(s)]"]
    for ep in recent:
        lines.append("")
        lines.append(ep.as_text())
    return "\n".join(lines)
