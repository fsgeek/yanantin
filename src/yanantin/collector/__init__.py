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

from yanantin.collector._collector_base import CollectorBase
from yanantin.collector._synthetic_base import SyntheticCollectorBase
from yanantin.collector.activity.linux import (
    FsChangeEvent,
    FsEventBatch,
    FsIncrementalCollector,
    SyntheticFsEventCollector,
)
from yanantin.collector.storage.cloud.dropbox import (
    DropboxCollector,
    DropboxEntryData,
    DropboxListing,
    SyntheticDropboxCollector,
)
from yanantin.collector.storage.local.checksum import (
    ChecksumCollector,
    ChecksumData,
    SyntheticChecksumCollector,
)
from yanantin.collector.storage.local.linux import (
    FileEntryData,
    FilesystemSnapshot,
    FileTimestamps,
    LinuxFilesystemCollector,
    SyntheticFilesystemCollector,
)
from yanantin.machine.linux import (
    MachineConfigCollector,
    MachineConfigData,
    MachineConfigRecorder,
    collect_and_record,
    collect_machine_config,
    render_machine_config,
)
from yanantin.recorder.activity.linux import FsEventRecorder, collect_and_record_fs_events
from yanantin.recorder.base import FactRecorderBase, RecorderBase
from yanantin.recorder.storage.cloud.dropbox import DropboxRecorder, collect_and_record_dropbox
from yanantin.recorder.storage.local.checksum import (
    ChecksumFactRecorder,
    ChecksumRecorder,
    collect_and_record_checksum,
)
from yanantin.recorder.storage.local.linux import (
    FilesystemRecorder,
    collect_and_record_filesystem,
)
from yanantin.transport.base import WranglerBase
from yanantin.transport.models import ProviderRegistration, WranglerEnvelope
from yanantin.transport.wranglers import BatchWrangler, DirectWrangler, QueuedWrangler

__all__ = [
    "BatchWrangler",
    "ChecksumCollector",
    "ChecksumData",
    "ChecksumFactRecorder",
    "ChecksumRecorder",
    "CollectorBase",
    "FactRecorderBase",
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
