"""Chain building for the finding metrics (predictions/2026-10-26-finding-metrics-claude.md).

Synthetic transcript lines in Claude Code's and Codex's formats. Written before the
instrument; the definitions are the pre-registration's, not the code's.
"""

from __future__ import annotations

import json

import pytest

from yanantin.eval.finding_chains import chains_from_claude, chains_from_codex, dedupe

T = "2026-10-01T10:00:{:02d}.000Z"


def human(s, text="find the thing"):
    return json.dumps({"type": "user", "timestamp": T.format(s), "message": {"role": "user", "content": text}})


def call(s, tid, name, inp):
    return json.dumps({"type": "assistant", "timestamp": T.format(s), "message": {
        "role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}})


def result(s, tid, text, as_list=True):
    content = [{"type": "text", "text": text}] if as_list else text
    return json.dumps({"type": "user", "timestamp": T.format(s), "message": {
        "role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": content}]}})


def hits(*keys):
    return json.dumps({"total": len(keys), "hits": [{"key": k, "snippet": "s"} for k in keys]})


SEARCH = "mcp__khipumaq__search"
RECALL = "mcp__khipumaq__recall"


def test_search_then_recall_of_a_hit_is_found():
    [c] = chains_from_claude([
        human(0),
        call(1, "s1", SEARCH, {"query": "a"}), result(2, "s1", hits("k1", "k2")),
        call(10, "r1", RECALL, {"key": "k2"}), result(11, "r1", "{}"),
    ])
    assert c.arm == "tool" and c.found
    assert c.searches_before_found == 1
    assert c.seconds_to_found == 9
    assert c.result_chars_to_found == len(hits("k1", "k2"))
    assert c.queries == ("a",)


def test_no_recall_is_abandoned():
    [c] = chains_from_claude([human(0), call(1, "s1", SEARCH, {"query": "a"}), result(2, "s1", hits("k1"))])
    assert not c.found and c.seconds_to_found is None and c.searches_before_found is None


def test_reformulations_join_one_chain_and_count_toward_cost():
    [c] = chains_from_claude([
        human(0),
        call(1, "s1", SEARCH, {"query": "a"}), result(2, "s1", hits()),
        call(3, "s2", "mcp__llm-memory__search", {"query": "b"}), result(4, "s2", hits("k9")),
        call(5, "r1", "mcp__llm-memory__recall", {"key": "k9"}), result(6, "r1", "{}"),
    ])
    assert c.found and c.searches_before_found == 2 and c.queries == ("a", "b")


def test_a_human_turn_ends_the_chain():
    chains = chains_from_claude([
        human(0), call(1, "s1", SEARCH, {"query": "a"}), result(2, "s1", hits("k1")),
        human(3), call(4, "r1", RECALL, {"key": "k1"}), result(5, "r1", "{}"),
    ])
    assert [c.found for c in chains] == [False]
    assert chains[0].unlinked_recalls == 0


def test_tool_result_lines_are_not_human_turns():
    [c] = chains_from_claude([
        human(0), call(1, "s1", SEARCH, {"query": "a"}), result(2, "s1", hits("k1"), as_list=False),
        call(3, "r1", RECALL, {"key": "k1"}), result(4, "r1", "{}"),
    ])
    assert c.found


def test_recall_of_a_key_no_search_returned_is_unlinked():
    [c] = chains_from_claude([
        human(0), call(1, "s1", SEARCH, {"query": "a"}), result(2, "s1", hits("k1")),
        call(3, "r1", RECALL, {"key": "elsewhere"}), result(4, "r1", "{}"),
    ])
    assert not c.found and c.unlinked_recalls == 1


def test_recall_with_wrong_arguments_is_not_found():
    [c] = chains_from_claude([
        human(0), call(1, "s1", SEARCH, {"query": "a"}), result(2, "s1", hits("k1")),
        call(3, "r1", RECALL, {"query": "k1"}), result(4, "r1", "Error executing tool recall"),
    ])
    assert not c.found


def test_other_servers_recall_is_ignored():
    [c] = chains_from_claude([
        human(0), call(1, "s1", SEARCH, {"query": "a"}), result(2, "s1", hits("k1")),
        call(3, "r1", "mcp__qhaway__recall", {"key": "k1"}), result(4, "r1", "{}"),
    ])
    assert not c.found


def test_recall_before_its_search_result_arrives_does_not_count():
    [c] = chains_from_claude([
        human(0), call(1, "s1", SEARCH, {"query": "a"}),
        call(2, "r1", RECALL, {"key": "k1"}), result(3, "s1", hits("k1")), result(4, "r1", "{}"),
    ])
    assert not c.found


def test_non_json_result_falls_back_to_key_fields():
    [c] = chains_from_claude([
        human(0), call(1, "s1", SEARCH, {"query": "a"}),
        result(2, "s1", 'garbled {"key": "k7", "snippet": "x"'),
        call(3, "r1", RECALL, {"key": "k7"}), result(4, "r1", "{}"),
    ])
    assert c.found


def test_no_search_no_chain():
    assert chains_from_claude([human(0), call(1, "b1", "Bash", {"command": "ls"}), result(2, "b1", "x")]) == []


def test_unparseable_lines_are_skipped():
    [c] = chains_from_claude(["not json", "", human(0), call(1, "s1", SEARCH, {"query": "a"}), result(2, "s1", hits())])
    assert c.queries == ("a",)


# -- the without-the-tool arm: transcript greps ------------------------------


def test_transcript_grep_then_read_of_a_matched_file_is_found():
    path = "/home/t/.claude/projects/-x/abc.jsonl"
    [c] = chains_from_claude([
        human(0),
        call(1, "g1", "Bash", {"command": "grep -l thunder ~/.claude/projects/*/*.jsonl"}),
        result(2, "g1", path + "\n"),
        call(5, "rd", "Read", {"file_path": path}), result(6, "rd", "..."),
    ])
    assert c.arm == "grep" and c.found and c.seconds_to_found == 4


def test_grep_tool_on_transcripts_counts_and_unmatched_read_does_not():
    [c] = chains_from_claude([
        human(0),
        call(1, "g1", "Grep", {"pattern": "x", "path": "/home/t/.claude/projects"}),
        result(2, "g1", "/home/t/.claude/projects/-x/one.jsonl\n"),
        call(3, "rd", "Bash", {"command": "sed -n 1,5p /home/t/.claude/projects/-x/other.jsonl"}),
        result(4, "rd", "..."),
    ])
    assert c.arm == "grep" and not c.found


def test_grep_outside_transcripts_is_not_a_search():
    assert chains_from_claude([
        human(0), call(1, "g1", "Bash", {"command": "grep -rn foo src/"}), result(2, "g1", "src/a.py:1:foo"),
    ]) == []


def test_a_span_with_both_arms_gives_one_chain_per_arm():
    chains = chains_from_claude([
        human(0),
        call(1, "g1", "Bash", {"command": "rg foo ~/.claude/projects"}), result(2, "g1", ""),
        call(3, "s1", SEARCH, {"query": "foo"}), result(4, "s1", hits()),
    ])
    assert sorted(c.arm for c in chains) == ["grep", "tool"]


# -- Codex --------------------------------------------------------------------


def codex_user(s):
    return json.dumps({"timestamp": T.format(s), "type": "event_msg",
                       "payload": {"type": "user_message", "message": "hi"}})


def codex_mcp(s, cid, tool, args, text):
    return json.dumps({"timestamp": T.format(s), "type": "event_msg", "payload": {
        "type": "mcp_tool_call_end", "call_id": cid,
        "invocation": {"server": "llm-memory", "tool": tool, "arguments": args},
        "result": {"Ok": {"content": [{"type": "text", "text": text}]}}}})


def test_codex_search_history_then_open_episode_is_found():
    ref = "episode://codex-history/abc"
    [c] = chains_from_codex([
        codex_user(0),
        codex_mcp(2, "c1", "search_history", {"query": "q"}, json.dumps({"hits": [{"episode_ref": ref}]})),
        codex_mcp(7, "c2", "open_episode", {"episode_ref": ref}, "{}"),
    ])
    assert c.arm == "tool" and c.found and c.seconds_to_found == 5


def test_codex_user_message_ends_the_chain():
    chains = chains_from_codex([
        codex_user(0), codex_mcp(1, "c1", "search", {"query": "q"}, hits("k")),
        codex_user(2), codex_mcp(3, "c2", "recall", {"key": "k"}, "{}"),
    ])
    assert [c.found for c in chains] == [False]


# -- de-duplication across hosts ---------------------------------------------


def test_dedupe_keeps_one_chain_per_first_call_id():
    lines = [human(0), call(1, "s1", SEARCH, {"query": "a"}), result(2, "s1", hits())]
    a, b = chains_from_claude(lines), chains_from_claude(lines)
    assert len(dedupe(a + b)) == 1


@pytest.mark.parametrize("bad", [{"query": "a"}, {}])
def test_search_input_without_query_still_counts(bad):
    [c] = chains_from_claude([human(0), call(1, "s1", SEARCH, bad), result(2, "s1", hits())])
    assert len(c.queries) == 1
