"""Characterization test: pin the public __all__ surface of yanantin.collector.

Locks the public export surface BEFORE the Task 4 repoint, so that
repointing internals to canonical paths cannot silently drop a name.
The `expected` set is copied verbatim from collector/__init__.py:__all__
as it stands pre-repoint.
"""


def test_collector_exports_stable_after_repoint():
    import yanantin.collector as c

    expected = {
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
    }

    assert expected.issubset(set(c.__all__))
    # Every exported name must actually resolve as an attribute.
    for name in c.__all__:
        assert hasattr(c, name), f"{name} in __all__ but not importable"
