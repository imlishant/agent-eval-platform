"""Tests for the tiered memory module (STM, episodic, semantic, warmstart)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evalrunner.memory.episodic import consolidate_episode
from evalrunner.memory.schema import Episode, MemoryStore, SemanticMemory, STMEntry
from evalrunner.memory.semantic import _parse_response, consolidate_semantic
from evalrunner.memory.stm import collect_stm
from evalrunner.memory.warmstart import build_warmstart
from evalrunner.schema import Trace


@pytest.fixture
def store(tmp_path):
    s = MemoryStore(tmp_path)
    s.ensure_dirs()
    return s


# ── STM ──────────────────────────────────────────────────────────────────

class TestSTM:
    def test_collect_from_trace(self, store):
        trace = Trace()
        trace.session = 1
        trace.add("message", role="user", text="hello")
        trace.add("tool_call", name="bash", args={"cmd": "ls"})
        trace.add("tool_result", name="bash", output="file.txt", is_error=False)
        trace.add("message", role="assistant", text="I see file.txt")
        trace.add("final_answer", text="done")
        # model_call should be ignored (not in CAPTURED_TYPES)
        trace.add("model_call", input_tokens=100, output_tokens=50, latency_ms=500, attempts=1)

        entries = collect_stm(trace, 1, store)
        assert len(entries) == 4  # tool_call, tool_result, assistant message, final_answer
        types = [e.type for e in entries]
        assert "tool_call" in types
        assert "tool_result" in types
        assert "message" in types
        assert "final_answer" in types

    def test_stm_persists_to_disk(self, store):
        entry = STMEntry(seq=0, session=1, type="tool_call", content="tool_call: bash(cmd='ls')")
        store.append_stm(entry)
        loaded = store.read_stm(1)
        assert len(loaded) == 1
        assert loaded[0].content == "tool_call: bash(cmd='ls')"

    def test_stm_empty_session(self, store):
        assert store.read_stm(99) == []


# ── Episodic ─────────────────────────────────────────────────────────────

class TestEpisodic:
    def test_consolidate_extracts_tool_names(self, store):
        trace = Trace()
        trace.session = 1
        trace.add("tool_call", name="bash", args={"cmd": "ls"})
        trace.add("tool_result", name="bash", output="ok", is_error=False)
        trace.add("tool_call", name="write_file", args={"path": "out.txt", "content": "hi"})
        trace.add("tool_result", name="write_file", output="wrote 2 chars to out.txt", is_error=False)
        trace.add("final_answer", text="done writing")
        collect_stm(trace, 1, store)

        ep = consolidate_episode(1, store)
        assert "bash" in ep.tool_calls
        assert "write_file" in ep.tool_calls
        assert "out.txt" in ep.files_written
        assert ep.final_answer == "done writing"

    def test_consolidate_extracts_facts(self, store):
        trace = Trace()
        trace.session = 1
        trace.add("message", role="assistant",
                  text="Remember: the server host is stg-eu-04.internal and port is 7443")
        trace.add("final_answer", text="noted")
        collect_stm(trace, 1, store)

        ep = consolidate_episode(1, store)
        # Should extract at least one fact about the server
        all_text = " ".join(ep.findings).lower()
        assert "stg-eu-04" in all_text or len(ep.findings) > 0

    def test_consolidate_captures_errors(self, store):
        trace = Trace()
        trace.session = 1
        trace.add("error", kind="timeout", message="trial exceeded 180s")
        trace.add("final_answer", text="")
        collect_stm(trace, 1, store)

        ep = consolidate_episode(1, store)
        assert len(ep.errors) == 1
        assert "timeout" in ep.errors[0] or "180s" in ep.errors[0]

    def test_episode_persists(self, store):
        ep = Episode(session_no=1, tool_calls=["bash"], findings=["fact1"],
                     files_written=["a.txt"], errors=[], final_answer="ok")
        store.save_episode(ep)
        loaded = store.load_episode(1)
        assert loaded is not None
        assert loaded.findings == ["fact1"]

    def test_episode_as_text(self):
        ep = Episode(session_no=2, tool_calls=["bash"], findings=["the host is xyz"],
                     files_written=["deploy.env"], errors=[], final_answer="done")
        text = ep.as_text()
        assert "Session 2" in text
        assert "xyz" in text


# ── Semantic ─────────────────────────────────────────────────────────────

class TestSemantic:
    def test_parse_clean_json(self):
        result = _parse_response('{"key_facts": ["a"], "insights": ["b"], "patterns": ["c"]}')
        assert result["key_facts"] == ["a"]

    def test_parse_fenced_json(self):
        result = _parse_response('```json\n{"key_facts": ["a"], "insights": [], "patterns": []}\n```')
        assert result["key_facts"] == ["a"]

    def test_parse_garbage(self):
        result = _parse_response("no json here at all")
        assert result == {"key_facts": [], "insights": [], "patterns": []}

    def test_needs_5_episodes(self, store):
        for i in range(1, 4):
            store.save_episode(Episode(session_no=i, tool_calls=[], findings=[f"fact-{i}"],
                                       files_written=[], errors=[], final_answer=""))
        # Mock model not needed — should return None before calling it
        result = consolidate_semantic(store, model=None)
        assert result is None

    def test_consolidate_with_mock_model(self, store):
        for i in range(1, 6):
            store.save_episode(Episode(session_no=i, tool_calls=["bash"], findings=[f"fact-{i}"],
                                       files_written=[], errors=[], final_answer=f"answer-{i}"))

        class MockModel:
            def chat(self, messages, tools, *, temperature, max_tokens):
                class R:
                    text = '{"key_facts": ["consolidated-fact"], "insights": ["it works"], "patterns": ["always bash"]}'
                    tool_calls = []
                    input_tokens = 100
                    output_tokens = 50
                    latency_ms = 200
                    attempts = 1
                return R()

        sem = consolidate_semantic(store, MockModel())
        assert sem is not None
        assert "consolidated-fact" in sem.key_facts
        assert sem.source_episodes == [1, 2, 3, 4, 5]

    def test_semantic_persists(self, store):
        sem = SemanticMemory(insights=["i1"], patterns=["p1"], key_facts=["f1"],
                             source_episodes=[1, 2, 3, 4, 5])
        store.save_semantic(sem)
        loaded = store.load_semantic()
        assert loaded is not None
        assert loaded.key_facts == ["f1"]


# ── Warmstart ────────────────────────────────────────────────────────────

class TestWarmstart:
    def test_empty_on_first_session(self, store):
        assert build_warmstart(store, 1) == ""

    def test_recent_episodes_when_under_5(self, store):
        for i in range(1, 4):
            store.save_episode(Episode(session_no=i, tool_calls=["bash"], findings=[f"fact-{i}"],
                                       files_written=[], errors=[], final_answer=""))
        text = build_warmstart(store, 4)
        assert "fact-1" in text
        assert "fact-3" in text
        assert "[Memory" in text

    def test_uses_semantic_after_5_episodes(self, store):
        for i in range(1, 6):
            store.save_episode(Episode(session_no=i, tool_calls=[], findings=[f"fact-{i}"],
                                       files_written=[], errors=[], final_answer=""))
        sem = SemanticMemory(insights=["big-insight"], patterns=["recurring-pattern"],
                             key_facts=["distilled-fact"], source_episodes=[1, 2, 3, 4, 5])
        store.save_semantic(sem)
        text = build_warmstart(store, 6)
        assert "distilled-fact" in text
        assert "big-insight" in text
        assert "consolidated" in text.lower() or "Memory" in text

    def test_falls_back_to_episodes_if_no_semantic(self, store):
        for i in range(1, 6):
            store.save_episode(Episode(session_no=i, tool_calls=[], findings=[f"fact-{i}"],
                                       files_written=[], errors=[], final_answer=""))
        # No semantic.json
        text = build_warmstart(store, 6)
        assert "fact-" in text
        assert "session" in text.lower()
