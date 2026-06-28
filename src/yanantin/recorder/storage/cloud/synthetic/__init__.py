"""Synthetic cloud storage recorders — the fan-out legs that write a cloud delta
into Objects (storage leg) and activity_facts (activity leg). See
docs/superpowers/specs/2026-06-28-ayllu-cloud-topology-design.md."""

from yanantin.recorder.storage.cloud.synthetic.fact_recorder import (
    CloudFactRecorder,
)
from yanantin.recorder.storage.cloud.synthetic.storage_recorder import (
    CloudStorageRecorder,
    normalize_cloud_entry,
)

__all__ = [
    "CloudFactRecorder",
    "CloudStorageRecorder",
    "normalize_cloud_entry",
]
