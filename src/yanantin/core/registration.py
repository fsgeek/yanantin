"""Provider registration — the common core's first primitive (gh #1, C0).

A **registrar** owns one collection and accepts **registrants** that
contribute into it. A registrant may itself be a registrar (the stacking
edge), which is how one recursive primitive produces both topologies:
"own a collection" (one registrant, no collapse) and "contribute to a
shared collection" (many registrants, one owned collection, provider
identity as a field). Registration STACKS; the registrar tree is the
substrate's logical data model, and it makes the catalog of what-exists
**data, not code** — the precondition for find-across-silos.

Ported in spirit from Indaleko's `IndalekoRegistrationService`, stripped
of its singleton / ServiceManager / OSError-swallowing / INDALEKO_ROOT
bootstrap. Fail-stop: a registry that cannot reach its store RAISES; it
never returns an empty list that reads as "no registrants."

The registrar rides on a `StandardDatabase` handle it is HANDED — it uses
whatever principal it is given. Which principal/DB a call routes to is an
*above* concern (the routing seam), not registration's to decide. Because
registration is scoped to the handle it holds, it is per-StandardDatabase:
the boundary that scopes "what exists here" is the same boundary that
scopes "who can see it."
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from arango.database import StandardDatabase
from pydantic import BaseModel, ConfigDict, Field

from yanantin.apacheta.models.provenance_edge import ProvenanceEdge
from yanantin.core.collection_definition import CollectionDefinition, arangodb_schema
from yanantin.core.khipu import Khipu
from yanantin.core.storage_obfuscator import StorageObfuscator, TransparentObfuscator


class RegistrantRecord(BaseModel):
    """A single registration — core's own record, NOT transport's DTO.

    `frozen=True`: a registration, once made, is immutable. You supersede,
    you do not mutate (matching supersession-in-place).

    `extra="allow"`: the record never refuses a field it didn't anticipate.
    Provider kinds nobody has invented yet carry kind-specific metadata that
    is KEPT, not rejected. This is the save-it-all law and Harness-1's
    "type the mechanical, leave the rest free" made structural — and the
    enabling condition for stacking (a shared collection can only absorb
    heterogeneous registrants losslessly if it keeps their divergent fields).
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    # Typed spine — the mechanical, validated part:
    registrant_id: UUID
    registrant_name: str
    registrant_kind: str  # e.g. "provider" vs "registrar" — the stacking edge
    description: str
    contributes_schema: dict | None = None
    parent_id: UUID | None = None  # the registrar registered with; None only for base
    registered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    active: bool = True
    # Everything else: allowed and stored.


class Registrar:
    """A registrar node: owns one catalog collection, accepts registrants.

    Flat-but-layered for C0 (Tony's call): "a registrar is itself a
    registrant" is an *additive* later step, not a rewrite. Registration is
    rare (init-time), so a 3-4-deep walk that is annoying to walk beats a
    pretty recursive abstraction that bites later.
    """

    def __init__(
        self,
        db: StandardDatabase,
        khipu: Khipu,
        catalog_collection: str,
        name: str,
        description: str,
        obfuscator: StorageObfuscator | None = None,
        owned_collection: str | None = None,
        owned_edge_collection: str | None = None,
    ) -> None:
        self._db = db
        self.name = name
        self.description = description
        # Names pass through the obfuscator from the first pour — "literal now,
        # obfuscate later" is an illusion of choice. The default is transparent
        # (dev/test); the fortress supplies the keyed one. The physical
        # collection the DB sees is the obfuscated name; semantic stays here.
        # Khipu is the SOLE collection creator: this registrar never calls
        # create_collection itself — it hands SEMANTIC names to watay (which
        # obfuscates internally) and reads the obfuscated physical name back off
        # the returned handle's .name for its AQL/insert paths below.
        self._obfuscator = obfuscator or TransparentObfuscator()
        self._semantic_name = catalog_collection
        catalog_handle = khipu.watay(
            catalog_collection,
            CollectionDefinition(schema=arangodb_schema(RegistrantRecord)),
        )
        self._catalog_name = catalog_handle.name

        # The OWNED data collection registrants contribute INTO (the Objects
        # case). Distinct from the catalog (which records who-registered):
        # stacking is many leaves writing into one owned collection, provider
        # identity carried as a FIELD, not as the collection name. Defaults to
        # the catalog itself for the degenerate own-a-collection case.
        owned = owned_collection if owned_collection is not None else catalog_collection
        if self._obfuscator.collection_name(owned) != self._catalog_name:
            # schema=None: schema-less for now. The StorageObject schema lands
            # in A2 after Pour B; until then the owned collection is open.
            owned_handle = khipu.watay(owned, CollectionDefinition(schema=None))
            self._owned_name = owned_handle.name
        else:
            # Degenerate own-a-collection case: owned obfuscates to the same
            # physical name as the catalog — reuse the catalog handle, do NOT
            # double-create (matches today's "only ensure owned when distinct").
            self._owned_name = self._catalog_name

        # Optional OWNED EDGE collection (Case 2: one recorder → Objects doc
        # AND Relationships edge). Edge collections need edge=True so native
        # OUTBOUND traversal works on _from/_to — the generic doc path cannot
        # host edges. None ⇒ this registrar owns no edges.
        self._owned_edge_name = None
        if owned_edge_collection is not None:
            edge_handle = khipu.watay(
                owned_edge_collection,
                CollectionDefinition(
                    schema=arangodb_schema(ProvenanceEdge), edge=True
                ),
            )
            self._owned_edge_name = edge_handle.name

    @property
    def owned_collection_name(self) -> str:
        """The obfuscated owned doc-collection name. A recorder writing through
        this registrar uses it to build canonical edge endpoints WITHOUT
        reaching into private attrs (the spec's 'resolve the handle' seam)."""
        return self._owned_name

    @property
    def owns_owned_collection(self) -> bool:
        """True iff this registrar owns a doc collection distinct from its
        catalog (i.e. it can host shared-collection contributions)."""
        return self._owned_name != self._catalog_name

    @property
    def owns_edge_collection(self) -> bool:
        """True iff this registrar owns an edge collection."""
        return self._owned_edge_name is not None

    def register(
        self,
        registrant_id: UUID,
        registrant_name: str,
        registrant_kind: str,
        description: str,
        **extra,
    ) -> RegistrantRecord:
        """Register a provider (or a child registrar). Stores the typed spine
        plus any extra fields, keyed by registrant_id."""
        if self.lookup_by_identifier(registrant_id) is not None:
            raise ValueError(
                f"registrant {registrant_id} already registered "
                "— supersede, do not clobber (registrations are immutable)"
            )
        record = RegistrantRecord(
            registrant_id=registrant_id,
            registrant_name=registrant_name,
            registrant_kind=registrant_kind,
            description=description,
            **extra,
        )
        doc = record.model_dump(mode="json")
        doc["_key"] = str(registrant_id)
        # Through the obfuscator on the way to storage — field NAMES are
        # obfuscated at rest (the threat model obfuscates labels), exactly as
        # the backend does at arango.py:253. The collection name was already
        # mapped; the document body must be too, or the labels sit in plaintext.
        self._db.collection(self._catalog_name).insert(
            self._obfuscator.obfuscate_document(doc)
        )
        return record

    def lookup_by_identifier(self, registrant_id: UUID) -> RegistrantRecord | None:
        """Return the registrant with this id, or None if not registered."""
        doc = self._db.collection(self._catalog_name).get(str(registrant_id))
        if doc is None:
            return None
        return self._record_from_doc(doc)

    def list_registrants(self) -> list[RegistrantRecord]:
        """Return every registrant in this catalog. Fail-stop: an unreachable
        store raises (the driver propagates), it never returns [] — an empty
        list must mean 'genuinely none', never 'could not reach the store'."""
        cursor = self._db.aql.execute(
            "FOR r IN @@coll RETURN r",
            bind_vars={"@coll": self._catalog_name},
        )
        return [self._record_from_doc(doc) for doc in cursor]

    def _record_from_doc(self, doc: dict) -> RegistrantRecord:
        """Rebuild a RegistrantRecord from a stored document: restore semantic
        field names through the obfuscator, then drop ArangoDB's internal keys
        (the open tail carries everything else)."""
        readable = self._obfuscator.deobfuscate_document(doc)
        clean = {k: v for k, v in readable.items() if not k.startswith("_")}
        return RegistrantRecord(**clean)

    # ── Contribution into the owned collection (the stacking data path) ──
    #
    # register() records WHO declared themselves (the catalog). contribute()
    # is the data path: a registrant writes a record INTO the owned collection
    # (the Objects case), tagged with its identity as a field. Many leaves
    # contributing into one owned collection is how "all files" is one scan and
    # "linux-local only" is a FILTER — the north star, defined against the RAG
    # fan-out. extra="allow" on the shape is what keeps the collapse lossless:
    # divergent platform fields are kept, not rejected.

    def contribute(self, contributor_id: UUID, **fields) -> dict:
        """Write a data record into the owned collection on behalf of a
        registrant. The contributor's identity is stored as a field so the one
        shared collection stays sliceable by provider."""
        doc = {"contributor_id": str(contributor_id), **fields}
        # Obfuscate field names at rest, same as register/the backend. The
        # identity field is just another label; it too lands opaque.
        self._db.collection(self._owned_name).insert(
            self._obfuscator.obfuscate_document(doc)
        )
        return doc

    def list_contributions(self, contributor_id: UUID | None = None) -> list[dict]:
        """Return contributions in the owned collection. With no contributor,
        'all files' in one scan; with one, a FILTER on the identity field —
        one collection, two query shapes. Fail-stop: an unreachable store
        raises, it never returns [] as a false 'none'.

        The FILTER targets the OBFUSCATED field name: under opaque storage the
        identity label is mapped, so the query must speak storage's labels, not
        the caller's. Results are deobfuscated back to semantic names."""
        if contributor_id is None:
            cursor = self._db.aql.execute(
                "FOR d IN @@coll RETURN d",
                bind_vars={"@coll": self._owned_name},
            )
        else:
            id_field = self._obfuscator.field_name("contributor_id")
            cursor = self._db.aql.execute(
                "FOR d IN @@coll FILTER d[@field] == @cid RETURN d",
                bind_vars={
                    "@coll": self._owned_name,
                    "field": id_field,
                    "cid": str(contributor_id),
                },
            )
        return [self._readable_contribution(doc) for doc in cursor]

    def _readable_contribution(self, doc: dict) -> dict:
        """Restore semantic field names and strip ArangoDB internals (_key,
        _id, _rev) — contributions are data, not driver bookkeeping."""
        readable = self._obfuscator.deobfuscate_document(doc)
        return {k: v for k, v in readable.items() if not k.startswith("_")}

    def contribute_edge(
        self,
        contributor_id: UUID,
        from_ref: str,
        to_ref: str,
        relation_type: str,
        **fields,
    ) -> dict:
        """Write an edge into the owned edge collection on behalf of a
        registrant. _from/_to are reference VALUES (canonical collection/key
        form) — they pass through the obfuscator unchanged; only labels map.
        Raises if this registrar owns no edge collection (fail-stop, not a
        silent doc-insert)."""
        if self._owned_edge_name is None:
            raise ValueError(
                "this registrar owns no edge collection; "
                "construct it with owned_edge_collection=..."
            )
        doc = {
            "_from": from_ref,
            "_to": to_ref,
            "relation_type": relation_type,
            "contributor_id": str(contributor_id),
            **fields,
        }
        self._db.collection(self._owned_edge_name).insert(
            self._obfuscator.obfuscate_document(doc)
        )
        return doc

    def list_edge_contributions(
        self, contributor_id: UUID | None = None
    ) -> list[dict]:
        """Edges in the owned edge collection, optionally filtered by provider.
        _from/_to are restored verbatim (reference values, not labels)."""
        if self._owned_edge_name is None:
            raise ValueError("this registrar owns no edge collection")
        if contributor_id is None:
            cursor = self._db.aql.execute(
                "FOR d IN @@coll RETURN d",
                bind_vars={"@coll": self._owned_edge_name},
            )
        else:
            id_field = self._obfuscator.field_name("contributor_id")
            cursor = self._db.aql.execute(
                "FOR d IN @@coll FILTER d[@field] == @cid RETURN d",
                bind_vars={
                    "@coll": self._owned_edge_name,
                    "field": id_field,
                    "cid": str(contributor_id),
                },
            )
        out = []
        for doc in cursor:
            readable = self._obfuscator.deobfuscate_document(doc)
            clean = {k: v for k, v in readable.items() if not k.startswith("_")}
            clean["_from"] = readable["_from"]
            clean["_to"] = readable["_to"]
            out.append(clean)
        return out


BASE_REGISTRANT_CATALOG = "core_registrants"
"""Semantic name of the base catalog. A constant IN CODE only — it reaches
storage solely through obfuscator.collection_name(), so the per-installation
opaque name is the only anchor at rest (no persisted service-UUID; the threat
model is third-party-custodian compromise, see the design doc)."""


class RegistrationService:
    """The Indaleko get_provider_list() seam: owns the well-known base-catalog
    name so callers (the CLI, future tools) never speak a collection name.

    Minus Indaleko's persisted service_uuid — yanantin persists no service
    identity; the opaque base-catalog name is the per-installation anchor.
    """

    def __init__(
        self,
        db: StandardDatabase,
        obfuscator: StorageObfuscator | None = None,
        catalog_collection: str = BASE_REGISTRANT_CATALOG,
        owned_collection: str | None = None,
        owned_edge_collection: str | None = None,
    ) -> None:
        # catalog/owned overrides exist for test isolation (a unique catalog per
        # run, no shared-state pollution of the real base catalog) and so the
        # inspector's contribution_count can read a registrar that owns the same
        # Objects collection a recorder contributes into. Defaults reproduce the
        # production seam exactly: the well-known base catalog, owned == catalog.
        # Khipu is the sole collection creator; it is import-independent and
        # cheap to construct per-service. It shares this service's db and
        # obfuscator so the physical names it mints match the ones the
        # registrar's AQL/insert paths speak.
        self.base_registrar = Registrar(
            db=db,
            khipu=Khipu(db=db, obfuscator=obfuscator),
            catalog_collection=catalog_collection,
            name="core registration service",
            description="the base registrant catalog",
            obfuscator=obfuscator,
            owned_collection=owned_collection,
            owned_edge_collection=owned_edge_collection,
        )

    def get_registrant_list(self) -> list[RegistrantRecord]:
        """Every registrant in the base catalog (the get_provider_list verb)."""
        return self.base_registrar.list_registrants()

    def lookup_by_identifier(self, registrant_id: UUID) -> RegistrantRecord | None:
        return self.base_registrar.lookup_by_identifier(registrant_id)

    def lookup_by_name(self, name: str) -> RegistrantRecord | None:
        """First registrant whose name matches, or None. Names are values
        (unobfuscated), so this is a cheap match over the listed records —
        the verb a human inspector wants (names, not UUIDs)."""
        for r in self.get_registrant_list():
            if r.registrant_name == name:
                return r
        return None

    def contribution_count(self, registrant_id: UUID) -> int:
        """How many data records this registrant owns in the base registrar's
        owned collection. The one place v1 touches the data path — a count
        column for the inspector, not a dump."""
        return len(self.base_registrar.list_contributions(registrant_id))
