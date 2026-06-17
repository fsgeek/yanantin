"""Integration tests for core provider registration (C0).

Per the no-mock-databases rule, these run against the live apacheta_test
database. A mock would prove bookkeeping, not the property the spec demands:
that a registry record — typed spine plus an unanticipated extra field —
round-trips losslessly through ArangoDB (extra="allow" is structural, not
decorative).

Design source: docs/superpowers/specs/2026-06-16-c0-registration-design.md

The registrar rides on a StandardDatabase handle it is HANDED (it uses
whatever principal it is given; identity-per-instance is an above concern).
So the tests inject a real handle from the connection singleton.
"""

from __future__ import annotations

import uuid

import pytest

from arango import ArangoClient
from arango.http import DefaultHTTPClient
from requests.adapters import HTTPAdapter

from yanantin.core.registration import Registrar
from yanantin.infra.config import ApachetaDBConfig, get_database


pytestmark = pytest.mark.integration


class _NoRetryHTTP(DefaultHTTPClient):
    """A driver HTTP client with urllib3 retries disabled.

    The connection singleton (config.py) builds ArangoClient with default
    retries, so a dead host takes ~18s to finally raise — a known, separate,
    xfail'd issue (the conn-error discrimination bug), NOT C0's to fix. For
    the fail-stop test we only need to prove the PROPERTY (raises, never a
    false-empty), so we disable retries to assert it promptly without
    touching production code.
    """

    def create_session(self, host: str):
        session = super().create_session(host)
        session.mount("http://", HTTPAdapter(max_retries=0))
        session.mount("https://", HTTPAdapter(max_retries=0))
        return session


class _OpaqueStandIn:
    """A non-transparent obfuscator that rewrites BOTH collection names AND
    field names, deterministically and reversibly. Stand-in for Pukara's
    SchemaMap. Documents stored through it must carry obfuscated field names
    (the threat model obfuscates LABELS); reads must restore semantic names.
    ArangoDB internals (keys starting with '_') pass through untouched.
    """

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    def collection_name(self, semantic: str) -> str:
        return f"{self._prefix}{semantic}"

    def field_name(self, semantic: str) -> str:
        return f"{self._prefix}{semantic}"

    def field_path(self, parts: tuple[str, ...]) -> str:
        return ".".join(self.field_name(p) for p in parts)

    def reverse_field(self, opaque: str) -> str:
        return opaque[len(self._prefix):] if opaque.startswith(self._prefix) else opaque

    def obfuscate_document(self, doc: dict) -> dict:
        return {
            (k if k.startswith("_") else self.field_name(k)): v
            for k, v in doc.items()
        }

    def deobfuscate_document(self, doc: dict) -> dict:
        return {
            (k if k.startswith("_") else self.reverse_field(k)): v
            for k, v in doc.items()
        }

    @property
    def is_transparent(self) -> bool:
        return False


@pytest.fixture
def live_db():
    """A real StandardDatabase handle on apacheta_test (test-tier creds)."""
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return get_database(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=creds["username"],
        password=creds["password"],
    )


@pytest.fixture
def registrar(live_db):
    """A registrar owning a unique throwaway collection, torn down after."""
    catalog = f"core_reg_catalog_{uuid.uuid4().hex}"
    reg = Registrar(
        db=live_db,
        catalog_collection=catalog,
        name="test-registrar",
        description="ephemeral registrar for C0 tests",
    )
    yield reg
    if live_db.has_collection(catalog):
        live_db.delete_collection(catalog)


def test_register_round_trips_typed_spine_and_an_extra_field(registrar):
    """A registration's typed spine AND an unanticipated extra field both
    survive the round trip through ArangoDB (extra="allow" is structural)."""
    rid = uuid.uuid4()
    registrar.register(
        registrant_id=rid,
        registrant_name="linux-local-fs",
        registrant_kind="provider",
        description="a storage recorder nobody special-cased",
        # a field the typed spine never anticipated:
        platform_quirk="case-sensitive-paths",
    )

    found = registrar.lookup_by_identifier(rid)

    assert found is not None
    assert found.registrant_id == rid
    assert found.registrant_name == "linux-local-fs"
    assert found.registrant_kind == "provider"
    # the unanticipated field was KEPT, not rejected:
    assert found.platform_quirk == "case-sensitive-paths"


def test_re_register_same_identifier_raises(registrar):
    """Re-registering the same UUID raises — no silent overwrite. A
    registration is immutable; you supersede, you do not clobber."""
    rid = uuid.uuid4()
    registrar.register(
        registrant_id=rid,
        registrant_name="first",
        registrant_kind="provider",
        description="the original registration",
    )

    with pytest.raises(ValueError):
        registrar.register(
            registrant_id=rid,
            registrant_name="second",
            registrant_kind="provider",
            description="an attempt to clobber the first",
        )


def test_list_registrants_returns_registered(registrar):
    """list_registrants returns every registrant written into this catalog."""
    ids = {uuid.uuid4() for _ in range(3)}
    for i, rid in enumerate(ids):
        registrar.register(
            registrant_id=rid,
            registrant_name=f"provider-{i}",
            registrant_kind="provider",
            description="one of several",
        )

    listed = registrar.list_registrants()

    assert {r.registrant_id for r in listed} == ids


def test_unreachable_store_raises_not_empty():
    """Fail-stop: a registrar over an unreachable store RAISES — it does not
    return an empty list that reads as 'no registrants'. (Indaleko's
    OSError-swallowing is deliberately NOT ported.)"""
    # A genuinely unreachable store: real loopback, discard port (9), retries
    # disabled so the refusal surfaces in milliseconds. NOT a mock — the socket
    # really fails to connect; we only bound the driver's retry budget so the
    # property can be asserted without an 18s hang.
    dead_client = ArangoClient(
        hosts="http://127.0.0.1:9",
        request_timeout=2,
        resolver_max_tries=1,
        http_client=_NoRetryHTTP(),
    )
    dead = dead_client.db("apacheta_test", username="nobody", password="nothing")

    with pytest.raises(Exception):  # noqa: B017 — any failure beats a false empty
        reg = Registrar(
            db=dead,
            catalog_collection=f"core_reg_dead_{uuid.uuid4().hex}",
            name="doomed",
            description="registrar over an unreachable store",
        )
        # If construction somehow tolerated the dead store, listing MUST still
        # raise rather than hand back a false-empty "no registrants".
        reg.list_registrants()


def test_owned_collection_is_created_under_obfuscated_name(live_db):
    """The registrar's owned collection passes through the obfuscator: under
    an opaque obfuscator the PHYSICAL collection is the obfuscated name, and
    the semantic name does NOT exist. Proves the seam is real, not decorative.
    """
    semantic = f"core_reg_obf_{uuid.uuid4().hex}"
    prefix = "zz_opaque_"
    obfuscated = f"{prefix}{semantic}"
    try:
        Registrar(
            db=live_db,
            catalog_collection=semantic,
            name="opaque-registrar",
            description="registrar behind an opaque obfuscator",
            obfuscator=_OpaqueStandIn(prefix),
        )

        assert live_db.has_collection(obfuscated)
        assert not live_db.has_collection(semantic)
    finally:
        for name in (obfuscated, semantic):
            if live_db.has_collection(name):
                live_db.delete_collection(name)


def test_transparent_and_opaque_obfuscators_yield_different_collections(live_db):
    """Same semantic catalog name, two obfuscators → two different physical
    collections. The seam is load-bearing: the name the DB sees depends on
    the obfuscator, not the caller's string."""
    semantic = f"core_reg_seam_{uuid.uuid4().hex}"
    prefix = "zz_seam_"
    obfuscated = f"{prefix}{semantic}"
    try:
        Registrar(
            db=live_db,
            catalog_collection=semantic,
            name="transparent",
            description="default transparent path",
        )
        Registrar(
            db=live_db,
            catalog_collection=semantic,
            name="opaque",
            description="opaque path",
            obfuscator=_OpaqueStandIn(prefix),
        )

        assert live_db.has_collection(semantic)  # transparent → semantic name
        assert live_db.has_collection(obfuscated)  # opaque → obfuscated name
    finally:
        for name in (semantic, obfuscated):
            if live_db.has_collection(name):
                live_db.delete_collection(name)


def test_stacking_reproduces_objects_as_one_shared_collection(live_db):
    """The load-bearing test: base ◀ storage-object-registrar(owns Objects) ◀
    {linux-local, windows-local}. Both leaves register AND contribute file
    records into the ONE owned Objects collection. Proves the spec's claim
    that Objects is reproducible by stacking, and that extra="allow" is what
    makes the lossless heterogeneous collapse work.
    """
    suffix = uuid.uuid4().hex
    catalog = f"core_reg_stack_catalog_{suffix}"
    objects = f"core_reg_stack_objects_{suffix}"

    linux_id = uuid.uuid4()
    windows_id = uuid.uuid4()

    try:
        # The storage-object registrar owns the shared Objects collection.
        store_reg = Registrar(
            db=live_db,
            catalog_collection=catalog,
            name="storage-object-registrar",
            description="owns the shared Objects space",
            owned_collection=objects,
        )

        # Two platform recorders register with it (the stacking edge: they are
        # registrants; the registrar itself would register upward with base).
        store_reg.register(
            registrant_id=linux_id,
            registrant_name="linux-local-fs",
            registrant_kind="provider",
            description="linux local filesystem recorder",
        )
        store_reg.register(
            registrant_id=windows_id,
            registrant_name="windows-local-fs",
            registrant_kind="provider",
            description="windows local filesystem recorder",
        )

        # Each leaf contributes a file-object record into the ONE Objects
        # collection: shared spine (path) + a platform-specific extra field.
        store_reg.contribute(
            contributor_id=linux_id,
            path="/srv/data/notes.md",
            inode=123456,  # linux-specific extra
        )
        store_reg.contribute(
            contributor_id=windows_id,
            path=r"C:\Users\tony\notes.md",
            ntfs_id="0x1A2B3C",  # windows-specific extra
        )

        # (a) one collection, not three (catalog + objects only; no per-leaf)
        assert live_db.has_collection(objects)
        # (b) "all files" = ONE scan returns both
        all_files = store_reg.list_contributions()
        assert len(all_files) == 2
        # (c) "linux-local only" = a FILTER on the contributor identity field
        linux_only = store_reg.list_contributions(contributor_id=linux_id)
        assert len(linux_only) == 1
        assert linux_only[0]["path"] == "/srv/data/notes.md"
        # (d) both platforms' extra fields survived (lossless collapse)
        by_contributor = {r["contributor_id"]: r for r in all_files}
        assert by_contributor[str(linux_id)]["inode"] == 123456
        assert by_contributor[str(windows_id)]["ntfs_id"] == "0x1A2B3C"
    finally:
        for name in (catalog, objects):
            if live_db.has_collection(name):
                live_db.delete_collection(name)


def test_field_names_are_obfuscated_in_stored_documents(live_db):
    """The seam the spec demands and the first build missed: under an opaque
    obfuscator, the RAW stored document carries OBFUSCATED field names (the
    threat model obfuscates labels), while lookup still returns semantic ones.
    Proves contribute/register run documents through the obfuscator, not just
    the collection name.
    """
    semantic_catalog = f"core_reg_fieldobf_{uuid.uuid4().hex}"
    prefix = "zz_field_"
    obf = _OpaqueStandIn(prefix)
    obf_catalog = f"{prefix}{semantic_catalog}"
    rid = uuid.uuid4()
    try:
        reg = Registrar(
            db=live_db,
            catalog_collection=semantic_catalog,
            name="field-obf-registrar",
            description="proves field-name obfuscation",
            obfuscator=obf,
        )
        reg.register(
            registrant_id=rid,
            registrant_name="some-provider",
            registrant_kind="provider",
            description="its fields must be obfuscated at rest",
        )

        # Raw document, read WITHOUT the obfuscator: field names are opaque.
        raw = live_db.collection(obf_catalog).get(str(rid))
        assert f"{prefix}registrant_name" in raw  # obfuscated label present
        assert "registrant_name" not in raw       # semantic label absent at rest

        # Through the registrar: semantic names restored.
        found = reg.lookup_by_identifier(rid)
        assert found is not None
        assert found.registrant_name == "some-provider"
    finally:
        if live_db.has_collection(obf_catalog):
            live_db.delete_collection(obf_catalog)


def test_contributions_do_not_leak_arango_key(registrar):
    """list_contributions must not leak ArangoDB's _key (an internal id, not
    registrant data). _record_from_doc strips all underscore keys; the
    contribution path must be just as clean."""
    rid = uuid.uuid4()
    registrar.register(
        registrant_id=rid,
        registrant_name="contributor",
        registrant_kind="provider",
        description="contributes one record",
    )
    registrar.contribute(contributor_id=rid, path="/srv/data/x.md")

    rows = registrar.list_contributions()

    assert rows, "expected one contribution"
    assert all("_key" not in r for r in rows)
    assert all(not k.startswith("_") for r in rows for k in r)
