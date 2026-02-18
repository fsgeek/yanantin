"""Filesystem metadata collectors.

Local storage collectors that gather file/directory metadata via os.walk()
and os.stat(). The Linux collector is the template — platform variants
(macOS, Windows) will follow the same pattern with platform-specific
stat handling.
"""

from yanantin.collector.filesystem.collector import LinuxFilesystemCollector
from yanantin.collector.filesystem.models import (
    FileEntryData,
    FilesystemSnapshot,
    FileTimestamps,
)
from yanantin.collector.filesystem.recorder import (
    FilesystemRecorder,
    collect_and_record_filesystem,
)
from yanantin.collector.filesystem.synthetic import SyntheticFilesystemCollector

__all__ = [
    "FileEntryData",
    "FilesystemRecorder",
    "FilesystemSnapshot",
    "FileTimestamps",
    "LinuxFilesystemCollector",
    "SyntheticFilesystemCollector",
    "collect_and_record_filesystem",
]
