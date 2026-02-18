"""Dropbox cloud storage collector.

Gathers file/folder metadata from Dropbox via the SDK with OAuth2
authentication. Supports full listings and cursor-based incremental sync.
Other cloud collectors (GDrive, OneDrive, iCloud) will follow the same
pattern as siblings.
"""

from yanantin.collector.dropbox.collector import DropboxCollector
from yanantin.collector.dropbox.models import DropboxEntryData, DropboxListing
from yanantin.collector.dropbox.recorder import (
    DropboxRecorder,
    collect_and_record_dropbox,
)
from yanantin.collector.dropbox.synthetic import SyntheticDropboxCollector

__all__ = [
    "DropboxCollector",
    "DropboxEntryData",
    "DropboxListing",
    "DropboxRecorder",
    "SyntheticDropboxCollector",
    "collect_and_record_dropbox",
]
