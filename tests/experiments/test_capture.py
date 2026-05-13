import json
from datetime import datetime, timezone
from pathlib import Path

import pydantic
import pytest

from yanantin.experiments.capture import CaptureRecord, CaptureWriter, load_run


def make_record(**overrides):
    data = {
        "record_id": "rec-1",
        "timestamp": datetime.now(timezone.utc),
        "experiment_id": "exp-1",
        "panel_id": "panel-1",
        "tool_variant_id": "tool-1",
        "model_id": "model-1",
        "prompt_template_id": "tmpl-1",
        "prompt_full": "full prompt",
        "request_full": {"k": "v"},
        "response_parsed": {"answer": 1},
        "response_raw_body": "raw",
        "usage": {"tokens": 1},
        "elapsed_seconds": 0.1,
        "status": "ok",
        "error_type": None,
        "error_message": None,
        "error_payload": None,
    }
    data.update(overrides)
    return CaptureRecord(**data)


def test_capture_record_minimal_ok():
    rec = make_record(status="ok")
    assert CaptureRecord.model_validate(rec.model_dump()) == rec


def test_capture_record_error_shape():
    rec = make_record(
        status="error",
        response_parsed=None,
        response_raw_body=None,
        error_type="RuntimeError",
        error_message="boom",
        error_payload="trace",
    )
    assert isinstance(rec, CaptureRecord)


def test_capture_record_extra_allowed():
    rec = make_record(collector_note="hi")
    assert rec.model_dump()["collector_note"] == "hi"


def test_capture_record_status_literal():
    with pytest.raises(pydantic.ValidationError):
        make_record(status="weird")


def test_writer_appends_lines(tmp_path: Path):
    path = tmp_path / "run" / "r1.jsonl"
    rec1 = make_record(record_id="r1")
    rec2 = make_record(record_id="r2")

    w = CaptureWriter(path)
    w.write(rec1)
    w.write(rec2)
    w.close()

    lines = path.read_text().splitlines()
    assert len(lines) == 2
    payloads = [json.loads(line) for line in lines]
    assert [p["record_id"] for p in payloads] == ["r1", "r2"]


def test_writer_creates_parent_dirs(tmp_path: Path):
    path = tmp_path / "a" / "b" / "c.jsonl"
    w = CaptureWriter(path)
    w.write(make_record())
    w.close()

    assert path.exists()


def test_writer_context_manager(tmp_path: Path):
    path = tmp_path / "d" / "e.jsonl"
    with CaptureWriter(path) as w:
        w.write(make_record())

    assert len(path.read_text().splitlines()) == 1


def test_load_run_roundtrip(tmp_path: Path):
    path = tmp_path / "roundtrip.jsonl"
    records = [
        make_record(record_id="r1"),
        make_record(record_id="r2"),
        make_record(record_id="r3"),
    ]

    with CaptureWriter(path) as w:
        for rec in records:
            w.write(rec)

    loaded = load_run(path)
    assert [r.model_dump() for r in loaded] == [r.model_dump() for r in records]


def test_load_run_skips_blank_lines(tmp_path: Path):
    path = tmp_path / "blank.jsonl"
    rec1 = make_record(record_id="r1")
    rec2 = make_record(record_id="r2")

    path.write_text(
        json.dumps(rec1.model_dump(mode="json"))
        + "\n\n"
        + json.dumps(rec2.model_dump(mode="json"))
        + "\n"
    )

    loaded = load_run(path)
    assert len(loaded) == 2


def test_load_run_bad_line(tmp_path: Path):
    path = tmp_path / "bad.jsonl"
    rec1 = make_record(record_id="r1")

    path.write_text(json.dumps(rec1.model_dump(mode="json")) + "\nnot json\n")

    with pytest.raises(ValueError) as exc:
        load_run(path)
    assert "line 2" in str(exc.value)
