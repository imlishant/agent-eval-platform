"""Shared data shapes for one trial. The API mirrors these in TypeScript.

Config  = what is being evaluated (harness + model + settings). ID = hash of its content.
Task    = what the agent is asked to do and how it is graded.
Trace   = everything the agent did, as an ordered list of events.
Grade   = one grader's verdict on the finished trial.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

EVENT_TYPES = {
    "message",       # text from user or agent
    "model_call",    # one request to the model: tokens, latency
    "tool_call",     # agent asked to run a tool
    "tool_result",   # what the tool returned
    "memory_read",   # memory loaded into context
    "memory_write",  # agent saved something to memory
    "skill_used",    # agent used a skill
    "error",         # something went wrong (agent or infra)
    "final_answer",  # agent's last answer for a session
}


@dataclass
class ModelSpec:
    provider: str                  # adapter id, e.g. "openai_compat"
    id: str                        # model name at that provider
    base_url: str | None = None
    api_key_env: str | None = None  # name of env var holding the key, never the key


@dataclass
class Settings:
    skills: list[str] = field(default_factory=list)
    memory: str = "off"            # "off" | "on"
    tools: list[str] = field(default_factory=lambda: ["bash", "read_file", "write_file"])
    temperature: float = 0.7
    max_steps: int = 20
    max_tokens: int = 4000
    timeout_s: int = 180
    extra: dict[str, Any] = field(default_factory=dict)  # harness-specific knobs


@dataclass
class Config:
    name: str
    harness: str
    model: ModelSpec
    settings: Settings

    @classmethod
    def from_dict(cls, d: dict) -> Config:
        return cls(
            name=d["name"],
            harness=d["harness"],
            model=ModelSpec(**d["model"]),
            settings=Settings(**d.get("settings", {})),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def config_id(self) -> str:
        """Same content => same ID. `name` is a label, so it is left out."""
        body = {k: v for k, v in self.to_dict().items() if k != "name"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]


@dataclass
class Task:
    id: str
    category: str
    sessions: list[str]
    graders: list[dict]
    path: Path

    @classmethod
    def load(cls, task_dir: str | Path) -> Task:
        task_dir = Path(task_dir)
        d = yaml.safe_load((task_dir / "task.yaml").read_text())
        return cls(id=d["id"], category=d["category"], sessions=d["sessions"],
                   graders=d["graders"], path=task_dir)

    def content_hash(self) -> str:
        """Hash of every file in the task folder, so a changed task gets a new hash."""
        h = hashlib.sha256()
        for f in sorted(p for p in self.path.rglob("*") if p.is_file()):
            h.update(str(f.relative_to(self.path)).encode())
            h.update(f.read_bytes())
        return h.hexdigest()[:12]


@dataclass
class TraceEvent:
    seq: int
    session: int
    type: str
    ts: float
    payload: dict


class Trace:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []
        self.session = 1

    def add(self, type: str, **payload: Any) -> TraceEvent:
        if type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {type}")
        ev = TraceEvent(seq=len(self.events), session=self.session, type=type,
                        ts=time.time(), payload=payload)
        self.events.append(ev)
        return ev

    def final_answer(self, session: int | None = None) -> str:
        """Last final_answer text (of a given session, or of the whole trial)."""
        for ev in reversed(self.events):
            if ev.type == "final_answer" and (session is None or ev.session == session):
                return ev.payload.get("text", "")
        return ""

    def usage(self) -> dict:
        calls = [e.payload for e in self.events if e.type == "model_call"]
        return {
            "input_tokens": sum(c.get("input_tokens", 0) for c in calls),
            "output_tokens": sum(c.get("output_tokens", 0) for c in calls),
            "model_calls": len(calls),
        }

    def to_list(self) -> list[dict]:
        return [asdict(e) for e in self.events]


@dataclass
class TrialContext:
    task: Task
    config: Config
    sandbox_dir: Path   # agent's working folder (copy of task fixtures)
    home_dir: Path      # agent's private HOME: memory, harness state
    trial_index: int = 0


@dataclass
class Grade:
    grader: str
    score: float        # 0.0 .. 1.0
    passed: bool
    reasoning: str
