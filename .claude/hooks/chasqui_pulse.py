#!/usr/bin/env python3
"""Chasqui pulse — the reactive heartbeat.

Runs frequently via cron (every 1-5 minutes). Mostly does nothing.
Wakes up when:
  - Code changed (new commits since last check) → dispatch a scout
  - 6 hours since last scout → dispatch one anyway (minimum heartbeat)
  - Work queue has items → process the next one

The work queue is the living part. Scouts create verify items.
Verifications with DENIED verdicts create respond items. The system
generates its own work.

State lives in .claude/heartbeat_state.json (not committed).
Work queue lives in .claude/work_queue.json (not committed).

Install:
    crontab -e
    * * * * * cd /home/tony/projects/yanantin && uv run python .claude/hooks/chasqui_pulse.py >> logs/chasqui.log 2>&1
"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
UV_BIN = Path.home() / ".local" / "bin" / "uv"
STATE_FILE = PROJECT_DIR / ".claude" / "heartbeat_state.json"
QUEUE_FILE = PROJECT_DIR / ".claude" / "work_queue.json"
LOCK_FILE = PROJECT_DIR / ".claude" / ".pulse.lock"
LOG_DIR = PROJECT_DIR / "logs"

# Intervals in seconds
MIN_SCOUT_INTERVAL = 300       # 5 minutes between scouts
HEARTBEAT_INTERVAL = 6 * 3600  # 6 hours minimum heartbeat


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def load_json(path: Path, default: dict | list) -> dict | list:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return default


def save_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def current_commit() -> str:
    """Get the current HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def commits_since(old_hash: str) -> list[str]:
    """Get commit hashes between old_hash and HEAD."""
    if not old_hash:
        return []
    try:
        result = subprocess.run(
            ["git", "rev-list", f"{old_hash}..HEAD"],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        return [h for h in result.stdout.strip().split("\n") if h]
    except (subprocess.SubprocessError, OSError):
        return []


def code_changed(commits: list[str]) -> bool:
    """Check if any of the commits touched src/ or tests/."""
    for commit in commits:
        try:
            result = subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit],
                capture_output=True, text=True, cwd=PROJECT_DIR,
            )
            for f in result.stdout.strip().split("\n"):
                if f.startswith("src/") or f.startswith("tests/"):
                    return True
        except (subprocess.SubprocessError, OSError):
            pass
    return False


def run_tinkuy_check() -> tuple[bool, str]:
    """Run tinkuy --check to verify blueprint accuracy.

    Returns (passed, output_text).
    """
    cmd = [str(UV_BIN), "run", "python", "-m", "yanantin.tinkuy", "--check"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=PROJECT_DIR,
            timeout=60,
        )
        output = result.stdout + result.stderr
        passed = result.returncode == 0
        return passed, output.strip()
    except (subprocess.SubprocessError, OSError) as e:
        return False, f"tinkuy check failed to run: {e}"


def enqueue(queue: list, item: dict) -> list:
    """Add an item to the queue if no duplicate type+trigger exists."""
    for existing in queue:
        if existing.get("type") == item.get("type") and existing.get("trigger") == item.get("trigger"):
            return queue  # Already queued
    queue.append(item)
    return queue


def dispatch_chasqui(mode: str, extra_args: list[str] | None = None) -> dict | None:
    """Run Chasqui and return parsed JSON output."""
    cmd = [str(UV_BIN), "run", "python", "-m", "yanantin.chasqui", "--json"]
    if mode == "scout":
        pass  # Default mode
    elif mode == "verify":
        cmd.extend(["--verify", "3"])
    elif mode == "respond":
        if extra_args:
            cmd.extend(["--respond", extra_args[0]])
    elif mode == "score":
        cmd.extend(["--score"])
    else:
        return None

    try:
        log(f"Dispatching: {mode}")
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=PROJECT_DIR,
            timeout=300,  # 5 minute timeout
        )
        if result.returncode != 0:
            log(f"Chasqui error: {result.stderr}")
            return None
        return json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as e:
        log(f"Dispatch failed: {e}")
        return None


def process_queue_item(item: dict, state: dict) -> list[dict]:
    """Process one queue item. Returns new items to enqueue."""
    new_items: list[dict] = []
    item_type = item.get("type", "scout")

    if item_type == "scout":
        result = dispatch_chasqui("scout")
        if result:
            state["last_scout"] = time.time()
            state["last_commit_scouted"] = current_commit()
            # A scout ran — queue a verification
            new_items.append({
                "type": "verify",
                "trigger": "post_scout",
                "created": datetime.now(timezone.utc).isoformat(),
            })

    elif item_type == "verify":
        result = dispatch_chasqui("verify")
        if result and isinstance(result, list):
            # Check for DENIED verdicts — those are interesting
            denied = [r for r in result if r.get("verdict") == "DENIED"]
            if denied:
                for d in denied:
                    cairn_path = d.get("cairn_path", "")
                    if cairn_path:
                        new_items.append({
                            "type": "respond",
                            "trigger": "denied_claim",
                            "target": cairn_path,
                            "created": datetime.now(timezone.utc).isoformat(),
                        })

    elif item_type == "respond":
        target = item.get("target", "")
        if target and Path(target).exists():
            dispatch_chasqui("respond", extra_args=[target])

    elif item_type == "governance":
        log(f"GOVERNANCE ALERT: {item.get('details', 'unknown issue')}")

    elif item_type == "tinkuy_audit":
        result = dispatch_chasqui("score")
        if result:
            log(f"Tinkuy audit score: {result}")

    return new_items


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Acquire exclusive lock — only one pulse runs at a time
    lock_fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError):
        # Another pulse is running. Exit silently.
        os.close(lock_fd)
        return

    try:
        state = load_json(STATE_FILE, {
            "last_commit": "",
            "last_scout": 0,
            "last_commit_scouted": "",
        })
        queue = load_json(QUEUE_FILE, [])

        now = time.time()
        head = current_commit()

        # ── Change detection ──────────────────────────────────────
        last_commit = state.get("last_commit", "")
        if head != last_commit and last_commit:
            new_commits = commits_since(last_commit)
            if new_commits and code_changed(new_commits):
                last_scout = state.get("last_scout", 0)
                if now - last_scout >= MIN_SCOUT_INTERVAL:
                    log(f"Code changed ({len(new_commits)} commits). Running tinkuy check.")
                    tinkuy_passed, tinkuy_output = run_tinkuy_check()
                    if not tinkuy_passed:
                        log("Blueprint is stale. Queueing governance alert.")
                        queue = enqueue(queue, {
                            "type": "governance",
                            "trigger": "blueprint_stale",
                            "details": tinkuy_output,
                            "created": datetime.now(timezone.utc).isoformat(),
                        })
                    else:
                        log("Blueprint check passed.")
                    log("Queueing scout.")
                    queue = enqueue(queue, {
                        "type": "scout",
                        "trigger": "code_change",
                        "commit": head,
                        "created": datetime.now(timezone.utc).isoformat(),
                    })
                else:
                    log("Code changed but scout ran recently. Skipping.")

        state["last_commit"] = head

        # ── Minimum heartbeat ─────────────────────────────────────
        last_scout = state.get("last_scout", 0)
        if now - last_scout >= HEARTBEAT_INTERVAL:
            log("Heartbeat interval reached. Queueing scout.")
            queue = enqueue(queue, {
                "type": "scout",
                "trigger": "heartbeat",
                "created": datetime.now(timezone.utc).isoformat(),
            })

        # ── Process next queue item ───────────────────────────────
        if queue:
            item = queue.pop(0)
            log(f"Processing: {item.get('type')} ({item.get('trigger')})")
            new_items = process_queue_item(item, state)
            for ni in new_items:
                queue = enqueue(queue, ni)
        else:
            # Nothing to do. Silent exit.
            pass

        # ── Save state ────────────────────────────────────────────
        save_json(STATE_FILE, state)
        save_json(QUEUE_FILE, queue)

    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


if __name__ == "__main__":
    main()
