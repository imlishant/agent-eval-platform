"""Semantic memory: distill insights from recent episodes using an LLM call.

This is the ONLY tier that uses an LLM. It reads the latest N episodes,
sends them to the model with a distillation prompt, and parses the structured output.
"""

from __future__ import annotations

import json
import re

from ..models.base import ModelAdapter
from .schema import Episode, MemoryStore, SemanticMemory

DISTILL_PROMPT = """\
You are a memory consolidation system. Below are episode summaries from an AI agent's recent sessions.

Extract:
1. **Key facts** — concrete, reusable facts (server names, conventions, code words, file paths, config values).
2. **Insights** — observations about what worked or failed.
3. **Patterns** — recurring behaviors or themes across episodes.

Respond in EXACTLY this JSON format, nothing else:
{
  "key_facts": ["fact1", "fact2"],
  "insights": ["insight1", "insight2"],
  "patterns": ["pattern1", "pattern2"]
}

Episodes:
"""

DEFAULT_SEMANTIC_THRESHOLD = 5
DEFAULT_SEMANTIC_REFRESH = 5


def should_refresh_semantic(store: MemoryStore, threshold: int = DEFAULT_SEMANTIC_THRESHOLD,
                            refresh_interval: int = DEFAULT_SEMANTIC_REFRESH) -> bool:
    """True when semantic memory should be (re)generated: at threshold, then every refresh_interval."""
    count = store.episode_count()
    if count < threshold:
        return False
    sem = store.load_semantic()
    if sem is None:
        return True
    # Refresh every N episodes after the initial generation
    episodes_since = count - max(sem.source_episodes) if sem.source_episodes else count
    return episodes_since >= refresh_interval


def consolidate_semantic(store: MemoryStore, model: ModelAdapter,
                         episode_window: int = DEFAULT_SEMANTIC_THRESHOLD) -> SemanticMemory | None:
    """Distill the latest episodes into semantic memory (replaces previous semantic)."""
    episodes = store.all_episodes()
    if len(episodes) < episode_window:
        return None

    recent = episodes[-episode_window:]
    prompt = DISTILL_PROMPT + "\n\n".join(ep.as_text() for ep in recent)

    messages = [
        {"role": "system", "content": "You are a precise JSON-only responder. Output valid JSON and nothing else."},
        {"role": "user", "content": prompt},
    ]
    resp = model.chat(messages, tools=[], temperature=0.0, max_tokens=1000)
    parsed = _parse_response(resp.text)

    sem = SemanticMemory(
        insights=parsed.get("insights", []),
        patterns=parsed.get("patterns", []),
        key_facts=parsed.get("key_facts", []),
        source_episodes=[ep.session_no for ep in recent],
    )
    store.save_semantic(sem)
    return sem


def _parse_response(text: str) -> dict:
    """Extract JSON from model response, tolerating markdown fences."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    try:
        d = json.loads(text)
        if isinstance(d, dict):
            return d
    except json.JSONDecodeError:
        pass
    # Fallback: try to find a JSON object anywhere in the text
    m = re.search(r"\{[^{}]*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {"key_facts": [], "insights": [], "patterns": []}
