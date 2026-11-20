"""Stream stdin into one Azure block blob: azure_put_blob.py BLOB_NAME

For the off-site copy (2026-11-20): `... | age -r PUB | azure_put_blob.py yanantin/RUN.tar.age`.
The dump is encrypted in the pipe, so its 6.9 GB never land on this disk twice.

The container SAS is read from its 0600 file, never put on a command line
(docs/credentials.md, decision 4); azcopy wants it in the URL, hence this.
The SAS is create+write only: it can't read, list or delete, and the container's
retention policy keeps every blob 30 days regardless.

Prints one JSON line: blob, bytes, sha256 of what was sent, blocks.
"""

import base64
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONF = Path.home() / ".yanantin/config"
ACCOUNT = (CONF / "azure-backup-account").read_text().strip()
SAS = (CONF / "secrets/azure-backup-sas").read_text().strip()
BLOCK = 64 * 1024 * 1024  # 64 MiB; Azure allows 50,000 blocks, so up to ~3 TiB


def _put(url: str, data: bytes, headers: dict) -> None:
    req = urllib.request.Request(url, data=data, method="PUT", headers={"x-ms-version": "2021-08-06", **headers})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                if r.status in (200, 201):
                    return
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 4:
                raise SystemExit(f"azure_put_blob: PUT failed: {getattr(e, 'code', '')} {e}")


def main(name: str) -> None:
    container, _, blob = name.partition("/")
    base = f"https://{ACCOUNT}.blob.core.windows.net/{container}/{blob}?{SAS}"
    digest, total, ids = hashlib.sha256(), 0, []
    while chunk := sys.stdin.buffer.read(BLOCK):
        bid = base64.b64encode(f"{len(ids):08d}".encode()).decode()
        _put(f"{base}&comp=block&blockid={urllib.parse.quote(bid)}", chunk, {})
        digest.update(chunk); total += len(chunk); ids.append(bid)
    body = "<?xml version='1.0' encoding='utf-8'?><BlockList>" + "".join(
        f"<Latest>{b}</Latest>" for b in ids) + "</BlockList>"
    _put(f"{base}&comp=blocklist", body.encode(), {"Content-Type": "application/xml",
                                                   "x-ms-blob-content-type": "application/octet-stream"})
    print(json.dumps({"blob": name, "bytes": total, "sha256": digest.hexdigest(), "blocks": len(ids)}))


if __name__ == "__main__":
    main(sys.argv[1])
