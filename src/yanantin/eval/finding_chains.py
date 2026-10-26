"""Search chains and their outcomes, from transcript lines.

The instrument for predictions/2026-10-26-finding-metrics-claude.md; the
definitions are that page's. A chain is the run of searches between two human
turns in one session stream. A tool chain is found when it recalls a key one of
its searches had already returned; a grep chain (transcript grep, the
without-the-tool arm) is found when it reads a session file one of its greps
had matched. Pure functions over raw lines: reading the store is the script's job.

Declared losses: a snippet that answers the need leaves no recall, so it counts
as abandoned here (the adjudication labels it); a line that is not JSON is
skipped; result size is characters, a proxy for tokens.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

_TOOL_SEARCH = re.compile(r"^mcp__(?:khipumaq|llm-memory)__search$")
_TOOL_RECALL = re.compile(r"^mcp__(?:khipumaq|llm-memory)__recall$")
_CODEX_SERVERS = {"khipumaq", "llm-memory"}
_CODEX_SEARCH = {"search", "search_history"}
_CODEX_RECALL = {"recall", "open_episode"}

# A session transcript: under Claude Code's or Codex's session directories, or a
# file named like one (session UUID, Codex rollout, subagent).
_TRANSCRIPT = re.compile(
    r"\.claude/projects|\.codex/sessions|"
    r"(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|rollout-[\w-]+|agent-[0-9a-f]+)\.jsonl\b"
)
_GREP_CMD = re.compile(r"(?:^|[\s|;&(])(?:grep|rg|egrep|zgrep)\s")
_READ_CMD = re.compile(r"(?:^|[\s|;&(])(?:sed|cat|head|tail|jq|less|python3?)\s")
_JSONL_PATH = re.compile(r"[\w~./-]+\.jsonl")
_KEY_FIELD = re.compile(r'"(?:key|_key|episode_ref)"\s*:\s*"([^"]+)"')


@dataclass
class Chain:
    arm: str  # "tool" or "grep"
    first_call_id: str
    first_ts: datetime | None
    queries: tuple[str, ...] = ()
    found: bool = False
    searches_before_found: int | None = None
    seconds_to_found: float | None = None
    result_chars_to_found: int | None = None
    unlinked_recalls: int = 0
    # Working state, not reported.
    _searches: int = 0
    _chars: int = 0
    _returned: set[str] = field(default_factory=set)
    _pending: dict[str, str] = field(default_factory=dict)  # call id -> kind


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _result_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def _hit_keys(text: str) -> set[str]:
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return set(_KEY_FIELD.findall(text))
    keys: set[str] = set()
    hits = data.get("hits") if isinstance(data, dict) else None
    for h in hits if isinstance(hits, list) else []:
        if isinstance(h, dict):
            keys.update(str(h[k]) for k in ("key", "_key", "episode_ref") if h.get(k))
    return keys or set(_KEY_FIELD.findall(text))


class _Span:
    """The chains of one span between human turns, one per arm."""

    def __init__(self) -> None:
        self.chains: dict[str, Chain] = {}

    def chain(self, arm: str, call_id: str, ts: datetime | None) -> Chain:
        if arm not in self.chains:
            self.chains[arm] = Chain(arm=arm, first_call_id=call_id, first_ts=ts)
        return self.chains[arm]

    def search(self, arm: str, call_id: str, ts, query: str) -> None:
        c = self.chain(arm, call_id, ts)
        c.queries += (query,)
        c._searches += 1
        c._pending[call_id] = "search"

    def result(self, call_id: str, text: str, keys: set[str]) -> None:
        for c in self.chains.values():
            if c._pending.pop(call_id, None) == "search":
                c._chars += len(text)
                c._returned |= keys

    def open(self, arm: str, ts, key: str | None) -> None:
        """A recall (tool) or a read of a session file (grep)."""
        c = self.chains.get(arm)
        if c is None or c.found:
            return
        if key is not None and key in c._returned:
            c.found = True
            c.searches_before_found = c._searches
            c.result_chars_to_found = c._chars
            if ts is not None and c.first_ts is not None:
                c.seconds_to_found = (ts - c.first_ts).total_seconds()
        elif arm == "tool":
            c.unlinked_recalls += 1


def _close(span: _Span, out: list[Chain]) -> _Span:
    out.extend(span.chains.values())
    return _Span()


def chains_from_claude(lines: Iterable[str]) -> list[Chain]:
    """Chains in one Claude Code session stream (lines in file order)."""
    out: list[Chain] = []
    span = _Span()
    grep_calls: set[str] = set()
    for line in lines:
        try:
            d = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(d, dict):
            continue
        msg: dict = d.get("message") if isinstance(d.get("message"), dict) else {}  # type: ignore[assignment]
        content = msg.get("content")
        ts = _ts(d.get("timestamp"))
        if d.get("type") == "user":
            blocks = content if isinstance(content, list) else None
            if blocks is None or any(
                    isinstance(b, dict) and b.get("type") != "tool_result" for b in blocks):
                span = _close(span, out)
                continue
            for b in blocks:
                text = _result_text(b.get("content"))
                tid = b.get("tool_use_id", "")
                if tid in grep_calls:
                    span.result(tid, text, set(_JSONL_PATH.findall(text)))
                else:
                    span.result(tid, text, _hit_keys(text))
        elif d.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if not isinstance(b, dict) or b.get("type") != "tool_use":
                    continue
                name, tid = b.get("name", ""), b.get("id", "")
                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                if _TOOL_SEARCH.match(name):
                    span.search("tool", tid, ts, str(inp.get("query", "")))
                elif _TOOL_RECALL.match(name):
                    key = inp.get("key")
                    span.open("tool", ts, str(key) if key else None)
                elif name == "Bash":
                    cmd = str(inp.get("command", ""))
                    if _GREP_CMD.search(cmd) and _TRANSCRIPT.search(cmd):
                        grep_calls.add(tid)
                        span.search("grep", tid, ts, cmd)
                    elif _READ_CMD.search(cmd):
                        for p in _JSONL_PATH.findall(cmd):
                            span.open("grep", ts, p)
                elif name == "Grep":
                    where = f"{inp.get('path', '')} {inp.get('glob', '')}"
                    if _TRANSCRIPT.search(where):
                        grep_calls.add(tid)
                        span.search("grep", tid, ts, str(inp.get("pattern", "")))
                elif name == "Read":
                    path = str(inp.get("file_path", ""))
                    if path.endswith(".jsonl"):
                        span.open("grep", ts, path)
    _close(span, out)
    return out


def chains_from_codex(lines: Iterable[str]) -> list[Chain]:
    """Chains in one Codex rollout (MCP calls only; Codex barely used the tool)."""
    out: list[Chain] = []
    span = _Span()
    for line in lines:
        try:
            d = json.loads(line)
        except (ValueError, TypeError):
            continue
        p = d.get("payload") if isinstance(d, dict) else None
        if not isinstance(p, dict):
            continue
        ts = _ts(d.get("timestamp"))
        if p.get("type") == "user_message":
            span = _close(span, out)
        elif p.get("type") == "mcp_tool_call_end":
            inv = p.get("invocation") or {}
            if inv.get("server") not in _CODEX_SERVERS:
                continue
            args = inv.get("arguments") or {}
            cid = p.get("call_id", "")
            res = (p.get("result") or {}).get("Ok") or {}
            text = _result_text(res.get("content"))
            if inv.get("tool") in _CODEX_SEARCH:
                span.search("tool", cid, ts, str(args.get("query", "")))
                span.result(cid, text, _hit_keys(text))
            elif inv.get("tool") in _CODEX_RECALL:
                key = args.get("key") or args.get("episode_ref")
                span.open("tool", ts, str(key) if key else None)
    _close(span, out)
    return out


def dedupe(chains: Iterable[Chain]) -> list[Chain]:
    """One chain per first call id: a session file ingested on two hosts is one session."""
    seen: dict[tuple[str, str], Chain] = {}
    for c in chains:
        seen.setdefault((c.arm, c.first_call_id), c)
    return list(seen.values())


def _human_text(content) -> str | None:
    """The person's words in a Claude user line, or None if it is only tool results."""
    if isinstance(content, str):
        return content
    if isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") != "tool_result" for b in content):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return None


def span_context(lines: Iterable[str], first_call_id: str) -> dict | None:
    """What an adjudicator sees for the chain starting at first_call_id: the human
    turn before it, the results of the span's searches, and the span's last
    assistant text. Claude Code or Codex lines. None if the id is not found."""
    request, ctx, search_ids = "", None, set()
    for line in lines:
        try:
            d = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(d, dict):
            continue
        p = d.get("payload") if isinstance(d.get("payload"), dict) else None
        msg: dict = d.get("message") if isinstance(d.get("message"), dict) else {}  # type: ignore[assignment]
        content = msg.get("content")
        if p is not None:  # Codex
            kind = p.get("type")
            if kind == "user_message":
                if ctx is not None:
                    return ctx
                request = str(p.get("message", ""))
            elif kind == "agent_message" and ctx is not None:
                ctx["response"] = str(p.get("message", ""))
            elif kind == "mcp_tool_call_end":
                inv = p.get("invocation") or {}
                if inv.get("server") in _CODEX_SERVERS and inv.get("tool") in _CODEX_SEARCH:
                    if ctx is None and p.get("call_id") == first_call_id:
                        ctx = {"request": request, "results": [], "response": ""}
                    if ctx is not None:
                        res = (p.get("result") or {}).get("Ok") or {}
                        ctx["results"].append(_result_text(res.get("content")))
        elif d.get("type") == "user":
            text = _human_text(content)
            if text is not None:
                if ctx is not None:
                    return ctx
                request = text
            elif ctx is not None and isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("tool_use_id") in search_ids:
                        ctx["results"].append(_result_text(b.get("content")))
        elif d.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use" and _TOOL_SEARCH.match(b.get("name", "")):
                    if ctx is None and b.get("id") == first_call_id:
                        ctx = {"request": request, "results": [], "response": ""}
                    if ctx is not None:
                        search_ids.add(b.get("id"))
                elif b.get("type") == "text" and ctx is not None:
                    ctx["response"] = b.get("text", "")
    return ctx
