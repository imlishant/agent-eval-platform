"""Data shapes and SQLite-backed store for the tiered memory system.

STM and episodic tiers are deterministic (regex/pattern extraction).
Only the semantic tier uses an LLM call.
"""

from __future__ import annotations

import json
import sqlite3
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
    tool_calls: list[str]
    findings: list[str]
    files_written: list[str]
    errors: list[str]
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


MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_stm (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trial_id INTEGER NOT NULL,
  session INTEGER NOT NULL,
  seq INTEGER NOT NULL,
  type TEXT NOT NULL,
  content TEXT NOT NULL,
  ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_episodes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trial_id INTEGER NOT NULL,
  session INTEGER NOT NULL,
  tool_calls TEXT NOT NULL,
  findings TEXT NOT NULL,
  files_written TEXT NOT NULL,
  errors TEXT NOT NULL,
  final_answer TEXT NOT NULL,
  ts REAL NOT NULL,
  UNIQUE(trial_id, session)
);
CREATE TABLE IF NOT EXISTS memory_semantic (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trial_id INTEGER NOT NULL,
  insights TEXT NOT NULL,
  patterns TEXT NOT NULL,
  key_facts TEXT NOT NULL,
  source_episodes TEXT NOT NULL,
  ts REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS stm_by_trial ON memory_stm(trial_id, session);
CREATE INDEX IF NOT EXISTS episodes_by_trial ON memory_episodes(trial_id);
CREATE INDEX IF NOT EXISTS semantic_by_trial ON memory_semantic(trial_id);
"""


class MemoryStore:
    """SQLite-backed store for one trial's tiered memory.

    When db_path and trial_id are provided, all reads/writes go to the DB.
    When they are None (e.g. standalone test runs), falls back to an in-memory
    SQLite database scoped to this instance.
    """

    def __init__(self, db_path: str | None = None, trial_id: int | None = None):
        self.trial_id = trial_id or 0
        if db_path:
            self._conn = sqlite3.connect(db_path, timeout=30)
            self._conn.execute("PRAGMA journal_mode = WAL")
        else:
            self._conn = sqlite3.connect(":memory:")
        self._conn.execute("PRAGMA foreign_keys = OFF")
        self._conn.executescript(MEMORY_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # -- STM --

    def append_stm(self, entry: STMEntry) -> None:
        self._conn.execute(
            "INSERT INTO memory_stm (trial_id, session, seq, type, content, ts) VALUES (?, ?, ?, ?, ?, ?)",
            (self.trial_id, entry.session, entry.seq, entry.type, entry.content, entry.ts),
        )
        self._conn.commit()

    def append_stm_batch(self, entries: list[STMEntry]) -> None:
        self._conn.executemany(
            "INSERT INTO memory_stm (trial_id, session, seq, type, content, ts) VALUES (?, ?, ?, ?, ?, ?)",
            [(self.trial_id, e.session, e.seq, e.type, e.content, e.ts) for e in entries],
        )
        self._conn.commit()

    def read_stm(self, session: int) -> list[STMEntry]:
        rows = self._conn.execute(
            "SELECT seq, session, type, content, ts FROM memory_stm WHERE trial_id = ? AND session = ? ORDER BY seq",
            (self.trial_id, session),
        ).fetchall()
        return [STMEntry(seq=r[0], session=r[1], type=r[2], content=r[3], ts=r[4]) for r in rows]

    # -- Episodes --

    def save_episode(self, ep: Episode) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO memory_episodes
               (trial_id, session, tool_calls, findings, files_written, errors, final_answer, ts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (self.trial_id, ep.session_no, json.dumps(ep.tool_calls), json.dumps(ep.findings),
             json.dumps(ep.files_written), json.dumps(ep.errors), ep.final_answer, ep.ts),
        )
        self._conn.commit()

    def load_episode(self, session: int) -> Episode | None:
        row = self._conn.execute(
            "SELECT session, tool_calls, findings, files_written, errors, final_answer, ts FROM memory_episodes WHERE trial_id = ? AND session = ?",
            (self.trial_id, session),
        ).fetchone()
        if not row:
            return None
        return Episode(
            session_no=row[0], tool_calls=json.loads(row[1]), findings=json.loads(row[2]),
            files_written=json.loads(row[3]), errors=json.loads(row[4]), final_answer=row[5], ts=row[6],
        )

    def all_episodes(self) -> list[Episode]:
        rows = self._conn.execute(
            "SELECT session, tool_calls, findings, files_written, errors, final_answer, ts FROM memory_episodes WHERE trial_id = ? ORDER BY session",
            (self.trial_id,),
        ).fetchall()
        return [
            Episode(session_no=r[0], tool_calls=json.loads(r[1]), findings=json.loads(r[2]),
                    files_written=json.loads(r[3]), errors=json.loads(r[4]), final_answer=r[5], ts=r[6])
            for r in rows
        ]

    def episode_count(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM memory_episodes WHERE trial_id = ?", (self.trial_id,),
        ).fetchone()
        return row[0] if row else 0

    # -- Semantic --

    def save_semantic(self, sem: SemanticMemory) -> None:
        # Delete previous semantic for this trial (refresh = replace)
        self._conn.execute("DELETE FROM memory_semantic WHERE trial_id = ?", (self.trial_id,))
        self._conn.execute(
            """INSERT INTO memory_semantic
               (trial_id, insights, patterns, key_facts, source_episodes, ts)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (self.trial_id, json.dumps(sem.insights), json.dumps(sem.patterns),
             json.dumps(sem.key_facts), json.dumps(sem.source_episodes), sem.ts),
        )
        self._conn.commit()

    def load_semantic(self) -> SemanticMemory | None:
        row = self._conn.execute(
            "SELECT insights, patterns, key_facts, source_episodes, ts FROM memory_semantic WHERE trial_id = ? ORDER BY id DESC LIMIT 1",
            (self.trial_id,),
        ).fetchone()
        if not row:
            return None
        return SemanticMemory(
            insights=json.loads(row[0]), patterns=json.loads(row[1]),
            key_facts=json.loads(row[2]), source_episodes=json.loads(row[3]), ts=row[4],
        )

    def snapshot(self) -> dict:
        """Dump the full memory state for inspection."""
        result: dict = {"episodes": [], "semantic": None, "stm_sessions": []}
        for ep in self.all_episodes():
            result["episodes"].append(ep.to_dict())
        sem = self.load_semantic()
        if sem:
            result["semantic"] = sem.to_dict()
        # Group STM by session
        rows = self._conn.execute(
            "SELECT DISTINCT session FROM memory_stm WHERE trial_id = ? ORDER BY session",
            (self.trial_id,),
        ).fetchall()
        for (session,) in rows:
            entries = self.read_stm(session)
            result["stm_sessions"].append({
                "session": session,
                "entries": [e.to_dict() for e in entries],
            })
        return result
