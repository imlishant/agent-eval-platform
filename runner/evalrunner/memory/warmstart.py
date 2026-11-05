"""Warm-start builder: decides what memory to inject into a session's context.

Logic:
  - Always include up to `max_recent` latest episode summaries
  - If semantic memory exists, prepend it before the episodes
  - No episodes (session 1) → empty string
"""

from __future__ import annotations

from .schema import MemoryStore

DEFAULT_WARMSTART_EPISODES = 3


def build_warmstart(store: MemoryStore, current_session: int,
                    max_recent: int = DEFAULT_WARMSTART_EPISODES) -> str:
    """Return the text to inject into the agent's context as memory."""
    parts: list[str] = []

    sem = store.load_semantic()
    if sem is not None:
        parts.append(_format_semantic(sem))

    episode_count = store.episode_count()
    if episode_count > 0:
        parts.append(_format_recent_episodes(store, max_recent))

    return "\n\n".join(parts)


def _format_semantic(sem) -> str:
    lines = ["[Consolidated memory]"]
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


def _format_recent_episodes(store: MemoryStore, max_recent: int) -> str:
    episodes = store.all_episodes()
    recent = episodes[-max_recent:]
    lines = [f"[Recent sessions ({len(recent)})]"]
    for ep in recent:
        lines.append("")
        lines.append(ep.as_text())
    return "\n".join(lines)
