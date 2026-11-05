"""Data shapes for the tiered memory system."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class STMEntry:
    """One event captured during a session."""
    seq: int
    session: int
    type: str  # tool_call | tool_result | message | error | final_answer
    content: str
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> STMEntry:
        return cls(**d)


@dataclass
class Episode:
    """Findings extracted from one session's STM (no LLM — pattern extraction)."""
    session_no: int
    tool_calls: list[str]          # tool names invoked
    findings: list[str]            # extracted facts/observations
    files_written: list[str]       # files the agent wrote
    errors: list[str]              # error messages encountered
    final_answer: str
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Episode:
        return cls(**d)

    def as_text(self) -> str:
        lines = [f"Session {self.session_no}:"]
        if self.findings:
            lines.append("  Findings: " + "; ".join(self.findings))
        if self.tool_calls:
            lines.append("  Tools used: " + ", ".join(self.tool_calls))
        if self.files_written:
            lines.append("  Files written: " + ", ".join(self.files_written))
        if self.errors:
            lines.append("  Errors: " + "; ".join(self.errors))
        if self.final_answer:
            lines.append("  Answer: " + self.final_answer[:200])
        return "\n".join(lines)


@dataclass
class SemanticMemory:
    """Cross-episode insights distilled by an LLM from recent episodes."""
    insights: list[str]
    patterns: list[str]
    key_facts: list[str]
    source_episodes: list[int]
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> SemanticMemory:
        return cls(**d)

    def as_text(self) -> str:
        lines = []
        if self.key_facts:
            lines.append("Key facts: " + "; ".join(self.key_facts))
        if self.insights:
            lines.append("Insights: " + "; ".join(self.insights))
        if self.patterns:
            lines.append("Patterns: " + "; ".join(self.patterns))
        return "\n".join(lines)


class MemoryStore:
    """Manages the on-disk layout for one trial's tiered memory."""

    def __init__(self, base_dir: Path):
        self.base = base_dir / "memory"
        self.stm_dir = self.base / "stm"
        self.episodes_dir = self.base / "episodes"
        self.semantic_path = self.base / "semantic.json"

    def ensure_dirs(self) -> None:
        self.stm_dir.mkdir(parents=True, exist_ok=True)
        self.episodes_dir.mkdir(parents=True, exist_ok=True)

    # -- STM --

    def stm_path(self, session: int) -> Path:
        return self.stm_dir / f"session-{session}.jsonl"

    def append_stm(self, entry: STMEntry) -> None:
        self.ensure_dirs()
        with self.stm_path(entry.session).open("a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def read_stm(self, session: int) -> list[STMEntry]:
        p = self.stm_path(session)
        if not p.exists():
            return []
        entries = []
        for line in p.read_text().splitlines():
            if line.strip():
                entries.append(STMEntry.from_dict(json.loads(line)))
        return entries

    # -- Episodes --

    def episode_path(self, session: int) -> Path:
        return self.episodes_dir / f"episode-{session}.json"

    def save_episode(self, ep: Episode) -> None:
        self.ensure_dirs()
        self.episode_path(ep.session_no).write_text(json.dumps(ep.to_dict(), indent=2))

    def load_episode(self, session: int) -> Episode | None:
        p = self.episode_path(session)
        if not p.exists():
            return None
        return Episode.from_dict(json.loads(p.read_text()))

    def all_episodes(self) -> list[Episode]:
        if not self.episodes_dir.exists():
            return []
        eps = []
        for p in sorted(self.episodes_dir.glob("episode-*.json")):
            eps.append(Episode.from_dict(json.loads(p.read_text())))
        return eps

    def episode_count(self) -> int:
        if not self.episodes_dir.exists():
            return 0
        return len(list(self.episodes_dir.glob("episode-*.json")))

    # -- Semantic --

    def save_semantic(self, sem: SemanticMemory) -> None:
        self.semantic_path.write_text(json.dumps(sem.to_dict(), indent=2))

    def load_semantic(self) -> SemanticMemory | None:
        if not self.semantic_path.exists():
            return None
        return SemanticMemory.from_dict(json.loads(self.semantic_path.read_text()))
