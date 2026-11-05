"""Episodic memory: extract findings from STM using regex/pattern matching.

No LLM calls — deterministic extraction of facts, tool usage, files, and errors.
"""

from __future__ import annotations

import re

from .schema import Episode, MemoryStore, STMEntry

# Patterns to extract factual content from user prompts, assistant messages, and tool results.
# Each pattern captures a group that becomes a finding.
FACT_PATTERNS = [
    # "the X is Y" — captures value up to sentence end, "Remember", or list separator
    re.compile(r"(?:the|our|its)\s+([\w\s]{2,30}?)\s+(?:is|are|=)\s+(\S(?:(?!\.\s|[,;]|\bRemember\b|\bNothing\b).)*\S)", re.I),
    # "remember/note/important: ..."
    re.compile(r"(?:remember|note|important|convention|rule|always|never|must)[:\s]+(.{10,200})", re.I),
    # "set/use/changed to/updated to ..."
    re.compile(r"(?:set|use|changed?\s+to|updated?\s+to|migrated?\s+to|moved?\s+to)\s+(\S.{5,150})", re.I),
    # "name is X" for service/config definitions — two groups: (key, value)
    re.compile(r"((?:name|port|host|path|branch|endpoint|prefix|token|header|user))\s+(?:is|=|:)\s+(\S.{0,100}?)(?:\.|,|;|\s*$)", re.I | re.M),
]

FILE_WRITE_PATTERN = re.compile(r"tool_call: (?:write_file|bash)\(.*?(?:path|>)\s*=?\s*['\"]?([^\s,'\")\]]+)")
WROTE_PATTERN = re.compile(r"wrote \d+ chars to (.+)")


def consolidate_episode(session: int, store: MemoryStore) -> Episode:
    """Build an Episode from the STM of one session using pattern extraction."""
    entries = store.read_stm(session)
    if not entries:
        return Episode(session_no=session, tool_calls=[], findings=[], files_written=[], errors=[], final_answer="")

    tool_calls: list[str] = []
    findings: list[str] = []
    files_written: list[str] = []
    errors: list[str] = []
    final_answer = ""

    seen_findings: set[str] = set()

    for entry in entries:
        if entry.type == "tool_call":
            name = _extract_tool_name(entry.content)
            if name and name not in tool_calls:
                tool_calls.append(name)

        if entry.type == "tool_result":
            _extract_file_writes(entry.content, files_written)

        if entry.type == "error":
            err_text = entry.content.replace("error ", "", 1).strip()[:200]
            if err_text and err_text not in errors:
                errors.append(err_text)

        if entry.type == "final_answer":
            text = entry.content.replace("final_answer: ", "", 1).strip()
            if text:
                final_answer = text[:500]

        # Extract facts from assistant messages and tool results
        if entry.type in ("message", "tool_result", "tool_call"):
            for fact in _extract_facts(entry.content):
                normalized = fact.strip().lower()
                if normalized not in seen_findings:
                    seen_findings.add(normalized)
                    findings.append(fact.strip())

    # Also extract facts from the user prompt if it was captured
    for entry in entries:
        if entry.type == "message" and entry.content.startswith("assistant:"):
            for fact in _extract_from_assistant(entry.content):
                normalized = fact.strip().lower()
                if normalized not in seen_findings:
                    seen_findings.add(normalized)
                    findings.append(fact.strip())

    ep = Episode(
        session_no=session,
        tool_calls=tool_calls,
        findings=findings[:20],
        files_written=list(dict.fromkeys(files_written)),
        errors=errors[:10],
        final_answer=final_answer,
    )
    store.save_episode(ep)
    return ep


def _extract_tool_name(content: str) -> str:
    m = re.match(r"tool_call:\s*(\w+)", content)
    return m.group(1) if m else ""


def _extract_file_writes(content: str, out: list[str]) -> None:
    for m in WROTE_PATTERN.finditer(content):
        path = m.group(1).strip()
        if path and path not in out:
            out.append(path)
    for m in FILE_WRITE_PATTERN.finditer(content):
        path = m.group(1).strip()
        if path and path not in out:
            out.append(path)


NOISE_PHRASES = {"this for later", "assistant: noted", "assistant: done", "assistant: ok",
                  "nothing else to do", "nothing else to do now", "for later sessions"}


def _extract_facts(content: str) -> list[str]:
    facts = []
    for pat in FACT_PATTERNS:
        for m in pat.finditer(content):
            groups = m.groups()
            if len(groups) >= 2 and groups[1]:
                fact = f"{groups[0].strip()} is {groups[1].strip()}".rstrip(".")
            else:
                fact = groups[0].strip().rstrip(".")
            if len(fact) >= 3 and not _is_noise(fact):
                facts.append(fact)
    return facts


def _is_noise(fact: str) -> bool:
    lower = fact.lower().strip()
    return any(lower.startswith(n) or lower == n for n in NOISE_PHRASES)


def _extract_from_assistant(content: str) -> list[str]:
    """Extract key-value style facts from assistant messages."""
    facts = []
    kv = re.findall(r"(\b\w[\w\s]{2,20})\s*(?:is|=|:)\s*([^\n,;]{3,100})", content)
    for key, val in kv:
        key, val = key.strip(), val.strip()
        if len(val) >= 3 and not val.startswith("(") and key.lower() not in (
                "this", "that", "it", "which", "what", "there", "nothing", "assistant"):
            fact = f"{key}: {val}"
            if not _is_noise(fact):
                facts.append(fact)
    return facts[:5]
