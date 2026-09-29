"""Passage-index acceptance tests on isolated collections in apacheta_test."""

from dataclasses import FrozenInstanceError, asdict
import json
import os
from uuid import UUID, uuid4

import pytest
from arango.exceptions import ArangoClientError
from tiksi.provenance import SourceIdentifier

from tests.integration._obfuscators import HashingObfuscator
from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.interface.errors import ImmutabilityError
from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.core.storage_obfuscator import TransparentObfuscator
from yanantin.infra.config import ApachetaDBConfig, get_database
from yanantin.llika import LlikaService
from yanantin.llika.models import FindHit, FindResult

pytestmark = pytest.mark.integration


class IsolatedTransparentMap(TransparentObfuscator):
    """Identity fields/values, unique physical collections to avoid shared data."""

    def __init__(self):
        self.names = HashingObfuscator(uuid4().hex)

    def collection_name(self, semantic):
        return self.names.collection_name(semantic)

    @property
    def collection_names(self):
        return self.names.collection_names


@pytest.fixture
def backend_factory():
    if os.environ.get("APACHETA_SKIP_ARANGO"):
        pytest.skip("APACHETA_SKIP_ARANGO is set")
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    connection = dict(host=cfg.host_url, db_name="apacheta_test",
                      username=creds["username"], password=creds["password"])
    try:
        db = get_database(**connection)
        db.collections()
    except (ArangoClientError, ConnectionError) as exc:
        pytest.skip(f"Live ArangoDB apacheta_test is unreachable: {exc}")
    assert db.name == "apacheta_test"
    before_collections = {c["name"] for c in db.collections()}
    before_views = {v["name"] for v in db.views()}
    maps = []
    backends = []

    def create(mapping=None):
        if mapping is None:
            mapping = IsolatedTransparentMap()
        # Register BEFORE construction so partially failed initialization cleans up.
        maps.append(mapping)
        backend = ArangoDBBackend(**connection, obfuscator=mapping)
        backends.append(backend)
        return backend

    try:
        yield create
    finally:
        owned = set().union(*(m.collection_names for m in maps))
        # Also remove accidentally un-mapped feature artifacts if newly created.
        owned.update({"passages", "passages_bm25"})
        try:
            for name in owned - before_views:
                db.delete_view(name, ignore_missing=True)
        finally:
            for name in owned - before_collections:
                db.delete_collection(name, ignore_missing=True)
            for backend in backends:
                backend.close()


@pytest.fixture
def passage_backend(backend_factory):
    return backend_factory()


def provenance(session=None):
    return ProvenanceEnvelope(
        source=SourceIdentifier(identifier=uuid4(), description="passage index test"),
        author_model_family="test",
        author_instance_id=str(session if session is not None else uuid4()),
    )


def store(backend, *, session=None, record_id=None, **fields):
    record_id = record_id if record_id is not None else uuid4()
    backend.store_record(record_id, ApachetaBaseModel(provenance=provenance(session), **fields))
    return str(record_id)


def collection(backend, semantic):
    return backend._db.collection(backend._map.collection_name(semantic))


def passage_snapshot(backend):
    return {
        doc["_key"]: {k: v for k, v in doc.items() if k not in {"_rev", "_id"}}
        for doc in collection(backend, "passages").all()
    }


def ids(result):
    return {hit.record_id for hit in result.hits}


def test_find_stems_passage_values(passage_backend):
    key = store(passage_backend, body={"observation": "The mice were running."})
    result = passage_backend.find("runs")
    assert ids(result) == {key}
    assert result.hits[0].matched_fields == ("body.observation",)


def test_find_reward_function_with_spaces_and_underscores(passage_backend):
    key = store(passage_backend, body={"description": "reward_function"})
    assert ids(passage_backend.find("reward function")) == {key}
    assert ids(passage_backend.find("reward_function")) == {key}


def test_find_first_owner_within_session(passage_backend):
    session = uuid4()
    first = store(passage_backend, session=session, body={"text": "quartz ownership"})
    second = store(passage_backend, session=session, body={"text": "quartz ownership"})
    result = passage_backend.find("quartz")
    assert ids(result) == {first}
    assert second not in ids(result)
    assert result.total_matched == 1
    assert {p["record_key"] for p in passage_snapshot(passage_backend).values()} == {first}


def test_find_both_owners_across_two_sessions(passage_backend):
    keys = {store(passage_backend, body={"text": "quartz ownership"}) for _ in range(2)}
    result = passage_backend.find("quartz")
    assert ids(result) == keys
    assert result.total_matched == 2


def test_find_exact_distinct_total_and_truncated_above_limit(passage_backend):
    keys = {
        store(passage_backend, body={"first": "quartz", "second": "quartz crystal"})
        for _ in range(7)
    }
    limited = passage_backend.find("quartz", limit=3)
    assert len(limited.hits) == len(ids(limited)) == 3
    assert ids(limited) <= keys
    assert limited.total_matched == 7  # records, not the fourteen passages
    assert limited.truncated is True
    complete = passage_backend.find("quartz", limit=7)
    assert ids(complete) == keys
    assert complete.total_matched == 7
    assert complete.truncated is False
    assert passage_backend.find("quartz", limit=8).truncated is False


def test_record_findable_immediately_after_store_record(passage_backend):
    record_id = uuid4()
    key = store(passage_backend, record_id=record_id, id="not_the_record_key",
                body={"nested": "instantaneous visibility"})
    # No sleeps, retries, manual sync, or polling: find must waitForSync itself.
    assert ids(passage_backend.find("instantaneous")) == {key}
    passages = passage_snapshot(passage_backend)
    assert {p["path"] for p in passages.values()} == {"body.nested"}
    assert {p["record_key"] for p in passages.values()} == {str(record_id)}


def test_duplicate_record_raises_and_preserves_passage_count(passage_backend):
    record_id = uuid4()
    store(passage_backend, record_id=record_id, body={"text": "original quartz"})
    before = passage_snapshot(passage_backend)
    assert before
    with pytest.raises(ImmutabilityError):
        store(passage_backend, record_id=record_id, body={"text": "replacement sapphire"})
    after = passage_snapshot(passage_backend)
    assert len(after) == len(before)
    assert after == before
    assert ids(passage_backend.find("quartz")) == {str(record_id)}
    assert passage_backend.find("sapphire").total_matched == 0


def test_sync_passages_twice_preserves_set_and_backfills_in_instrument_order(passage_backend):
    from yanantin.apacheta.passages import derive_passages, sync_passages

    session = uuid4()
    # Store out of cycle order; remove ONLY these isolated derived documents to
    # represent an old writer. All source records still use public store_record.
    later = store(passage_backend, session=session, lineage_tags=("cycle-2",), body="shared quartz")
    first = store(passage_backend, session=session, lineage_tags=("cycle-1",), body="shared quartz")
    orphan = uuid4()
    passage_backend.store_record(orphan, ApachetaBaseModel(body="orphan sapphire"))
    passages = collection(passage_backend, "passages")
    for doc in list(passages.all()):
        passages.delete(doc["_key"])
    expected = {}
    records = collection(passage_backend, "records")
    for key in (first, later, str(orphan)):
        for p in derive_passages(records.get(key), key):
            expected.setdefault(p["_key"], p)
    count1 = sync_passages(passage_backend)
    once = passage_snapshot(passage_backend)
    count2 = sync_passages(passage_backend)
    assert type(count1) is int and type(count2) is int
    assert once == expected
    assert passage_snapshot(passage_backend) == once
    assert ids(passage_backend.find("quartz")) == {first}
    assert ids(passage_backend.find("sapphire")) == {str(orphan)}


def test_existing_llika_service_find_contract(passage_backend):
    service = LlikaService(passage_backend, provenance())
    key = store(passage_backend, body={"text": "quartz " + "crystal " * 30})
    result = service.find("quartz")
    assert result == passage_backend.find("quartz")
    assert isinstance(result, FindResult)
    assert isinstance(result.hits, tuple)
    assert result.total_matched == 1 and result.truncated is False
    hit = result.hits[0]
    assert isinstance(hit, FindHit)
    assert hit.record_id == key and str(UUID(hit.record_id)) == key
    assert hit.matched_fields == ("body.text",)
    assert hit.snippet == ("quartz " + "crystal " * 30)[:120]
    json.dumps(asdict(result))
    with pytest.raises(FrozenInstanceError):
        result.total_matched = 0
    with pytest.raises(FrozenInstanceError):
        hit.snippet = "changed"
    executed = False

    def tripwire():
        nonlocal executed
        executed = True
        return "quartz"

    with pytest.raises((AttributeError, TypeError)):
        service.find(tripwire)
    assert executed is False
    assert not hasattr(service, "update")
    assert not hasattr(service, "delete")
