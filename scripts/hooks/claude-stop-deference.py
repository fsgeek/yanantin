#!/usr/bin/env python3
"""Claude Code Stop hook: catch a seat ending its turn on deference or waiting.

Adopted from hamut'ay (scripts/hooks/claude-stop-deference.py, 8d00ce4 and 381c08c,
2026-11-05) by yanantin's steward on 2026-11-20, with patterns for yanantin's own
variant: ending on "X is next" or "next on my list is X". On 2026-11-17 Tony read
"The restore check on the new disk is next" as his cue and went to check an empty
disk; on 2026-11-20 he had to ask how long the question register would take,
because "next on my list is the question register" had ended the turn.

The pattern this targets recurs across custodian seats despite feedback
memories recording it (third and fourth occurrences, 2026-11-03 and 11-04):
ending a turn by handing Tony a veto ("unless you'd rather...", "if you don't
object by..."), or ending on a promise or a wait ("next I'll...", "waiting for
the notification"). Memories teach what not to say; this runs outside the
model, at the moment it happens.

On a match it blocks the stop once, with a reason, so the seat reconsiders.
If the seat stops again (stop_hook_active), the stop is allowed: some
questions genuinely belong to Tony (keys, hardware, his own choices).

Every catch is appended to logs/stop-hook-catches.jsonl, including the
second, allowed stop, so false positives and real catches can be counted.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TAIL_CHARS = 500

PATTERNS = {
    "veto": [
        r"unless you'?d (rather|prefer)",
        r"if you'?d (rather|prefer)",
        r"if you don'?t object",
        r"let me know if you'?d",
        r"(do|would) you want me to",
        r"want me to (go ahead|proceed|start)",
        r"shall i (proceed|go ahead|start)",
        r"should i (proceed|go ahead|start)",
        r"say the word",
    ],
    "waiting": [
        r"waiting (for|on) (the |codex'?s? |its |a )?(notification|result|agent|review)",
        r"i'?ll (check back|report back) when",
        r"once (it|the agent|codex) (finishes|completes|reports)",
    ],
    "promise": [
        r"\bnext,? i'?ll\b",
        r"\b(is|comes) next\s*[.!:]",
        r"\bnext (on my list |up )?is\b",
        r"\bnext step is\b",
        r"\bi'?ll (now )?(start|begin) (on|with)\b[^.]*\.?\s*$",
    ],
}

# A turn that ends while a background agent really is running is how Claude
# Code waits; blocking it would force polling. These kinds are logged, not
# blocked, so their rate can be read against the 11-04 16-hour stall.
LOG_ONLY = {"waiting"}

REASON = (
    "Stop hook (scripts/hooks/claude-stop-deference.py) matched {kind} "
    "phrasing near the end of your message: {match!r}. "
    "The seat decides and acts. If this is a decision of the seat's, make it and "
    "do the work now; if you are waiting on background work, check its output "
    "(files, git status) instead of ending on the wait. If the question truly "
    "belongs to Tony (keys, hardware, his own choices), stop again and it will pass."
)


def last_assistant_text(transcript_path: str) -> str:
    text = ""
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "assistant":
                    continue
                content = entry.get("message", {}).get("content", [])
                if isinstance(content, str):
                    parts = [content]
                else:
                    parts = [
                        b.get("text", "")
                        for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    ]
                joined = "\n".join(p for p in parts if p)
                if joined.strip():
                    text = joined
    except OSError:
        return ""
    return text


def find_match(tail: str):
    lowered = tail.lower().replace("’", "'")
    for kind, pats in PATTERNS.items():
        for pat in pats:
            m = re.search(pat, lowered)
            if m:
                return kind, m.group(0)
    return None


def log_catch(record: dict) -> None:
    log = Path(__file__).resolve().parents[2] / "logs" / "stop-hook-catches.jsonl"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    # The transcript can lag the turn: on 2026-11-05 the hook judged the turn's
    # first text, not its last, because the final message was not yet written.
    # Prefer the final message from the hook input when Claude Code supplies it.
    supplied = data.get("last_assistant_message")
    source = "input" if isinstance(supplied, str) and supplied.strip() else "transcript"
    text = supplied if source == "input" else last_assistant_text(data.get("transcript_path", ""))
    if not text:
        return 0
    tail = text[-TAIL_CHARS:]
    hit = find_match(tail)
    if not hit:
        return 0
    kind, match = hit
    second = bool(data.get("stop_hook_active"))
    log_catch({
        "ts": datetime.now(timezone.utc).isoformat(),
        "session_id": data.get("session_id"),
        "kind": kind,
        "match": match,
        "tail": tail,
        "source": source,
        "input_keys": sorted(data),
        "action": "logged" if kind in LOG_ONLY else ("allowed_second_stop" if second else "blocked"),
    })
    if second or kind in LOG_ONLY:
        return 0
    print(json.dumps({"decision": "block", "reason": REASON.format(kind=kind, match=match)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
