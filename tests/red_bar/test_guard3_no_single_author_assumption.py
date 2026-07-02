"""GUARD 3 (accretion): no query may be optimized on the single-author assumption.

The single-principal standing decision
(pukara/docs/decisions/2026-06-06-single-principal-substrate-standing-decision.md)
lists three accretion guards. Guards 1 and 2 are red bars in
test_single_principal_accretion.py. Guard 3 was left as PROSE — a
"structural-review obligation" — because the authors judged it un-mechanizable:
"a single-author query looks correct until a second author exists."

But the doc's own thesis is that prose erodes; only red bars hold. And the doc
handed the mechanism in its own hint (lines 108-109): assert the corpus contains,
or CAN contain, more than one distinct author_instance_id, so no query may assume
singularity. The move is the same one that runs through the substrate — make the
dangerous assumption the TESTED-against one (cf. the non-transparent obfuscator
default): you cannot inspect an arbitrary query for a single-author assumption,
but you CAN poison the environment with plurality so any query that collapses to
one author returns observably wrong results.

This is that guard, made real:
  1. A deliberately PLURAL corpus (>=2 distinct author_instance_ids).
  2. list_author_instances() must round-trip the plurality (>=2) — the query
     whose whole correctness depends on the corpus being able to hold >1 author.
  3. query_open_by_author_instance(A) must return ONLY A's records — the author
     filter genuinely partitions. A query that ignored the author (the
     single-author collapse) would return B's records too and fail here.

Live DB, config-file creds (env path silently skips in a worktree).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.provenance import ProvenanceEnvelope
from yanantin.infra.config import ApachetaDBConfig

pytestmark = pytest.mark.integration

_DB = "apacheta_test"


def _conn():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return cfg.host_url, creds["username"], creds["password"]


def _available() -> bool:
    try:
        host, user, pwd = _conn()
        ArangoDBBackend(host=host, db_name=_DB, username=user, password=pwd)._db.collections()
        return True
    except Exception:
        return False


@pytest.fixture
def backend():
    if not _available():
        pytest.skip("ArangoDB test database not available")
    host, user, pwd = _conn()
    db = ArangoDBBackend(host=host, db_name=_DB, username=user, password=pwd)
    db._db.collection("records").truncate()
    yield db
    db._db.collection("records").truncate()
    db.close()


def _record(author: str, ts: datetime) -> ApachetaBaseModel:
    return ApachetaBaseModel(
        provenance=ProvenanceEnvelope(
            author_model_family="claude",
            author_instance_id=author,
            predecessors_in_scope=(),
            timestamp=ts,
        ),
        lineage_tags=(),
    )


def _seed_plural(backend) -> tuple[str, str]:
    """Seed the corpus with TWO distinct authors. The plurality is the guard."""
    a, b = "instance-A", "instance-B"
    base = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    backend.store_record(uuid4(), _record(a, base))
    backend.store_record(uuid4(), _record(a, base.replace(hour=13)))
    backend.store_record(uuid4(), _record(b, base.replace(hour=14)))
    return a, b


def test_corpus_holds_more_than_one_author_and_list_reflects_it(backend):
    """list_author_instances() must return BOTH authors. A substrate or query
    that collapsed to one author would return fewer — the guard fails."""
    a, b = _seed_plural(backend)

    authors = set(backend.list_author_instances())

    assert {a, b} <= authors, (
        f"corpus seeded with 2 distinct authors but list_author_instances "
        f"returned {authors} — a single-author assumption is present "
        "(Guard 3, single-principal standing decision)"
    )


def test_author_filter_partitions_and_excludes_the_other_author(backend):
    """query_open_by_author_instance(A) returns ONLY A's records. A query that
    ignored the author (the single-author collapse) would return B's too."""
    a, b = _seed_plural(backend)

    a_records = backend.query_open_by_author_instance(a)
    b_records = backend.query_open_by_author_instance(b)

    # Hydrated open records carry provenance as a dict, not a typed envelope.
    a_authors = {r.provenance["author_instance_id"] for (_, r) in a_records}
    b_authors = {r.provenance["author_instance_id"] for (_, r) in b_records}

    assert a_authors == {a}, f"query for {a} leaked other authors: {a_authors}"
    assert b_authors == {b}, f"query for {b} leaked other authors: {b_authors}"
    assert len(a_records) == 2 and len(b_records) == 1
