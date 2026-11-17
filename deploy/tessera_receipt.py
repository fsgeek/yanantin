"""Tessera receipts for the nightly backup manifest (pilot, 2026-11-16).

  tessera_receipt.py submit RUN_DIR   submit RUN_DIR/MANIFEST.sha256, once
  tessera_receipt.py fetch  ROOT      fetch receipts for every run under ROOT that has none yet

Everything lands in RUN_DIR/tessera/ (request.json, status.json, receipt.json), so the
receipt travels with the snapshot it attests. Tessera keeps receipts only 30 days, so ours
is the copy that lasts. The backup never waits on this: receipts take hours, and a request
can stay open indefinitely (Tessera's limit 2). See docs/requests/2026-11-16-to-tessera-*.

The API key is read from its 0600 file here, never put on a command line
(docs/credentials.md, decision 4).
"""

import hashlib
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = "https://p4e0222jof.execute-api.us-east-2.amazonaws.com/v1/v1/requests"
KEY_FILE = Path.home() / ".yanantin/config/secrets/tessera-pilot"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _call(url: str, data: bytes | None = None, extra: dict | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    req.add_header("x-api-key", KEY_FILE.read_text().strip())
    for k, v in (extra or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def submit(run: Path) -> None:
    out = run / "tessera"
    if (out / "request.json").exists():
        return
    manifest = (run / "MANIFEST.sha256").read_bytes()
    key = str(uuid.uuid4())
    code, body = _call(ENDPOINT, manifest, {"Tessera-Request-Key": key,
                                             "Content-Type": "application/octet-stream"})
    out.mkdir(exist_ok=True)
    (out / "request.json").write_text(json.dumps({
        "request_key": key, "submitted_at": _now(), "http_status": code,
        "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "response": body.decode(errors="replace")}, indent=1))
    print(f"tessera: submitted {run.name} -> {code}")
    if code != 202:
        sys.exit(1)


def fetch(root: Path) -> None:
    for req_file in sorted(root.glob("20*Z/tessera/request.json")):
        out = req_file.parent
        if (out / "receipt.json").exists():
            continue
        req = json.loads(req_file.read_text())
        if req.get("http_status") != 202:
            continue
        code, body = _call(f"{ENDPOINT}/{req['request_key']}")
        (out / "status.json").write_text(json.dumps({
            "checked_at": _now(), "http_status": code,
            "response": body.decode(errors="replace")}, indent=1))
        state = json.loads(body).get("state") if code == 200 else None
        print(f"tessera: {out.parent.name} -> {state or code}")
        if state != "COMPLETE":
            continue
        code, receipt = _call(f"{ENDPOINT}/{req['request_key']}/receipt")
        if code == 200 and hashlib.sha256(receipt).hexdigest() == json.loads(body).get("receipt_sha256"):
            (out / "receipt.json").write_bytes(receipt)
            print(f"tessera: {out.parent.name} receipt saved and its sha256 matches")
        else:
            print(f"tessera: {out.parent.name} receipt fetch {code} or sha256 mismatch; retry next run")


if __name__ == "__main__":
    {"submit": submit, "fetch": fetch}[sys.argv[1]](Path(sys.argv[2]))
