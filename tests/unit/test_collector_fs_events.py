"""Tests for filesystem event collectors (real and synthetic)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from yanantin.collector.activity.linux.collector import FsIncrementalCollector
from yanantin.collector.activity.linux.models import FsChangeEvent, FsEventBatch
from yanantin.collector.activity.linux.synthetic import SyntheticFsEventCollector


class TestFsIncrementalCollector:
    def test_first_run_reports_all_as_created(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "file1.txt").write_text("hello")
        (data_dir / "file2.txt").write_text("world")
        state_file = tmp_path / "state.json"

        collector = FsIncrementalCollector([str(data_dir)], state_file)
        batch = collector.collect()

        assert isinstance(batch, FsEventBatch)
        assert batch.last_run is None  # first run
        assert len(batch.events) == 2
        assert all(e.event_type == "created" for e in batch.events)

    def test_second_run_no_changes(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "file1.txt").write_text("hello")
        state_file = tmp_path / "state.json"

        collector = FsIncrementalCollector([str(data_dir)], state_file)
        collector.collect()  # first run

        # Second run — no changes
        batch = collector.collect()
        assert batch.last_run is not None
        assert len(batch.events) == 0

    def test_detects_modification(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        test_file = data_dir / "file.txt"
        test_file.write_text("original")
        state_file = tmp_path / "state.json"

        collector = FsIncrementalCollector([str(data_dir)], state_file)
        collector.collect()  # first run

        # Modify the file (ensure mtime changes)
        time.sleep(0.05)
        test_file.write_text("modified")

        batch = collector.collect()
        modified_events = [e for e in batch.events if e.event_type == "modified"]
        assert len(modified_events) == 1
        assert str(test_file) in modified_events[0].file_path

    def test_detects_deletion(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        test_file = data_dir / "file.txt"
        test_file.write_text("doomed")
        state_file = tmp_path / "state.json"

        collector = FsIncrementalCollector([str(data_dir)], state_file)
        collector.collect()  # first run

        test_file.unlink()
        batch = collector.collect()
        deleted_events = [e for e in batch.events if e.event_type == "deleted"]
        assert len(deleted_events) == 1

    def test_detects_creation(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        state_file = tmp_path / "state.json"

        collector = FsIncrementalCollector([str(data_dir)], state_file)
        collector.collect()  # first run (empty)

        (data_dir / "new_file.txt").write_text("fresh")
        batch = collector.collect()
        created_events = [e for e in batch.events if e.event_type == "created"]
        assert len(created_events) == 1

    def test_state_file_persistence(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_text("hello")
        state_file = tmp_path / "state.json"

        collector = FsIncrementalCollector([str(data_dir)], state_file)
        collector.collect()

        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert "last_run" in state
        assert "files" in state

    def test_state_file_atomic_write(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        state_file = tmp_path / "state.json"

        collector = FsIncrementalCollector([str(data_dir)], state_file)
        collector.collect()

        # No temp files should remain
        tmp_files = list(tmp_path.glob(".fs_events_state_*"))
        assert len(tmp_files) == 0

    def test_corrupt_state_file_handled(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_text("hello")
        state_file = tmp_path / "state.json"
        state_file.write_text("not json at all{{{")

        collector = FsIncrementalCollector([str(data_dir)], state_file)
        batch = collector.collect()
        # Should treat as first run
        assert batch.last_run is None
        assert all(e.event_type == "created" for e in batch.events)

    def test_provider_id_is_stable(self, tmp_path: Path) -> None:
        c1 = FsIncrementalCollector(["/tmp"], tmp_path / "s1.json")
        c2 = FsIncrementalCollector(["/var"], tmp_path / "s2.json")
        assert c1.get_provider_id() == c2.get_provider_id()

    def test_multiple_volumes(self, tmp_path: Path) -> None:
        vol1 = tmp_path / "vol1"
        vol2 = tmp_path / "vol2"
        vol1.mkdir()
        vol2.mkdir()
        (vol1 / "a.txt").write_text("a")
        (vol2 / "b.txt").write_text("b")
        state_file = tmp_path / "state.json"

        collector = FsIncrementalCollector(
            [str(vol1), str(vol2)], state_file,
        )
        batch = collector.collect()
        assert len(batch.volumes) == 2
        assert len(batch.events) == 2

    def test_batch_roundtrips_json(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "file.txt").write_text("hello")
        state_file = tmp_path / "state.json"

        collector = FsIncrementalCollector([str(data_dir)], state_file)
        batch = collector.collect()

        json_str = batch.model_dump_json()
        restored = FsEventBatch.model_validate_json(json_str)
        assert len(restored.events) == len(batch.events)


class TestSyntheticFsEventCollector:
    def test_generate_returns_batch(self) -> None:
        collector = SyntheticFsEventCollector(seed=42)
        batch = collector.generate()
        assert isinstance(batch, FsEventBatch)
        assert len(batch.events) == 20  # default

    def test_deterministic_with_seed(self) -> None:
        c1 = SyntheticFsEventCollector(seed=42)
        c2 = SyntheticFsEventCollector(seed=42)
        assert c1.collect() == c2.collect()

    def test_different_seeds_differ(self) -> None:
        c1 = SyntheticFsEventCollector(seed=42)
        c2 = SyntheticFsEventCollector(seed=99)
        assert c1.collect() != c2.collect()

    def test_temporal_ordering(self) -> None:
        collector = SyntheticFsEventCollector(seed=42, events_per_batch=50)
        batch = collector.collect()
        times = [e.modified_time for e in batch.events]
        # Events should be temporally ordered
        assert times == sorted(times)

    def test_configurable_batch_size(self) -> None:
        collector = SyntheticFsEventCollector(seed=42, events_per_batch=5)
        batch = collector.collect()
        assert len(batch.events) == 5

    def test_event_types_valid(self) -> None:
        collector = SyntheticFsEventCollector(seed=42, events_per_batch=100)
        batch = collector.collect()
        valid_types = {"created", "modified", "deleted"}
        for event in batch.events:
            assert event.event_type in valid_types

    def test_has_last_run_and_current_run(self) -> None:
        collector = SyntheticFsEventCollector(seed=42)
        batch = collector.collect()
        assert batch.last_run is not None
        assert batch.current_run is not None
        assert batch.current_run > batch.last_run
