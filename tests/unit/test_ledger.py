import json

import pytest

from yanantin.eval.ledger import LedgerError, append, verify


def entry(**overrides):
    base = {
        "observed_at": "2026-05-08T00:00:00+00:00",
        "instrument": {"name": "test", "version": "0"},
        "population": {"source": "x", "sha256": "0" * 64},
        "quantity": "state_bytes",
        "value": 1,
    }
    base.update(overrides)
    return base


def test_append_assigns_sequential_ids_and_chains(tmp_path):
    path = tmp_path / "obs.jsonl"
    first = append(entry(), path)
    second = append(entry(value=2), path)
    assert first["id"] == "obs-0001" and first["prev"] is None
    assert second["id"] == "obs-0002" and second["prev"] is not None
    assert verify(path) == 2


def test_observed_and_recorded_times_are_distinct_fields(tmp_path):
    rec = append(entry(), tmp_path / "obs.jsonl")
    assert rec["observed_at"] == "2026-05-08T00:00:00+00:00"
    assert rec["recorded_at"] != rec["observed_at"]


def test_missing_required_field_is_refused(tmp_path):
    bad = entry()
    del bad["observed_at"]
    with pytest.raises(LedgerError):
        append(bad, tmp_path / "obs.jsonl")


def test_caller_cannot_supply_chain_fields(tmp_path):
    with pytest.raises(LedgerError):
        append(entry(id="obs-9999"), tmp_path / "obs.jsonl")


def test_edited_middle_entry_is_detected(tmp_path):
    path = tmp_path / "obs.jsonl"
    for v in (1, 2, 3):
        append(entry(value=v), path)
    lines = path.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["value"] = 99
    lines[1] = json.dumps(rec, sort_keys=True, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(LedgerError):
        verify(path)


def test_deleted_middle_entry_is_detected(tmp_path):
    path = tmp_path / "obs.jsonl"
    for v in (1, 2, 3):
        append(entry(value=v), path)
    lines = path.read_text().splitlines()
    path.write_text(lines[0] + "\n" + lines[2] + "\n")
    with pytest.raises(LedgerError):
        verify(path)
