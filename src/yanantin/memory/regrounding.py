"""Re-ground one stored claim against the live store.

The feedback edge (2026-06-28-ayllu-topology-vocabulary.md) applied to a memory
claim: the frozen value is the stored object, the live count is the source, and
`reground` is the depth-1 one-shot re-collect that returns both. Nothing is
overwritten — the frozen value is kept beside the live one as the evidence the
drift existed (rule 1: before/after visible).

Two claim kinds now: `collection_count` (a number, re-grounded against the live
DB) and `code_fact` (a claim-about-source, re-grounded against the live tree).
The second kind forced the dispatch — it is here now (extract-on-the-second-instance).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from yanantin.infra.config import ApachetaDBConfig


class UnsupportedClaimKind(ValueError):
    """A claim kind that re-grounding does not (yet) know how to check."""


@dataclass(frozen=True)
class Regrounding:
    """The result of re-grounding one `collection_count` claim: stored AND live."""

    stored: int
    live: int
    as_of: str
    stale: bool
    collection: str
    db: str

    def render(self) -> str:
        if self.stale:
            return (
                f"{self.live} (live; stored claim {self.stored}, "
                f"as of {self.as_of})"
            )
        return (
            f"{self.live} (live; matches stored claim, as of {self.as_of})"
        )

    def __str__(self) -> str:
        return self.render()


@dataclass(frozen=True)
class CodeFactRegrounding:
    """Re-grounding a claim-about-source against the live tree: expected AND actual.

    `stored` is the frozen expectation (the substring the memory swears is in the
    file); `live` is what the tree actually holds — either the confirmed substring
    or a marker that the file is gone / the string is absent. Both kept side by
    side, same as the count case (rule 1: before/after visible).
    """

    stored: str
    live: str
    as_of: str
    stale: bool
    file: str

    def render(self) -> str:
        if self.stale:
            return (
                f"{self.file}: {self.live} "
                f"(stored claim {self.stored!r}, as of {self.as_of})"
            )
        return (
            f"{self.file}: still contains {self.stored!r} "
            f"(matches stored claim, as of {self.as_of})"
        )

    def __str__(self) -> str:
        return self.render()


def _live_collection_count(db_name: str, collection: str) -> int:
    """Count one collection in any silo via the admin tier.

    Admin reaches `_system`; from there we open the named database by handle.
    Read-only — a count, never a write. Reuses the connection singleton so this
    does not fork a new client (config.py: get_database behind connect).
    """
    cfg = ApachetaDBConfig()
    creds = cfg.get_admin_credentials()
    from arango import ArangoClient

    client = ArangoClient(hosts=cfg.host_url)
    db = client.db(db_name, username=creds["username"], password=creds["password"])
    return db.collection(collection).count()


def reground(
    claim: dict, root: Path | None = None
) -> Regrounding | CodeFactRegrounding:
    """Re-ground one claim against its live source; return frozen AND live.

    Dispatches on `kind`:
      - `collection_count` → the live DB (a number).
      - `code_fact` → the live working tree under `root` (a claim-about-source).

    Staleness is the divergence between frozen and live. Unsupported kinds raise
    UnsupportedClaimKind. `root` is only consulted for `code_fact`.
    """
    kind = claim.get("kind")
    if kind == "collection_count":
        return _reground_collection_count(claim)
    if kind == "code_fact":
        return _reground_code_fact(claim, root or Path.cwd())
    raise UnsupportedClaimKind(
        f"unsupported claim kind {kind!r}; "
        "grounded kinds are 'collection_count' and 'code_fact'"
    )


def _reground_collection_count(claim: dict) -> Regrounding:
    stored = int(claim["value"])
    live = _live_collection_count(claim["db"], claim["collection"])
    return Regrounding(
        stored=stored,
        live=live,
        as_of=claim["as_of"],
        stale=stored != live,
        collection=claim["collection"],
        db=claim["db"],
    )


def _reground_code_fact(claim: dict, root: Path) -> CodeFactRegrounding:
    """Re-ground a `code_fact` claim against the live tree.

    The frozen expectation is a substring the memory swears is in the file. The
    live reality is one of: the substring confirmed present, the substring absent,
    or the file gone entirely — the sharpest drift (memory points at a path that
    no longer exists). A missing file or absent string is stale, never a crash.
    """
    expect = str(claim["expect"])
    rel = claim["file"]
    path = root / rel

    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError):
        return CodeFactRegrounding(
            stored=expect,
            live=f"file {rel} not found",
            as_of=claim["as_of"],
            stale=True,
            file=rel,
        )

    present = expect in text
    return CodeFactRegrounding(
        stored=expect,
        live=(
            f"present in {rel}"
            if present
            else f"{expect!r} absent from {rel}"
        ),
        as_of=claim["as_of"],
        stale=not present,
        file=rel,
    )
