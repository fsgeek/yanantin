"""Synthetic cloud storage provider — the deterministic ground-truth twin used to
build and prove the ayllu data-flow topology (fan-out + depth-1 feedback edge)
without OAuth or a live cloud account. See
docs/superpowers/specs/2026-06-28-ayllu-cloud-topology-design.md."""

from yanantin.collector.storage.cloud.synthetic.collector import (
    SyntheticCloudCollector,
)
from yanantin.collector.storage.cloud.synthetic.models import (
    CloudDelta,
    CloudEntry,
    CloudListing,
)

__all__ = [
    "CloudDelta",
    "CloudEntry",
    "CloudListing",
    "SyntheticCloudCollector",
]
