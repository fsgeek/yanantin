"""Re-ground one stored claim against the live store.

The feedback edge (2026-06-28-ayllu-topology-vocabulary.md) applied to a memory
claim: the frozen value is the stored object, the live count is the source, and
`reground` is the depth-1 one-shot re-collect that returns both. Nothing is
overwritten — the frozen value is kept beside the live one as the evidence the
drift existed (rule 1: before/after visible).

One claim kind today: `collection_count`. The second kind forces the dispatch
abstraction — not before it exists (extract-on-the-second-instance).
"""

from __future__ import annotations

from dataclasses import dataclass

from yanantin.infra.config import ApachetaDBConfig


class UnsupportedClaimKind(ValueError):
    """A claim kind that re-grounding does not (yet) know how to check."""


@dataclass(frozen=True)
class Regrounding:
    """The result of re-grounding one claim: stored AND live, side by side."""

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


def reground(claim: dict) -> Regrounding:
    """Re-ground one `collection_count` claim against the live store.

    Returns both the frozen value and the live count; staleness is the
    inequality between them. Unsupported kinds raise UnsupportedClaimKind —
    the second kind will force a dispatch, not this one.
    """
    kind = claim.get("kind")
    if kind != "collection_count":
        raise UnsupportedClaimKind(
            f"unsupported claim kind {kind!r}; only 'collection_count' is grounded"
        )

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
