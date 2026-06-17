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
# RecorderBase/FactRecorderBase live in recorder.base, which does NOT import
# collector models — it is cycle-free and safe to re-export eagerly (a test
# imports it from this package).
from yanantin.recorder.base import FactRecorderBase, RecorderBase
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

# Concrete domain recorders import collector *models*, so eagerly importing
# them here at collector/__init__ time created a recorder<->collector cycle
# (importing collector.X.models runs this __init__, which reached forward
# into the recorder packages still mid-init -> ImportError). PEP 562 lazy
# resolution keeps these names importable from ``yanantin.collector`` while
# deferring the recorder import until the name is first accessed, which is
# after both packages have finished initializing. (Phase 1 Task 8.)
_LAZY_RECORDER_EXPORTS = {
    "FsEventRecorder": "yanantin.recorder.activity.linux",
    "collect_and_record_fs_events": "yanantin.recorder.activity.linux",
    "DropboxRecorder": "yanantin.recorder.storage.cloud.dropbox",
    "collect_and_record_dropbox": "yanantin.recorder.storage.cloud.dropbox",
    "ChecksumFactRecorder": "yanantin.recorder.storage.local.checksum",
    "ChecksumRecorder": "yanantin.recorder.storage.local.checksum",
    "collect_and_record_checksum": "yanantin.recorder.storage.local.checksum",
    "FilesystemRecorder": "yanantin.recorder.storage.local.linux",
    "collect_and_record_filesystem": "yanantin.recorder.storage.local.linux",
}


def __getattr__(name: str):  # noqa: D401 — PEP 562 module-level hook
    module_path = _LAZY_RECORDER_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(module_path), name)


def __dir__() -> list[str]:
    return sorted(__all__)
