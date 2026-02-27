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

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

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

# Provider UUID lookup by model class. Keeps _store_record and
# _load_all generic without per-type helper methods.
_PROVIDER_FOR: dict[type[BaseModel], UUID] = {
    Jabberwock: JABBERWOCK_PROVIDER,
    Tove: TOVE_PROVIDER,
    Vorpal: VORPAL_PROVIDER,
    Rath: RATH_PROVIDER,
}


def _provider_or_root(bandersnatch: UUID | None) -> UUID:
    """Default to ROOT_BANDERSNATCH_ID when no provider is given."""
    return bandersnatch if bandersnatch is not None else ROOT_BANDERSNATCH_ID


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
        for fact in self._store.query_range(provider_id=JABBERWOCK_PROVIDER):
            if fact.data.get("id") == str(ROOT_BANDERSNATCH_ID):
                try:
                    return Jabberwock.model_validate(fact.data)
                except ValidationError as e:
                    logger.warning(
                        "Root bandersnatch exists but fails validation: %s (raw: %s)",
                        e, fact.data,
                    )
                    # Fall through to create a fresh root
                    break

        now = datetime.now(timezone.utc)

        # 1. Root Jabberwock
        root = Jabberwock(
            id=ROOT_BANDERSNATCH_ID,
            brillig=now,
            bandersnatch=ROOT_BANDERSNATCH_ID,
        )
        self._store_record(root)

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
        now = datetime.now(timezone.utc)
        entity = Jabberwock(
            brillig=now,
            bandersnatch=_provider_or_root(bandersnatch),
        )
        self._store_record(entity)
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
        now = datetime.now(timezone.utc)
        vorpal = Vorpal(
            jabberwock_id=jabberwock_id,
            tulgey=tulgey,
            snicker_snack=snicker_snack,
            bandersnatch=_provider_or_root(bandersnatch),
            brillig=now,
        )
        self._store_record(vorpal)
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
        now = datetime.now(timezone.utc)
        tove = Tove(
            jabberwock_id=jabberwock_id,
            wabe=wabe,
            gimble=normalize_gimble(wabe, gimble),
            gyre_from=gyre_from if gyre_from is not None else now,
            gyre_to=gyre_to,
            bandersnatch=_provider_or_root(bandersnatch),
            brillig=now,
        )
        self._store_record(tove)
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
        canonical = normalize_gimble(wabe, gimble)

        matching = [
            t for t in self._load_all(Tove)
            if t.wabe == wabe and t.gimble == canonical
        ]

        if not matching:
            return MomeResult()

        # Collect distinct jabberwock_ids (excluding None/mome)
        resolved_ids = {t.jabberwock_id for t in matching if t.jabberwock_id is not None}

        if not resolved_ids:
            return MomeResult(
                toves=tuple(matching),
                mome_vorpals=tuple(self.mome_vorpals()),
            )

        if len(resolved_ids) == 1:
            return self.uffish(next(iter(resolved_ids)))

        # Multiple candidates
        candidates = []
        for jid in resolved_ids:
            try:
                candidates.append(self._load_jabberwock(jid))
            except NotFoundError:
                pass

        return MomeResult(
            toves=tuple(matching),
            candidates=tuple(candidates),
        )

    def uffish(self, jabberwock_id: UUID) -> Frabjous:
        """Materialize: entity UUID -> full view from all observations.

        Queries all Toves, Vorpals, and Raths for the given entity,
        folds them into a Frabjous. Raises NotFoundError if the
        Jabberwock entity doesn't exist.

        Claim Vorpals (tulgey="claim") are structural linking events,
        not observations about the entity. They are excluded from the
        vorpals tuple but their IDs are kept in evidence_ids (proof
        envelope). The count of excluded claims is tracked in
        excluded_count.

        All collections are sorted by brillig descending (newest first)
        so consumers can take the first observation of a given tulgey
        as the most recent without inspecting timestamps.
        """
        jabberwock = self._load_jabberwock(jabberwock_id)

        entity_toves = [t for t in self._load_all(Tove) if t.jabberwock_id == jabberwock_id]
        all_entity_vorpals = [v for v in self._load_all(Vorpal) if v.jabberwock_id == jabberwock_id]
        entity_raths = [r for r in self._load_all(Rath) if r.jabberwock_id == jabberwock_id]

        # Separate claim events from observation vorpals
        claim_vorpals = [v for v in all_entity_vorpals if v.tulgey == "claim"]
        observation_vorpals = [v for v in all_entity_vorpals if v.tulgey != "claim"]

        # Sort by brillig descending (newest first)
        entity_toves.sort(key=lambda t: t.brillig, reverse=True)
        observation_vorpals.sort(key=lambda v: v.brillig, reverse=True)
        entity_raths.sort(key=lambda r: r.brillig, reverse=True)

        # Evidence includes ALL events (including claims -- proof envelope)
        evidence: list[UUID] = [jabberwock.id]
        evidence.extend(t.id for t in entity_toves)
        evidence.extend(v.id for v in all_entity_vorpals)
        evidence.extend(r.id for r in entity_raths)

        return Frabjous(
            jabberwock=jabberwock,
            toves=tuple(entity_toves),
            vorpals=tuple(observation_vorpals),
            raths=tuple(entity_raths),
            evidence_ids=tuple(evidence),
            excluded_count=len(claim_vorpals),
            callooh=datetime.now(timezone.utc),
        )

    # -- Mome operations ---------------------------------------------------

    def mome_vorpals(self) -> list[Vorpal]:
        """Show everything we noticed but couldn't attach to anyone.

        The still-walking observations. Data, not error.
        Returns all Vorpals where jabberwock_id is None, excluding
        any mome records that have been claimed (connected to an entity
        via a claim event).
        """
        all_vorpals = self._load_all(Vorpal)

        # Collect record_ids from claim events to exclude claimed momes
        claimed_record_ids: set[str] = set()
        for v in all_vorpals:
            if v.tulgey == "claim" and isinstance(v.snicker_snack, dict):
                rid = v.snicker_snack.get("record_id")
                if rid is not None:
                    claimed_record_ids.add(str(rid))

        return [
            v for v in all_vorpals
            if v.jabberwock_id is None and str(v.id) not in claimed_record_ids
        ]

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
        return self.outgrabe(
            jabberwock_id=jabberwock_id,
            tulgey="claim",
            snicker_snack={
                "record_id": str(record_id),
                "jabberwock_id": str(jabberwock_id),
            },
            bandersnatch=_provider_or_root(bandersnatch),
        )

    # -- Group traversal ---------------------------------------------------

    def whiffling(self, borogove_id: UUID) -> list[Frabjous]:
        """Traverse: all members of a group, fully resolved.

        Finds all Rath edges where borogove_id matches, then
        materializes each member via uffish.
        """
        seen: set[UUID] = set()
        member_ids: list[UUID] = []
        for rath in self._load_all(Rath):
            if rath.borogove_id == borogove_id and rath.jabberwock_id not in seen:
                member_ids.append(rath.jabberwock_id)
                seen.add(rath.jabberwock_id)

        results: list[Frabjous] = []
        for mid in member_ids:
            try:
                results.append(self.uffish(mid))
            except NotFoundError:
                pass  # referenced but not found -- Rath still exists as evidence

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
        now = datetime.now(timezone.utc)
        rath = Rath(
            jabberwock_id=jabberwock_id,
            borogove_id=borogove_id,
            mimsy=mimsy,
            gyre_from=gyre_from if gyre_from is not None else now,
            gyre_to=gyre_to,
            bandersnatch=_provider_or_root(bandersnatch),
            brillig=now,
        )
        self._store_record(rath)
        return rath

    # -- Internal helpers --------------------------------------------------

    def _store_record(self, record: BaseModel) -> None:
        """Store any Jabberwock record as a FactRecord.

        Looks up the provider UUID from the model's type.
        All four record types (Jabberwock, Tove, Vorpal, Rath) use
        the same pattern: serialize to JSON, wrap in FactRecord, store.
        """
        provider = _PROVIDER_FOR[type(record)]
        brillig = getattr(record, "brillig")
        self._store.store_fact(FactRecord(
            provider_id=provider,
            timestamp=brillig,
            data=record.model_dump(mode="json"),
        ))

    def _load_all[T: BaseModel](self, cls: type[T]) -> list[T]:
        """Load all records of a given type from the store.

        Historical records that fail current validation constraints are
        skipped with a warning. Event-sourced stores accumulate records
        over time; new validators must not break old data.
        """
        provider = _PROVIDER_FOR[cls]
        results: list[T] = []
        for f in self._store.query_range(provider_id=provider):
            try:
                results.append(cls.model_validate(f.data))
            except ValidationError as e:
                logger.warning(
                    "Skipping %s record %s: validation failed: %s",
                    cls.__name__, f.data.get("id", "?"), e,
                )
        return results

    def _load_jabberwock(self, jabberwock_id: UUID) -> Jabberwock:
        """Load a Jabberwock entity by its ID.

        Scans all Jabberwock facts. Raises NotFoundError if not found
        or if the record exists but fails current validation.
        """
        for fact in self._store.query_range(provider_id=JABBERWOCK_PROVIDER):
            if str(fact.data.get("id")) == str(jabberwock_id):
                try:
                    return Jabberwock.model_validate(fact.data)
                except ValidationError as e:
                    logger.warning(
                        "Jabberwock %s exists but fails validation: %s (raw: %s)",
                        jabberwock_id, e, fact.data,
                    )
                    raise NotFoundError(
                        f"Jabberwock {jabberwock_id} exists in store but "
                        f"fails current validation: {e}"
                    ) from e

        raise NotFoundError(f"Jabberwock {jabberwock_id} not found.")
