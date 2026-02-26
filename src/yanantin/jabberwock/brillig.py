"""The Brillig service: resolution, observation, traversal.

"Four o'clock -- time when you begin broiling things."

Brillig cooks raw observations into resolved views. It sits on top of
an ActivityStreamStore, storing all Jabberwock records as FactRecords
with type-specific provider UUIDs.

Resolution is late-bound: Frabjous is never cached, never stored,
constructed fresh on every call. Python-side joins. Falls over at
Indaleko scale. Acceptable for the classroom problem, the project
identity problem, and the AI colleague problem.

Declared loss: no AQL pushdown, no view-based resolution, no
Tumtum layers. All of those are future path (see spec).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.apacheta.interface.errors import NotFoundError
from yanantin.jabberwock.models import (
    JABBERWOCK_PROVIDER,
    RATH_PROVIDER,
    ROOT_BANDERSNATCH_ID,
    TOVE_PROVIDER,
    VORPAL_PROVIDER,
    Frabjous,
    Jabberwock,
    MomeResult,
    Rath,
    Tove,
    Vorpal,
)
from yanantin.jabberwock.normalize import normalize_gimble


class Brillig:
    """Resolution service. Cooks raw observations into views.

    All write operations append FactRecords to the store.
    All read operations query facts and reconstruct models.
    Nothing is cached. Nothing is mutated.
    """

    def __init__(self, store: ActivityStreamStore) -> None:
        self._store = store

    # -- Bootstrap ---------------------------------------------------------

    def bootstrap(self) -> Jabberwock:
        """Create the root bandersnatch -- the Ouroboros.

        Self-referential: id == bandersnatch. Solves the genesis
        problem: every record requires a provider, this is the first.

        Creates:
        1. Root Jabberwock (self-referential)
        2. Species Vorpal: tulgey="species", snicker_snack="system"
        3. System Tove: wabe="system", gimble="root"

        Idempotent: if root already exists, returns it without creating
        duplicates.
        """
        # Check if root already bootstrapped
        existing = self._store.query_range(
            provider_id=JABBERWOCK_PROVIDER,
        )
        for fact in existing:
            if fact.data.get("id") == str(ROOT_BANDERSNATCH_ID):
                return Jabberwock(**self._deserialize_jabberwock(fact.data))

        now = datetime.now(timezone.utc)

        # 1. Root Jabberwock
        root = Jabberwock(
            id=ROOT_BANDERSNATCH_ID,
            brillig=now,
            bandersnatch=ROOT_BANDERSNATCH_ID,
        )
        self._store_jabberwock(root)

        # 2. Species Vorpal
        self.outgrabe(
            jabberwock_id=ROOT_BANDERSNATCH_ID,
            tulgey="species",
            snicker_snack="system",
            bandersnatch=ROOT_BANDERSNATCH_ID,
        )

        # 3. System Tove
        self.slithy(
            jabberwock_id=ROOT_BANDERSNATCH_ID,
            wabe="system",
            gimble="root",
            bandersnatch=ROOT_BANDERSNATCH_ID,
        )

        return root

    # -- Entity creation ---------------------------------------------------

    def beamish(self, bandersnatch: UUID | None = None) -> Jabberwock:
        """Declare a new entity into existence.

        Uses ROOT_BANDERSNATCH_ID as the provider if none specified.
        Returns the newly created Jabberwock.
        """
        provider = bandersnatch if bandersnatch is not None else ROOT_BANDERSNATCH_ID
        now = datetime.now(timezone.utc)

        entity = Jabberwock(
            brillig=now,
            bandersnatch=provider,
        )
        self._store_jabberwock(entity)
        return entity

    # -- Observation -------------------------------------------------------

    def outgrabe(
        self,
        jabberwock_id: UUID | None,
        tulgey: str,
        snicker_snack: Any,
        bandersnatch: UUID | None = None,
    ) -> Vorpal:
        """Observe: push a fact about an entity. Fire and forget.

        jabberwock_id=None creates a mome vorpal (still walking).
        bandersnatch defaults to ROOT_BANDERSNATCH_ID if not specified.
        """
        provider = bandersnatch if bandersnatch is not None else ROOT_BANDERSNATCH_ID
        now = datetime.now(timezone.utc)

        vorpal = Vorpal(
            jabberwock_id=jabberwock_id,
            tulgey=tulgey,
            snicker_snack=snicker_snack,
            bandersnatch=provider,
            brillig=now,
        )
        self._store_vorpal(vorpal)
        return vorpal

    # -- Alias creation ----------------------------------------------------

    def slithy(
        self,
        jabberwock_id: UUID | None,
        wabe: str,
        gimble: str,
        gyre_from: datetime | None = None,
        gyre_to: datetime | None = None,
        bandersnatch: UUID | None = None,
    ) -> Tove:
        """Alias: declare a projection of an entity into a namespace.

        gimble is normalized per wabe rules before storage.
        jabberwock_id=None creates a mome tove (unresolved).
        gyre_from defaults to now if not specified.
        bandersnatch defaults to ROOT_BANDERSNATCH_ID if not specified.
        """
        provider = bandersnatch if bandersnatch is not None else ROOT_BANDERSNATCH_ID
        now = datetime.now(timezone.utc)
        canonical_gimble = normalize_gimble(wabe, gimble)

        tove = Tove(
            jabberwock_id=jabberwock_id,
            wabe=wabe,
            gimble=canonical_gimble,
            gyre_from=gyre_from if gyre_from is not None else now,
            gyre_to=gyre_to,
            bandersnatch=provider,
            brillig=now,
        )
        self._store_tove(tove)
        return tove

    # -- Resolution --------------------------------------------------------

    def galumph(self, wabe: str, gimble: str) -> Frabjous | MomeResult:
        """Resolve: (namespace, identifier) -> entity + all projections.

        Returns Frabjous if fully resolved to a single entity.
        Returns MomeResult if:
        - The alias exists but is unresolved (mome tove)
        - Multiple candidates exist
        - No alias exists at all (empty MomeResult)
        """
        canonical_gimble = normalize_gimble(wabe, gimble)

        # Find all Toves matching (wabe, canonical_gimble)
        all_toves = self._load_all_toves()
        matching_toves = [
            t for t in all_toves
            if t.wabe == wabe and t.gimble == canonical_gimble
        ]

        if not matching_toves:
            # Nothing found at all
            return MomeResult()

        # Collect distinct jabberwock_ids (excluding None/mome)
        resolved_ids: set[UUID] = set()
        mome_toves: list[Tove] = []
        for tove in matching_toves:
            if tove.jabberwock_id is not None:
                resolved_ids.add(tove.jabberwock_id)
            else:
                mome_toves.append(tove)

        # If all toves are mome, return MomeResult
        if not resolved_ids:
            return MomeResult(
                toves=tuple(matching_toves),
                mome_vorpals=tuple(self.mome_vorpals()),
            )

        # If exactly one resolved entity, return Frabjous
        if len(resolved_ids) == 1:
            jabberwock_id = next(iter(resolved_ids))
            return self.uffish(jabberwock_id)

        # Multiple candidates -- return MomeResult with candidates
        candidates = []
        for jid in resolved_ids:
            try:
                jabberwock = self._load_jabberwock(jid)
                candidates.append(jabberwock)
            except NotFoundError:
                pass

        return MomeResult(
            toves=tuple(matching_toves),
            candidates=tuple(candidates),
        )

    def uffish(self, jabberwock_id: UUID) -> Frabjous:
        """Materialize: entity UUID -> full view from all observations.

        Queries all Toves, Vorpals, and Raths for the given entity,
        folds them into a Frabjous. Raises NotFoundError if the
        Jabberwock entity doesn't exist.
        """
        jabberwock = self._load_jabberwock(jabberwock_id)

        # Gather all projections
        all_toves = self._load_all_toves()
        entity_toves = [t for t in all_toves if t.jabberwock_id == jabberwock_id]

        all_vorpals = self._load_all_vorpals()
        entity_vorpals = [v for v in all_vorpals if v.jabberwock_id == jabberwock_id]

        all_raths = self._load_all_raths()
        entity_raths = [r for r in all_raths if r.jabberwock_id == jabberwock_id]

        # Collect evidence IDs
        evidence: list[UUID] = [jabberwock.id]
        evidence.extend(t.id for t in entity_toves)
        evidence.extend(v.id for v in entity_vorpals)
        evidence.extend(r.id for r in entity_raths)

        now = datetime.now(timezone.utc)

        return Frabjous(
            jabberwock=jabberwock,
            toves=tuple(entity_toves),
            vorpals=tuple(entity_vorpals),
            raths=tuple(entity_raths),
            evidence_ids=tuple(evidence),
            callooh=now,
        )

    # -- Mome operations ---------------------------------------------------

    def mome_vorpals(self) -> list[Vorpal]:
        """Show everything we noticed but couldn't attach to anyone.

        The still-walking observations. Data, not error.
        Returns all Vorpals where jabberwock_id is None.
        """
        all_vorpals = self._load_all_vorpals()
        return [v for v in all_vorpals if v.jabberwock_id is None]

    def claim_mome(
        self,
        record_id: UUID,
        jabberwock_id: UUID,
        bandersnatch: UUID | None = None,
    ) -> Vorpal:
        """Connect a mome record to an entity by creating a claim event.

        Does NOT mutate the original record. Creates a new Vorpal with
        tulgey="claim" linking the record to the entity. This is
        event sourcing: the original event persists unchanged, the
        claim is a new event that establishes the connection.
        """
        provider = bandersnatch if bandersnatch is not None else ROOT_BANDERSNATCH_ID

        return self.outgrabe(
            jabberwock_id=jabberwock_id,
            tulgey="claim",
            snicker_snack={
                "record_id": str(record_id),
                "jabberwock_id": str(jabberwock_id),
            },
            bandersnatch=provider,
        )

    # -- Group traversal ---------------------------------------------------

    def whiffling(self, borogove_id: UUID) -> list[Frabjous]:
        """Traverse: all members of a group, fully resolved.

        Finds all Rath edges where borogove_id matches, then
        materializes each member via uffish.
        """
        all_raths = self._load_all_raths()
        member_ids: list[UUID] = []
        seen: set[UUID] = set()

        for rath in all_raths:
            if rath.borogove_id == borogove_id and rath.jabberwock_id not in seen:
                member_ids.append(rath.jabberwock_id)
                seen.add(rath.jabberwock_id)

        results: list[Frabjous] = []
        for member_id in member_ids:
            try:
                results.append(self.uffish(member_id))
            except NotFoundError:
                # Member entity was referenced but not found.
                # Possible if the entity was declared in a different
                # store or hasn't been created yet. Skip silently --
                # the Rath still exists as evidence.
                pass

        return results

    # -- Rath creation (group membership) ----------------------------------

    def add_rath(
        self,
        jabberwock_id: UUID,
        borogove_id: UUID,
        mimsy: str,
        gyre_from: datetime | None = None,
        gyre_to: datetime | None = None,
        bandersnatch: UUID | None = None,
    ) -> Rath:
        """Add a membership edge: entity belongs to group with role.

        gyre_from defaults to now if not specified.
        bandersnatch defaults to ROOT_BANDERSNATCH_ID if not specified.
        """
        provider = bandersnatch if bandersnatch is not None else ROOT_BANDERSNATCH_ID
        now = datetime.now(timezone.utc)

        rath = Rath(
            jabberwock_id=jabberwock_id,
            borogove_id=borogove_id,
            mimsy=mimsy,
            gyre_from=gyre_from if gyre_from is not None else now,
            gyre_to=gyre_to,
            bandersnatch=provider,
            brillig=now,
        )
        self._store_rath(rath)
        return rath

    # -- Internal storage helpers ------------------------------------------

    def _store_jabberwock(self, jabberwock: Jabberwock) -> None:
        """Store a Jabberwock entity as a FactRecord."""
        fact = FactRecord(
            provider_id=JABBERWOCK_PROVIDER,
            timestamp=jabberwock.brillig,
            data=jabberwock.model_dump(mode="json"),
        )
        self._store.store_fact(fact)

    def _store_tove(self, tove: Tove) -> None:
        """Store a Tove alias as a FactRecord."""
        fact = FactRecord(
            provider_id=TOVE_PROVIDER,
            timestamp=tove.brillig,
            data=tove.model_dump(mode="json"),
        )
        self._store.store_fact(fact)

    def _store_vorpal(self, vorpal: Vorpal) -> None:
        """Store a Vorpal observation as a FactRecord."""
        fact = FactRecord(
            provider_id=VORPAL_PROVIDER,
            timestamp=vorpal.brillig,
            data=vorpal.model_dump(mode="json"),
        )
        self._store.store_fact(fact)

    def _store_rath(self, rath: Rath) -> None:
        """Store a Rath membership edge as a FactRecord."""
        fact = FactRecord(
            provider_id=RATH_PROVIDER,
            timestamp=rath.brillig,
            data=rath.model_dump(mode="json"),
        )
        self._store.store_fact(fact)

    # -- Internal query helpers --------------------------------------------

    @staticmethod
    def _deserialize_jabberwock(data: dict) -> dict:
        """Prepare raw fact data for Jabberwock construction.

        FactRecord.data stores UUIDs as strings and datetimes as
        ISO 8601 strings. Pydantic handles the conversion, but we
        need to pass the dict through.
        """
        return data

    def _load_jabberwock(self, jabberwock_id: UUID) -> Jabberwock:
        """Load a Jabberwock entity by its ID.

        Scans all Jabberwock facts. Raises NotFoundError if not found.
        """
        facts = self._store.query_range(provider_id=JABBERWOCK_PROVIDER)
        for fact in facts:
            if str(fact.data.get("id")) == str(jabberwock_id):
                return Jabberwock.model_validate(fact.data)

        raise NotFoundError(
            f"Jabberwock {jabberwock_id} not found."
        )

    def _load_all_toves(self) -> list[Tove]:
        """Load all Tove records from the store."""
        facts = self._store.query_range(provider_id=TOVE_PROVIDER)
        return [Tove.model_validate(fact.data) for fact in facts]

    def _load_all_vorpals(self) -> list[Vorpal]:
        """Load all Vorpal records from the store."""
        facts = self._store.query_range(provider_id=VORPAL_PROVIDER)
        return [Vorpal.model_validate(fact.data) for fact in facts]

    def _load_all_raths(self) -> list[Rath]:
        """Load all Rath records from the store."""
        facts = self._store.query_range(provider_id=RATH_PROVIDER)
        return [Rath.model_validate(fact.data) for fact in facts]
