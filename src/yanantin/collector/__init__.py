"""Collector — the data pipeline for bringing human-side data into Yanantin.

The collector/wrangler/recorder pattern separates three concerns:

- **Collector** gathers data from a source (filesystem, API, sensor)
- **Wrangler** moves data across boundaries (in-memory, file, queue)
- **Recorder** normalizes and stores data via the Apacheta interface

The pattern comes from the Indaleko project (8 years of development)
and represents hard-won design knowledge about ingesting data from
diverse sources into a unified store.

Usage::

    from yanantin.collector import CollectorBase, RecorderBase, DirectWrangler
    from yanantin.collector import WranglerEnvelope, ProviderRegistration
"""

from yanantin.collector.base import CollectorBase, RecorderBase, WranglerBase
from yanantin.collector.models import ProviderRegistration, WranglerEnvelope
from yanantin.collector.wranglers import BatchWrangler, DirectWrangler, QueuedWrangler

__all__ = [
    "BatchWrangler",
    "CollectorBase",
    "DirectWrangler",
    "ProviderRegistration",
    "QueuedWrangler",
    "RecorderBase",
    "WranglerBase",
    "WranglerEnvelope",
]
