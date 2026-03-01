#!/usr/bin/env python3
"""Transparent logging proxy for Claude API calls.

Captures the full request body (including system prompt and messages array)
on every API call, logs it to a JSONL file, and forwards to Anthropic's
actual endpoint.

Usage:
    # Start the proxy
    uv run python tools/phase1/proxy.py [--port 8080] [--log-dir tmp/api_logs]

    # Point Claude Code at it
    ANTHROPIC_BASE_URL=http://localhost:8080 claude

The proxy captures:
- System prompt (full text, every turn)
- Messages array (all roles, all content blocks)
- Token counts from the response
- Timestamps for request/response timing

Does NOT modify requests or responses. Pure observation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx required: uv pip install httpx", file=sys.stderr)
    sys.exit(1)

try:
    from flask import Flask, Response, request
except ImportError:
    print("flask required: uv pip install flask", file=sys.stderr)
    sys.exit(1)


ANTHROPIC_API_BASE = "https://api.anthropic.com"


def create_app(log_dir: Path) -> Flask:
    """Create the proxy Flask app."""
    app = Flask(__name__)
    log_dir.mkdir(parents=True, exist_ok=True)

    # One log file per proxy session
    session_start = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"proxy_{session_start}.jsonl"

    # Persistent HTTP client for forwarding
    client = httpx.Client(
        base_url=ANTHROPIC_API_BASE,
        timeout=httpx.Timeout(300.0, connect=30.0),
    )

    def log_record(record: dict) -> None:
        """Append a record to the log file."""
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def measure_system_prompt(body: dict) -> dict:
        """Extract system prompt metrics."""
        system = body.get("system", "")
        if isinstance(system, str):
            return {
                "system_prompt_bytes": len(system.encode("utf-8")),
                "system_prompt_type": "string",
                "system_prompt_preview": system[:200],
            }
        elif isinstance(system, list):
            # System can be a list of content blocks
            total_bytes = sum(
                len(json.dumps(block).encode("utf-8")) for block in system
            )
            block_types = [
                block.get("type", "unknown")
                for block in system
                if isinstance(block, dict)
            ]
            return {
                "system_prompt_bytes": total_bytes,
                "system_prompt_type": "blocks",
                "system_prompt_block_count": len(system),
                "system_prompt_block_types": block_types,
                "system_prompt_preview": json.dumps(system[0])[:200]
                if system
                else "",
            }
        return {"system_prompt_bytes": 0, "system_prompt_type": "absent"}

    def measure_messages(body: dict) -> dict:
        """Extract message array metrics without storing full content."""
        messages = body.get("messages", [])
        metrics = {
            "message_count": len(messages),
            "messages_total_bytes": len(
                json.dumps(messages).encode("utf-8")
            ),
            "role_counts": {},
            "tool_result_count": 0,
            "tool_result_bytes": 0,
            "tool_use_count": 0,
            "text_bytes": 0,
            "thinking_bytes": 0,
        }

        for msg in messages:
            role = msg.get("role", "unknown")
            metrics["role_counts"][role] = (
                metrics["role_counts"].get(role, 0) + 1
            )

            content = msg.get("content", "")
            if isinstance(content, str):
                metrics["text_bytes"] += len(content.encode("utf-8"))
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type", "")
                    if block_type == "tool_result":
                        metrics["tool_result_count"] += 1
                        result_content = block.get("content", "")
                        if isinstance(result_content, str):
                            metrics["tool_result_bytes"] += len(
                                result_content.encode("utf-8")
                            )
                        else:
                            metrics["tool_result_bytes"] += len(
                                json.dumps(result_content).encode("utf-8")
                            )
                    elif block_type == "tool_use":
                        metrics["tool_use_count"] += 1
                    elif block_type == "text":
                        metrics["text_bytes"] += len(
                            block.get("text", "").encode("utf-8")
                        )
                    elif block_type == "thinking":
                        metrics["thinking_bytes"] += len(
                            block.get("thinking", "").encode("utf-8")
                        )

        return metrics

    @app.route("/v1/messages", methods=["POST"])
    def proxy_messages():
        """Proxy the messages endpoint with full logging."""
        request_time = datetime.now(timezone.utc)
        body = request.get_json(force=True)

        # Measure without storing full content (that would be huge)
        system_metrics = measure_system_prompt(body)
        message_metrics = measure_messages(body)

        # Log the request metrics
        request_record = {
            "type": "request",
            "timestamp": request_time.isoformat(),
            "model": body.get("model", "unknown"),
            "max_tokens": body.get("max_tokens"),
            "stream": body.get("stream", False),
            "system": system_metrics,
            "messages": message_metrics,
            "total_request_bytes": len(
                json.dumps(body).encode("utf-8")
            ),
        }

        # Optionally capture full system prompt (it's the part we
        # can't get from JSONL)
        if body.get("system"):
            request_record["system_prompt_full"] = body["system"]

        log_record(request_record)

        # Forward to Anthropic — preserve query string (e.g. ?beta=true)
        headers = dict(request.headers)
        # Remove hop-by-hop headers
        for h in ["Host", "Content-Length", "Transfer-Encoding"]:
            headers.pop(h, None)

        upstream_path = "/v1/messages"
        if request.query_string:
            upstream_path += "?" + request.query_string.decode("utf-8")

        if body.get("stream", False):
            # Streaming response — forward chunks
            return _proxy_streaming(body, headers, request_time, upstream_path)
        else:
            # Non-streaming — simple forward
            return _proxy_direct(body, headers, request_time, upstream_path)

    def _strip_response_headers(raw_headers):
        """Remove hop-by-hop headers that Flask manages itself.

        Forwarding transfer-encoding/content-length from upstream
        causes double-chunking or length mismatches — Flask sets
        these based on how it sends the response body.
        """
        skip = {
            "transfer-encoding",
            "content-length",
            "content-encoding",
            "connection",
            "keep-alive",
        }
        return {
            k: v
            for k, v in raw_headers.items()
            if k.lower() not in skip
        }

    def _proxy_direct(body, headers, request_time, upstream_path):
        """Handle non-streaming API call."""
        try:
            resp = client.post(
                upstream_path,
                json=body,
                headers=headers,
            )

            response_time = datetime.now(timezone.utc)

            # Log the response
            try:
                resp_body = resp.json()
                usage = resp_body.get("usage", {})
                response_record = {
                    "type": "response",
                    "timestamp": response_time.isoformat(),
                    "duration_ms": int(
                        (response_time - request_time).total_seconds() * 1000
                    ),
                    "status_code": resp.status_code,
                    "usage": usage,
                    "stop_reason": resp_body.get("stop_reason"),
                }
                log_record(response_record)
            except Exception:
                log_record({
                    "type": "response_error",
                    "timestamp": response_time.isoformat(),
                    "status_code": resp.status_code,
                })

            return Response(
                resp.content,
                status=resp.status_code,
                headers=_strip_response_headers(resp.headers),
            )
        except Exception as e:
            log_record({
                "type": "proxy_error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            })
            return Response(
                json.dumps({"error": str(e)}),
                status=502,
                content_type="application/json",
            )

    def _proxy_streaming(body, headers, request_time, upstream_path):
        """Handle streaming API call (SSE).

        The generator must own the stream lifecycle — the httpx context
        manager cannot wrap the Response because Flask iterates the
        generator *after* the function returns, by which time the `with`
        block has exited and the stream is closed.
        """
        try:
            resp = client.send(
                client.build_request(
                    "POST",
                    upstream_path,
                    json=body,
                    headers=headers,
                ),
                stream=True,
            )
            response_headers = _strip_response_headers(resp.headers)

            def generate():
                first_byte_time = None
                chunks_collected = []
                try:
                    for chunk in resp.iter_bytes():
                        if first_byte_time is None:
                            first_byte_time = datetime.now(timezone.utc)
                        chunks_collected.append(chunk)
                        yield chunk
                finally:
                    resp.close()

                    # Log after stream completes
                    response_time = datetime.now(timezone.utc)
                    full_response = b"".join(chunks_collected)

                    # Try to extract usage from the final event
                    usage = {}
                    try:
                        # SSE events are text lines
                        text = full_response.decode("utf-8", errors="replace")
                        for line in reversed(text.split("\n")):
                            if "message_delta" in line and "usage" in line:
                                if line.startswith("data: "):
                                    event_data = json.loads(line[6:])
                                    usage = event_data.get("usage", {})
                                    break
                            elif "message_start" in line and "usage" in line:
                                if line.startswith("data: "):
                                    event_data = json.loads(line[6:])
                                    msg = event_data.get("message", {})
                                    usage = msg.get("usage", {})
                    except Exception:
                        pass

                    log_record({
                        "type": "response_stream",
                        "timestamp": response_time.isoformat(),
                        "duration_ms": int(
                            (response_time - request_time).total_seconds()
                            * 1000
                        ),
                        "first_byte_ms": int(
                            (first_byte_time - request_time).total_seconds()
                            * 1000
                        )
                        if first_byte_time
                        else None,
                        "status_code": resp.status_code,
                        "response_bytes": len(full_response),
                        "usage": usage,
                    })

            return Response(
                generate(),
                status=resp.status_code,
                headers=response_headers,
                content_type=response_headers.get(
                    "content-type", "text/event-stream"
                ),
            )

        except Exception as e:
            log_record({
                "type": "proxy_error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            })
            return Response(
                json.dumps({"error": str(e)}),
                status=502,
                content_type="application/json",
            )

    # Health check
    @app.route("/health")
    def health():
        return {"status": "ok", "log_file": str(log_file)}

    print(f"Logging to: {log_file}", file=sys.stderr)
    return app


def main():
    parser = argparse.ArgumentParser(
        description="Transparent logging proxy for Claude API"
    )
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--log-dir", type=Path, default=Path("tmp/api_logs")
    )
    args = parser.parse_args()

    app = create_app(args.log_dir)
    print(
        f"Proxy listening on http://localhost:{args.port}",
        file=sys.stderr,
    )
    print(
        f"Use: ANTHROPIC_BASE_URL=http://localhost:{args.port} claude",
        file=sys.stderr,
    )
    app.run(host="127.0.0.1", port=args.port, threaded=True)


if __name__ == "__main__":
    main()
