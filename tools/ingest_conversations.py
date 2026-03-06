#!/usr/bin/env python3
"""
Ingest Claude Code conversation JSONL files into DuckDB.

Two source roots:
  1. ~/.claude/projects/           (live conversations)
  2. ~/projects/yanantin/tmp/ubuntu-vm.claude/  (archived conversations)

Preserves the tree structure (parentUuid chains), token usage,
and all metadata. Filters to message types: user, assistant, system.
"""

import duckdb
import json
import os
import sys
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "conversations.duckdb"

SOURCE_ROOTS = [
    Path.home() / ".claude" / "projects",
    Path.home() / "projects" / "yanantin" / "tmp" / "ubuntu-vm.claude" / "projects",
]

HISTORY_FILES = [
    Path.home() / ".claude" / "history.jsonl",
    Path.home() / "projects" / "yanantin" / "tmp" / "ubuntu-vm.claude" / "history.jsonl",
]

MESSAGE_TYPES = {"user", "assistant", "system"}


def extract_project_name(dir_name: str) -> str:
    """Convert directory name like '-home-tony-projects-yanantin' to 'yanantin'."""
    parts = dir_name.replace("-", "/").strip("/").split("/")
    # Find the part after 'projects'
    for i, p in enumerate(parts):
        if p == "projects" and i + 1 < len(parts):
            return "/".join(parts[i + 1:])
    return dir_name


def is_conversation_file(name: str) -> bool:
    """Check if filename is a conversation (UUID) or subagent (agent-*) file."""
    import re
    if re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', name):
        return True
    if name.startswith('agent-'):
        return True
    return False


def conversation_type(name: str) -> str:
    """Return 'main' for UUID conversations, 'agent' for subagent threads."""
    return 'agent' if name.startswith('agent-') else 'main'


def iter_conversations(source_root: Path):
    """Yield (project_dir_name, session_id, conv_type, filepath) for each conversation."""
    if not source_root.exists():
        return
    for project_dir in source_root.iterdir():
        if not project_dir.is_dir():
            continue
        # Main conversations at top level
        for jsonl_file in project_dir.glob("*.jsonl"):
            if not is_conversation_file(jsonl_file.stem):
                continue
            session_id = jsonl_file.stem
            conv_type = conversation_type(jsonl_file.stem)
            yield project_dir.name, session_id, conv_type, jsonl_file
        # Subagent conversations nested under <uuid>/subagents/
        for jsonl_file in project_dir.glob("*/subagents/agent-*.jsonl"):
            parent_uuid = jsonl_file.parent.parent.name
            session_id = jsonl_file.stem
            yield project_dir.name, session_id, "agent", jsonl_file


def parse_message(line: str, source_root: str) -> dict | None:
    """Parse a JSONL line into a flat record for DuckDB, or None if not a message type."""
    d = json.loads(line)
    msg_type = d.get("type")
    if msg_type not in MESSAGE_TYPES:
        return None

    msg = d.get("message", {})
    content = msg.get("content", "")

    # Content can be string or list of content blocks
    if isinstance(content, list):
        text_parts = []
        tool_uses = []
        tool_results = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_uses.append({
                        "id": block.get("id"),
                        "name": block.get("name"),
                        "input_keys": list(block.get("input", {}).keys()) if isinstance(block.get("input"), dict) else [],
                    })
                elif block.get("type") == "tool_result":
                    tool_results.append({
                        "tool_use_id": block.get("tool_use_id"),
                        "is_error": block.get("is_error", False),
                    })
        text_content = "\n".join(text_parts)
        n_tool_uses = len(tool_uses)
        n_tool_results = len(tool_results)
        tool_names = json.dumps([t["name"] for t in tool_uses]) if tool_uses else None
    else:
        text_content = str(content)
        n_tool_uses = 0
        n_tool_results = 0
        tool_names = None

    usage = msg.get("usage", {})

    return {
        "uuid": d.get("uuid"),
        "parent_uuid": d.get("parentUuid"),
        "session_id": d.get("sessionId"),
        "type": msg_type,
        "role": msg.get("role", msg_type),
        "is_sidechain": d.get("isSidechain", False),
        "is_meta": d.get("isMeta", False),
        "timestamp": d.get("timestamp"),
        "cwd": d.get("cwd"),
        "git_branch": d.get("gitBranch"),
        "version": d.get("version"),
        "model": msg.get("model"),
        "text_content": text_content,
        "text_length": len(text_content),
        "n_tool_uses": n_tool_uses,
        "n_tool_results": n_tool_results,
        "tool_names": tool_names,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cache_read_tokens": usage.get("cache_read_input_tokens"),
        "cache_creation_tokens": usage.get("cache_creation_input_tokens"),
        "stop_reason": msg.get("stop_reason"),
        "source_root": source_root,
    }


def ingest(db_path: Path = DB_PATH):
    """Main ingestion: read all JSONL files, load into DuckDB."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing DB for clean rebuild
    if db_path.exists():
        db_path.unlink()

    con = duckdb.connect(str(db_path))

    con.execute("""
        CREATE TABLE messages (
            uuid VARCHAR,
            parent_uuid VARCHAR,
            session_id VARCHAR,
            project VARCHAR,
            type VARCHAR,
            role VARCHAR,
            is_sidechain BOOLEAN,
            is_meta BOOLEAN,
            timestamp TIMESTAMP,
            cwd VARCHAR,
            git_branch VARCHAR,
            version VARCHAR,
            model VARCHAR,
            text_content VARCHAR,
            text_length INTEGER,
            n_tool_uses INTEGER,
            n_tool_results INTEGER,
            tool_names VARCHAR,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            cache_creation_tokens INTEGER,
            stop_reason VARCHAR,
            source_root VARCHAR
        )
    """)

    con.execute("""
        CREATE TABLE conversations (
            session_id VARCHAR,
            project VARCHAR,
            conv_type VARCHAR,
            source_root VARCHAR,
            file_path VARCHAR,
            n_messages INTEGER,
            n_user INTEGER,
            n_assistant INTEGER,
            n_system INTEGER,
            n_tool_uses INTEGER,
            total_input_tokens BIGINT,
            total_output_tokens BIGINT,
            total_cache_read BIGINT,
            total_cache_creation BIGINT,
            first_timestamp TIMESTAMP,
            last_timestamp TIMESTAMP,
            models VARCHAR
        )
    """)

    total_messages = 0
    total_conversations = 0
    batch = []
    batch_size = 5000

    def flush_batch():
        nonlocal batch
        if not batch:
            return
        con.executemany("""
            INSERT INTO messages VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, batch)
        batch = []

    for source_root in SOURCE_ROOTS:
        print(f"Scanning {source_root}...")
        for project_dir_name, session_id, conv_type, filepath in iter_conversations(source_root):
            project = extract_project_name(project_dir_name)
            msg_count = 0
            user_count = 0
            assistant_count = 0
            system_count = 0
            tool_use_count = 0
            input_tokens_total = 0
            output_tokens_total = 0
            cache_read_total = 0
            cache_creation_total = 0
            timestamps = []
            models = set()

            try:
                with open(filepath) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        rec = parse_message(line, str(source_root))
                        if rec is None:
                            continue

                        rec["project"] = project
                        msg_count += 1

                        if rec["type"] == "user":
                            user_count += 1
                        elif rec["type"] == "assistant":
                            assistant_count += 1
                        elif rec["type"] == "system":
                            system_count += 1

                        tool_use_count += rec["n_tool_uses"]
                        input_tokens_total += rec["input_tokens"] or 0
                        output_tokens_total += rec["output_tokens"] or 0
                        cache_read_total += rec["cache_read_tokens"] or 0
                        cache_creation_total += rec["cache_creation_tokens"] or 0

                        if rec["timestamp"]:
                            timestamps.append(rec["timestamp"])
                        if rec["model"]:
                            models.add(rec["model"])

                        batch.append((
                            rec["uuid"], rec["parent_uuid"], rec["session_id"],
                            rec["project"], rec["type"], rec["role"],
                            rec["is_sidechain"], rec["is_meta"],
                            rec["timestamp"], rec["cwd"], rec["git_branch"],
                            rec["version"], rec["model"], rec["text_content"],
                            rec["text_length"], rec["n_tool_uses"],
                            rec["n_tool_results"], rec["tool_names"],
                            rec["input_tokens"], rec["output_tokens"],
                            rec["cache_read_tokens"], rec["cache_creation_tokens"],
                            rec["stop_reason"], rec["source_root"],
                        ))

                        if len(batch) >= batch_size:
                            flush_batch()

            except Exception as e:
                print(f"  Error reading {filepath}: {e}", file=sys.stderr)
                continue

            if msg_count > 0:
                timestamps.sort()
                con.execute("""
                    INSERT INTO conversations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, project, conv_type, str(source_root), str(filepath),
                    msg_count, user_count, assistant_count, system_count,
                    tool_use_count, input_tokens_total, output_tokens_total,
                    cache_read_total, cache_creation_total,
                    timestamps[0] if timestamps else None,
                    timestamps[-1] if timestamps else None,
                    json.dumps(sorted(models)) if models else None,
                ))
                total_conversations += 1
                total_messages += msg_count

    flush_batch()

    # Create indexes
    con.execute("CREATE INDEX idx_msg_session ON messages(session_id)")
    con.execute("CREATE INDEX idx_msg_type ON messages(type)")
    con.execute("CREATE INDEX idx_msg_parent ON messages(parent_uuid)")
    con.execute("CREATE INDEX idx_conv_project ON conversations(project)")

    print(f"\nDone. {total_messages} messages across {total_conversations} conversations.")
    print(f"Database: {db_path}")

    # Quick summary
    result = con.execute("""
        SELECT project, COUNT(*) as convos,
               SUM(n_messages) as msgs,
               SUM(total_input_tokens) as input_tok,
               SUM(total_output_tokens) as output_tok
        FROM conversations
        GROUP BY project
        ORDER BY convos DESC
    """).fetchall()

    print(f"\n{'Project':<40} {'Convos':>8} {'Messages':>10} {'Input Tok':>12} {'Output Tok':>12}")
    print("-" * 84)
    for row in result:
        print(f"{row[0]:<40} {row[1]:>8} {row[2]:>10} {row[3]:>12,} {row[4]:>12,}")

    con.close()


if __name__ == "__main__":
    ingest()
