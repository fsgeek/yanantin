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
from yanantin.collector.checksum import (
    ChecksumCollector,
    ChecksumData,
    ChecksumRecorder,
    SyntheticChecksumCollector,
    collect_and_record_checksum,
)
from yanantin.collector.dropbox import (
    DropboxCollector,
    DropboxEntryData,
    DropboxListing,
    DropboxRecorder,
    SyntheticDropboxCollector,
    collect_and_record_dropbox,
)
from yanantin.collector.filesystem import (
    FileEntryData,
    FilesystemRecorder,
    FilesystemSnapshot,
    FileTimestamps,
    LinuxFilesystemCollector,
    SyntheticFilesystemCollector,
    collect_and_record_filesystem,
)
from yanantin.collector.fs_events import (
    FsChangeEvent,
    FsEventBatch,
    FsEventRecorder,
    FsIncrementalCollector,
    SyntheticFsEventCollector,
    collect_and_record_fs_events,
)
from yanantin.collector.machine_config import (
    MachineConfigCollector,
    MachineConfigData,
    MachineConfigRecorder,
    collect_and_record,
    collect_machine_config,
    render_machine_config,
)
from yanantin.collector.models import ProviderRegistration, WranglerEnvelope
from yanantin.collector.synthetic import SyntheticCollectorBase
from yanantin.collector.wranglers import BatchWrangler, DirectWrangler, QueuedWrangler

__all__ = [
    "BatchWrangler",
    "ChecksumCollector",
    "ChecksumData",
    "ChecksumRecorder",
    "CollectorBase",
    "DirectWrangler",
    "DropboxCollector",
    "DropboxEntryData",
    "DropboxListing",
    "DropboxRecorder",
    "FileEntryData",
    "FilesystemRecorder",
    "FilesystemSnapshot",
    "FileTimestamps",
    "FsChangeEvent",
    "FsEventBatch",
    "FsEventRecorder",
    "FsIncrementalCollector",
    "LinuxFilesystemCollector",
    "MachineConfigCollector",
    "MachineConfigData",
    "MachineConfigRecorder",
    "ProviderRegistration",
    "QueuedWrangler",
    "RecorderBase",
    "SyntheticChecksumCollector",
    "SyntheticCollectorBase",
    "SyntheticDropboxCollector",
    "SyntheticFsEventCollector",
    "SyntheticFilesystemCollector",
    "WranglerBase",
    "WranglerEnvelope",
    "collect_and_record",
    "collect_and_record_checksum",
    "collect_and_record_dropbox",
    "collect_and_record_filesystem",
    "collect_and_record_fs_events",
    "collect_machine_config",
    "render_machine_config",
]
