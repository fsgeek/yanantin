"""Ground-truth falsification: drive the REAL FsIncrementalCollector over a
REAL directory tree on this machine and feed its REAL FsEventBatch output
through the REAL aggregator + recorder. Spec 2026-07-05 §8.

The sibling test (test_band_falsification.py) exercises the aggregator with
hand-built FsChangeEvent lists — it proves the aggregator LOGIC. This test
closes the gap that memory demands: §8.1 says "run against the real
FsIncrementalCollector on this actual repo", ground truth, not synthetics
grading their own imagination. No mocks (feedback-no-mock-databases): a real
os.walk over a real tree, a real mtime-diff scan, the real band pipeline.

It also prints the events-in / facts-out counts so the ratio is a pasted
receipt, not a claim.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.activity.band import StorageAccessKind
from yanantin.activity.band_aggregator import BandAggregator
from yanantin.collector.activity.linux.band_adapter import feed_batch
from yanantin.collector.activity.linux.collector import FsIncrementalCollector
from yanantin.recorder.activity.linux.band_fact_recorder import BandFactRecorder

# Ground-truth corpus: this repo's own source tree. Real files, real mtimes.
_REPO_SRC = Path(__file__).resolve().parents[2] / "src"


def test_ground_truth_firehose_tamed(tmp_path, capsys):
    """§8.1 — the real collector over the real src/ tree: repeated touches
    across scans collapse; facts-out is strictly fewer than events-in."""
    corpus = _REPO_SRC
    assert corpus.is_dir(), (
        f"ground-truth corpus missing at {corpus}; test cannot reach its "
        "target (guard against a silent sandbox skip)"
    )

    state = tmp_path / "fs_state.json"
    collector = FsIncrementalCollector(volumes=[str(corpus)], state_file=state)
    agg = BandAggregator(quiescence=timedelta(minutes=5))

    # Scan 1: cold — every real file reports as 'created'.
    batch1 = collector.collect()
    n_created = len(batch1.events)
    assert n_created > 0, "empty corpus — no real files scanned"
    assert all(e.event_type == "created" for e in batch1.events)

    # Touch a handful of REAL files so scan 2 yields real 'modified' events
    # for the SAME paths already seen as 'created'. That cross-scan repeat is
    # exactly the churn the aggregator must collapse to one band per file.
    py_files = sorted(str(p) for p in corpus.rglob("*.py"))[:20]
    assert len(py_files) >= 5, "need several real files to exercise the collapse"
    future = batch1.current_run.timestamp() + 3600
    for f in py_files:
        os.utime(f, (future, future))

    batch2 = collector.collect()
    n_modified = sum(1 for e in batch2.events if e.event_type == "modified")
    assert n_modified >= 5, (
        f"expected the touched files to reappear as 'modified'; "
        f"got {n_modified} (batch2 had {len(batch2.events)} events)"
    )

    events_in = n_created + len(batch2.events)
    feed_batch(agg, batch1)
    feed_batch(agg, batch2)
    bands = agg.flush_all()

    store = InMemoryActivityStreamStore()
    facts_out = BandFactRecorder(store).record_bands(uuid4(), bands)

    # The load-bearing inequality. Every touched file was seen at least twice
    # (created in scan 1, modified in scan 2) yet emits ONE band.
    assert facts_out < events_in, (
        f"firehose NOT tamed: facts_out={facts_out} !< events_in={events_in}"
    )
    # And specifically: the repeated files did not each spawn a second fact.
    assert facts_out <= n_created, (
        f"repeated cross-scan touches leaked extra facts: "
        f"facts_out={facts_out} > distinct files {n_created}"
    )

    with capsys.disabled():
        print(
            f"\n[§8.1 GROUND TRUTH] corpus={corpus}\n"
            f"  events_in  = {events_in}  "
            f"(created={n_created} + scan2={len(batch2.events)})\n"
            f"  facts_out  = {facts_out}\n"
            f"  reduction  = {events_in / facts_out:.2f}x "
            f"({facts_out}/{events_in} = {facts_out / events_in:.4f})"
        )


def test_ground_truth_per_file_firehose_collapses(tmp_path, capsys):
    """§8.1 with teeth — one REAL file hammered across many REAL scan runs
    (the mtime-scan analogue of high-frequency churn) collapses to ONE band.

    The whole-tree scan reduction is modest (~1x) precisely because a
    quiescent tree yields one event per file; the spec says so (real-time
    sources have the advantage). This isolates the collapse the aggregator
    DOES win on a scan source: repeated touches to the same handle across
    successive batches stay a single band."""
    hot = tmp_path / "hot.log"
    hot.write_text("0")
    state = tmp_path / "fs_state.json"
    collector = FsIncrementalCollector(
        volumes=[str(tmp_path)], state_file=state
    )
    agg = BandAggregator(quiescence=timedelta(minutes=5))

    scans = 25
    events_in = 0
    prev_mtime = hot.stat().st_mtime
    for _ in range(scans):
        batch = collector.collect()
        # Filter to the hot file (the state file itself churns too).
        hot_events = [e for e in batch.events if e.file_path == str(hot)]
        events_in += len(hot_events)
        feed_batch(
            agg,
            batch.model_copy(update={"events": tuple(hot_events)}),
        )
        # Bump mtime forward so the next scan sees a real 'modified'.
        prev_mtime += 60
        os.utime(hot, (prev_mtime, prev_mtime))

    bands = agg.flush_all()
    hot_bands = [b for b in bands if b.location == f"path:{hot}"]
    store = InMemoryActivityStreamStore()
    facts_out = BandFactRecorder(store).record_bands(uuid4(), hot_bands)

    assert events_in >= scans - 1, (
        f"expected ~{scans} real events on the hot file, got {events_in}"
    )
    assert facts_out == 1, (
        f"per-file firehose NOT tamed: {events_in} events on one file "
        f"produced {facts_out} facts, expected 1"
    )
    with capsys.disabled():
        print(
            f"\n[§8.1 PER-FILE] one file, {scans} real scans\n"
            f"  events_in = {events_in}\n"
            f"  facts_out = {facts_out}\n"
            f"  reduction = {events_in}x"
        )


def test_ground_truth_weak_anchor_honesty(tmp_path):
    """§8.3 — real collector output carries path: URIs, os_principal=None,
    and never infers RENAME."""
    corpus = _REPO_SRC
    state = tmp_path / "fs_state.json"
    collector = FsIncrementalCollector(volumes=[str(corpus)], state_file=state)
    agg = BandAggregator(quiescence=timedelta(minutes=5))

    feed_batch(agg, collector.collect())
    bands = agg.flush_all()
    assert bands, "no bands from real corpus"

    assert all(b.location.startswith("path:") for b in bands), (
        "mtime-scan must mint weak path: URIs"
    )
    assert all(b.os_principal is None for b in bands), (
        "mtime-scan has no principal attribution"
    )
    assert all(
        StorageAccessKind.RENAME not in StorageAccessKind(b.access_kinds)
        for b in bands
    ), "RENAME must never be inferred on a weak-anchor source"
