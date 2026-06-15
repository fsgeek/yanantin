"""Synthetic Dropbox listing generator.

Produces DropboxListing instances with realistic cloud file metadata:
mix of files and folders, common document types, shared files, revision
IDs, and plausible Dropbox content hashes.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from yanantin.collector._synthetic_base import SyntheticCollectorBase
from yanantin.collector.storage.cloud.dropbox.models import DropboxEntryData, DropboxListing

_CLOUD_EXTENSIONS = (
    ".docx", ".xlsx", ".pptx", ".pdf", ".txt", ".csv",
    ".png", ".jpg", ".mp4", ".zip", ".json", ".html",
)

_FOLDER_NAMES = (
    "Documents", "Photos", "Projects", "Shared", "Archive",
    "Work", "Personal", "Backup", "Downloads", "Reports",
    "Presentations", "Spreadsheets", "Templates", "Assets",
)

_FILE_STEMS = (
    "report", "presentation", "budget", "invoice", "contract",
    "meeting_notes", "proposal", "readme", "summary", "draft",
    "photo", "screenshot", "backup", "export", "analysis",
)


def _fake_content_hash(rng, seed_str: str) -> str:
    """Generate a plausible Dropbox content hash."""
    h = hashlib.sha256(seed_str.encode())
    return h.hexdigest()


def _fake_rev(rng) -> str:
    """Generate a plausible Dropbox revision ID."""
    return f"{rng.randint(0, 0xFFFFFFFFFFFF):012x}"


class SyntheticDropboxCollector(SyntheticCollectorBase[DropboxListing]):
    """Generates realistic Dropbox listings with deterministic output."""

    def __init__(
        self,
        seed: int | None = None,
        total_entries: int = 50,
        shared_fraction: float = 0.2,
        account_email: str = "synthetic@example.com",
    ) -> None:
        super().__init__(seed)
        self._total_entries = total_entries
        self._shared_fraction = shared_fraction
        self._account_email = account_email
        self._base_time = datetime(2024, 6, 1, tzinfo=timezone.utc)

    def _make_folder(self, path: str, collected_at: datetime) -> DropboxEntryData:
        """Create a synthetic folder entry."""
        name = path.rsplit("/", 1)[-1] if "/" in path else path
        return DropboxEntryData(
            name=name,
            path_display=path,
            path_lower=path.lower(),
            entry_type="folder",
            shared=self._rng.random() < self._shared_fraction,
            collected_at=collected_at,
        )

    def _make_file(self, folder_path: str, collected_at: datetime | None = None) -> DropboxEntryData:
        """Create a synthetic file entry."""
        stem = self._rng.choice(_FILE_STEMS)
        ext = self._rng.choice(_CLOUD_EXTENSIONS)
        name = f"{stem}_{self._rng.randint(1, 999)}{ext}"
        path = f"{folder_path}/{name}"

        modified = self._base_time + timedelta(
            days=self._rng.randint(0, 365),
            hours=self._rng.randint(0, 23),
        )
        size = int(self._rng.paretovariate(1.5) * 1000)

        return DropboxEntryData(
            name=name,
            path_display=path,
            path_lower=path.lower(),
            entry_type="file",
            size=size,
            content_hash=_fake_content_hash(self._rng, f"{path}-{size}"),
            rev=_fake_rev(self._rng),
            modified_time=modified,
            shared=self._rng.random() < self._shared_fraction,
            is_downloadable=True,
            collected_at=collected_at or modified,
        )

    def generate(self) -> DropboxListing:
        """Generate a synthetic Dropbox listing."""
        entries: list[DropboxEntryData] = []
        total_files = 0
        total_folders = 0

        collected_at = self._base_time + timedelta(
            days=self._rng.randint(0, 365),
        )

        n_folders = max(3, self._total_entries // 10)
        folders: list[str] = []
        for _ in range(n_folders):
            folder_name = self._rng.choice(_FOLDER_NAMES)
            folder_path = f"/{folder_name}"
            if folder_path not in folders:
                folders.append(folder_path)
                entries.append(self._make_folder(folder_path, collected_at))
                total_folders += 1

                if self._rng.random() < 0.4:
                    sub_name = self._rng.choice(_FOLDER_NAMES)
                    sub_path = f"{folder_path}/{sub_name}"
                    if sub_path not in folders:
                        folders.append(sub_path)
                        entries.append(self._make_folder(sub_path, collected_at))
                        total_folders += 1

        remaining = self._total_entries - len(entries)
        for _ in range(max(0, remaining)):
            folder = self._rng.choice(folders) if folders else "/"
            entries.append(self._make_file(folder, collected_at))
            total_files += 1

        return DropboxListing(
            account_email=self._account_email,
            entries=tuple(entries),
            total_files=total_files,
            total_folders=total_folders,
            cursor=f"synthetic_cursor_{self._rng.randint(0, 99999):05d}",
            collected_at=collected_at,
        )

    def get_description(self) -> str:
        return (
            f"Synthetic Dropbox collector — generates {self._total_entries} "
            f"entries for {self._account_email}"
        )
