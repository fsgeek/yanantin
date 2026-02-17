"""End-to-end tests for the collector CLI entrypoint."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import UUID


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"

EXPECTED_CONFIG_KEYS = {
    "hostname",
    "fqdn",
    "os_name",
    "os_release",
    "os_version",
    "architecture",
    "cpu_count",
    "python_version",
    "platform_string",
    "machine_id",
    "collected_at",
}


def run_collector_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Invoke ``python -m yanantin.collector`` with the given args."""
    cmd = [sys.executable, "-m", "yanantin.collector", *args]
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")
    combined = [str(SRC_PATH)]
    if pythonpath:
        combined.append(pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(combined)
    return subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=PROJECT_ROOT, env=env)


def test_cli_without_arguments_shows_banner_and_section_titles() -> None:
    result = run_collector_cli()
    output = result.stdout
    assert "Yanantin Collector" in output
    assert "Machine Configuration" in output


def test_cli_json_output_is_valid_and_has_expected_keys() -> None:
    result = run_collector_cli("--json")
    payload = json.loads(result.stdout)
    assert EXPECTED_CONFIG_KEYS <= payload.keys()


def test_cli_record_mode_reports_tensor_uuid() -> None:
    result = run_collector_cli("--record")
    output = result.stdout
    assert "Recorded as tensor" in output
    match = re.search(r"Recorded as tensor ([0-9a-fA-F-]{36})", output)
    assert match is not None
    UUID(match.group(1))


def test_cli_json_record_mode_outputs_two_json_documents() -> None:
    result = run_collector_cli("--json", "--record")
    decoder = json.JSONDecoder()
    text = result.stdout.strip()
    config_payload, idx = decoder.raw_decode(text)
    recording_payload, _ = decoder.raw_decode(text[idx:].strip())

    assert EXPECTED_CONFIG_KEYS <= config_payload.keys()
    assert recording_payload.get("recorded") is True
    UUID(recording_payload["tensor_id"])


def test_cli_help_displays_usage() -> None:
    result = run_collector_cli("--help")
    output = result.stdout
    assert result.returncode == 0
    assert "usage:" in output.lower()
    assert "--json" in output
