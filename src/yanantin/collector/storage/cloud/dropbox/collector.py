"""Dropbox cloud storage collector.

Uses the Dropbox SDK with OAuth2 for authentication. Supports full
recursive listings with cursor-based pagination. Token refresh is
handled automatically.

Auth flow reused from Indaleko: config file has app_key/app_secret,
token file has access/refresh tokens. Interactive auth prompt when
no tokens exist.

Requires optional dependency: pip install yanantin[dropbox]
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.collector._collector_base import CollectorBase
from yanantin.collector.storage.cloud.dropbox.models import DropboxEntryData, DropboxListing

logger = logging.getLogger(__name__)

_CONFIG_FILENAME = "dropbox_config.json"
_TOKEN_FILENAME = "dropbox_token.json"


def _require_dropbox():
    """Import the dropbox SDK, raising a clear error if not installed."""
    try:
        import dropbox
        return dropbox
    except ImportError:
        msg = (
            "Dropbox collector requires the 'dropbox' package. "
            "Install with: pip install yanantin[dropbox] "
            "or: pip install dropbox"
        )
        raise ImportError(msg)


class DropboxCollector(CollectorBase[DropboxListing]):
    """Collects file and folder metadata from Dropbox.

    Authentication is configured via JSON files in config_dir:
    - dropbox_config.json: {"app_key": "...", "app_secret": "..."}
    - dropbox_token.json: {"access_token": "...", "refresh_token": "...",
                           "expires_at": "..."}

    If tokens don't exist, the collector will run the interactive OAuth
    flow and save the resulting tokens.
    """

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir.resolve()
        self._dbx = None
        self._account_email = ""
        self._provider_id: UUID | None = None

    def _load_config(self) -> dict:
        """Load app credentials from config file."""
        config_path = self._config_dir / _CONFIG_FILENAME
        if not config_path.exists():
            msg = (
                f"Dropbox config not found at {config_path}. "
                f"Create it with: "
                f'{{"app_key": "YOUR_KEY", "app_secret": "YOUR_SECRET"}}'
            )
            raise FileNotFoundError(msg)
        return json.loads(config_path.read_text())

    def _load_tokens(self) -> dict | None:
        """Load saved tokens, or None if not yet authenticated."""
        token_path = self._config_dir / _TOKEN_FILENAME
        if not token_path.exists():
            return None
        try:
            return json.loads(token_path.read_text())
        except (json.JSONDecodeError, KeyError):
            logger.warning("Corrupt token file, re-authenticating")
            return None

    def _save_tokens(self, tokens: dict) -> None:
        """Save tokens atomically with owner-only permissions.

        OAuth tokens are credentials. The temp file is opened 0o600 before
        any bytes are written, so the token is never briefly world-readable
        (a write-then-chmod sequence would leave that race window open).
        """
        token_path = self._config_dir / _TOKEN_FILENAME
        tmp_path = token_path.with_suffix(".tmp")
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(tokens, f, indent=2)
        tmp_path.rename(token_path)

    def _authenticate(self) -> None:
        """Establish an authenticated Dropbox client."""
        dropbox = _require_dropbox()
        config = self._load_config()
        app_key = config["app_key"]
        app_secret = config["app_secret"]
        tokens = self._load_tokens()

        if tokens and tokens.get("refresh_token"):
            self._dbx = dropbox.Dropbox(
                oauth2_access_token=tokens.get("access_token", ""),
                oauth2_refresh_token=tokens["refresh_token"],
                app_key=app_key,
                app_secret=app_secret,
            )
            try:
                self._dbx.check_and_refresh_access_token()
            except Exception:
                logger.info("Token refresh failed, running interactive auth")
                self._interactive_auth(app_key, app_secret, dropbox)
                return
        else:
            self._interactive_auth(app_key, app_secret, dropbox)
            return

        self._save_tokens({
            "access_token": self._dbx._oauth2_access_token,
            "refresh_token": tokens["refresh_token"],
        })

    def _interactive_auth(self, app_key: str, app_secret: str, dropbox) -> None:
        """Run the interactive OAuth2 authorization flow."""
        flow = dropbox.DropboxOAuth2FlowNoRedirect(
            app_key, app_secret, token_access_type="offline",
        )
        authorize_url = flow.start()
        print(f"\n  Dropbox authorization required.")
        print(f"  1. Go to: {authorize_url}")
        print(f"  2. Click 'Allow' and copy the authorization code.")
        auth_code = input("  3. Enter the code here: ").strip()

        result = flow.finish(auth_code)
        self._dbx = dropbox.Dropbox(
            oauth2_access_token=result.access_token,
            oauth2_refresh_token=result.refresh_token,
            app_key=app_key,
            app_secret=app_secret,
        )

        self._save_tokens({
            "access_token": result.access_token,
            "refresh_token": result.refresh_token,
        })

    def _get_account_email(self) -> str:
        """Get the authenticated account's email address."""
        if not self._account_email:
            account = self._dbx.users_get_current_account()
            self._account_email = account.email
        return self._account_email

    def _entry_to_data(self, entry) -> DropboxEntryData | None:
        """Convert a Dropbox API entry to our model."""
        dropbox = _require_dropbox()

        if isinstance(entry, dropbox.files.FileMetadata):
            return DropboxEntryData(
                name=entry.name,
                path_display=entry.path_display,
                path_lower=entry.path_lower,
                entry_type="file",
                size=entry.size,
                content_hash=entry.content_hash or "",
                rev=entry.rev,
                modified_time=entry.server_modified.replace(
                    tzinfo=timezone.utc,
                ) if entry.server_modified else None,
                shared=entry.sharing_info is not None,
                is_downloadable=entry.is_downloadable,
                media_info=(
                    {"tag": entry.media_info.get_tag()}
                    if entry.media_info
                    else {}
                ),
            )
        elif isinstance(entry, dropbox.files.FolderMetadata):
            return DropboxEntryData(
                name=entry.name,
                path_display=entry.path_display,
                path_lower=entry.path_lower,
                entry_type="folder",
                shared=entry.sharing_info is not None,
            )
        elif isinstance(entry, dropbox.files.DeletedMetadata):
            return DropboxEntryData(
                name=entry.name,
                path_display=entry.path_display,
                path_lower=entry.path_lower,
                entry_type="deleted",
            )
        return None

    def collect(self, since: datetime | None = None) -> DropboxListing:
        """List all files and folders in the Dropbox account."""
        if self._dbx is None:
            self._authenticate()

        email = self._get_account_email()
        entries: list[DropboxEntryData] = []
        total_files = 0
        total_folders = 0

        result = self._dbx.files_list_folder("", recursive=True)

        while True:
            for entry in result.entries:
                data = self._entry_to_data(entry)
                if data is not None:
                    if (
                        since is not None
                        and data.entry_type == "file"
                        and data.modified_time is not None
                        and data.modified_time < since
                    ):
                        continue
                    entries.append(data)
                    if data.entry_type == "file":
                        total_files += 1
                    elif data.entry_type == "folder":
                        total_folders += 1

            if not result.has_more:
                break
            result = self._dbx.files_list_folder_continue(result.cursor)

        return DropboxListing(
            account_email=email,
            entries=tuple(entries),
            total_files=total_files,
            total_folders=total_folders,
            cursor=result.cursor,
        )

    def get_provider_id(self) -> UUID:
        if self._provider_id is None:
            email = self._account_email or "unknown"
            self._provider_id = uuid5(
                NAMESPACE_DNS,
                f"yanantin.collector.dropbox.{email}",
            )
        return self._provider_id

    def get_description(self) -> str:
        email = self._account_email or "<not authenticated>"
        return f"Dropbox collector — lists files for {email}"
