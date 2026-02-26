"""Unit tests for the Brillig resolution service.

Uses InMemoryActivityStreamStore as the backend. Tests cover:
- Bootstrap (root Jabberwock, species Vorpal, system Tove)
- Bootstrap idempotence
- Entity creation (beamish)
- Observation recording (outgrabe)
- Alias creation (slithy)
- Resolution (galumph) -- resolved, mome, and no-match cases
- Materialization (uffish) -- including NotFoundError
- Mome lifecycle: create mome -> claim_mome -> verify unchanged
- Group traversal (whiffling, add_rath)
- Provenance closure
- Namespace normalization in galumph
- Temporal consistency (gyre_to before gyre_from)
- Event sourcing (outgrabe twice = two events)
- brillig vs gyre independence
- Frabjous proof envelope

Test author: separate from builder (CI enforces separation).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.apacheta.interface.errors import NotFoundError
from yanantin.jabberwock.brillig import Brillig
from yanantin.jabberwock.models import (
    JABBERWOCK_PROVIDER,
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


NOW = datetime.now(timezone.utc)
LAST_YEAR = NOW - timedelta(days=365)
LAST_MONTH = NOW - timedelta(days=30)
YESTERDAY = NOW - timedelta(days=1)
TOMORROW = NOW + timedelta(days=1)


# -- Fixtures --------------------------------------------------------------


@pytest.fixture
def store() -> InMemoryActivityStreamStore:
    return InMemoryActivityStreamStore()


@pytest.fixture
def brillig(store: InMemoryActivityStreamStore) -> Brillig:
    return Brillig(store)


@pytest.fixture
def bootstrapped(store: InMemoryActivityStreamStore) -> Brillig:
    """Brillig service with bootstrap already called."""
    b = Brillig(store)
    b.bootstrap()
    return b


# -- Bootstrap -------------------------------------------------------------


class TestBootstrap:
    def test_bootstrap_creates_root_jabberwock(self, brillig: Brillig):
        root = brillig.bootstrap()
        assert root.id == ROOT_BANDERSNATCH_ID
        assert root.bandersnatch == ROOT_BANDERSNATCH_ID, (
            "Root is self-referential: bandersnatch == id"
        )

    def test_bootstrap_creates_species_vorpal(self, brillig: Brillig):
        brillig.bootstrap()
        # Resolve root via uffish -- should have a species vorpal
        view = brillig.uffish(ROOT_BANDERSNATCH_ID)
        species_vorpals = [v for v in view.vorpals if v.tulgey == "species"]
        assert len(species_vorpals) == 1
        assert species_vorpals[0].snicker_snack == "system"

    def test_bootstrap_creates_system_tove(self, brillig: Brillig):
        brillig.bootstrap()
        view = brillig.uffish(ROOT_BANDERSNATCH_ID)
        system_toves = [t for t in view.toves if t.wabe == "system"]
        assert len(system_toves) == 1
        assert system_toves[0].gimble == "root"

    def test_bootstrap_idempotent(self, brillig: Brillig):
        """Calling bootstrap() twice must not create duplicates."""
        root1 = brillig.bootstrap()
        root2 = brillig.bootstrap()
        assert root1.id == root2.id

        # Verify only one Jabberwock entity with root ID exists
        view = brillig.uffish(ROOT_BANDERSNATCH_ID)
        species_vorpals = [v for v in view.vorpals if v.tulgey == "species"]
        assert len(species_vorpals) == 1, (
            "Bootstrap called twice should not create duplicate species Vorpals"
        )


# -- Entity creation (beamish) --------------------------------------------


class TestBeamish:
    def test_beamish_creates_entity(self, bootstrapped: Brillig):
        entity = bootstrapped.beamish()
        assert isinstance(entity, Jabberwock)
        assert entity.bandersnatch == ROOT_BANDERSNATCH_ID

    def test_beamish_with_custom_bandersnatch(self, bootstrapped: Brillig):
        custom_provider = uuid4()
        entity = bootstrapped.beamish(bandersnatch=custom_provider)
        assert entity.bandersnatch == custom_provider

    def test_beamish_creates_unique_entities(self, bootstrapped: Brillig):
        e1 = bootstrapped.beamish()
        e2 = bootstrapped.beamish()
        assert e1.id != e2.id

    def test_beamish_entity_materializable(self, bootstrapped: Brillig):
        """A beamished entity can be materialized via uffish."""
        entity = bootstrapped.beamish()
        view = bootstrapped.uffish(entity.id)
        assert isinstance(view, Frabjous)
        assert view.jabberwock.id == entity.id


# -- Observation (outgrabe) ------------------------------------------------


class TestOutgrabe:
    def test_outgrabe_returns_vorpal(self, bootstrapped: Brillig):
        entity = bootstrapped.beamish()
        vorpal = bootstrapped.outgrabe(
            jabberwock_id=entity.id,
            tulgey="species",
            snicker_snack="person",
        )
        assert isinstance(vorpal, Vorpal)
        assert vorpal.jabberwock_id == entity.id
        assert vorpal.tulgey == "species"
        assert vorpal.snicker_snack == "person"

    def test_outgrabe_mome(self, bootstrapped: Brillig):
        """jabberwock_id=None creates a mome vorpal (still walking)."""
        vorpal = bootstrapped.outgrabe(
            jabberwock_id=None,
            tulgey="behavioral",
            snicker_snack="prefers tabs",
        )
        assert vorpal.jabberwock_id is None

    def test_outgrabe_visible_in_uffish(self, bootstrapped: Brillig):
        """Observations appear in the materialized view."""
        entity = bootstrapped.beamish()
        bootstrapped.outgrabe(
            jabberwock_id=entity.id,
            tulgey="teaching",
            snicker_snack="CPSC 436c",
        )
        view = bootstrapped.uffish(entity.id)
        teaching = [v for v in view.vorpals if v.tulgey == "teaching"]
        assert len(teaching) == 1
        assert teaching[0].snicker_snack == "CPSC 436c"

    def test_outgrabe_default_bandersnatch(self, bootstrapped: Brillig):
        """Default bandersnatch is ROOT_BANDERSNATCH_ID."""
        vorpal = bootstrapped.outgrabe(
            jabberwock_id=None,
            tulgey="test",
            snicker_snack="value",
        )
        assert vorpal.bandersnatch == ROOT_BANDERSNATCH_ID


# -- Alias creation (slithy) ----------------------------------------------


class TestSlithy:
    def test_slithy_creates_tove(self, bootstrapped: Brillig):
        entity = bootstrapped.beamish()
        tove = bootstrapped.slithy(
            jabberwock_id=entity.id,
            wabe="github",
            gimble="fsgeek",
        )
        assert isinstance(tove, Tove)
        assert tove.jabberwock_id == entity.id
        assert tove.wabe == "github"
        # Gimble is normalized (default: lowercase)
        assert tove.gimble == "fsgeek"

    def test_slithy_normalizes_gimble(self, bootstrapped: Brillig):
        """Gimble is normalized per wabe rules before storage."""
        entity = bootstrapped.beamish()
        tove = bootstrapped.slithy(
            jabberwock_id=entity.id,
            wabe="github",
            gimble="FsGeek",
        )
        assert tove.gimble == "fsgeek"

    def test_slithy_mome(self, bootstrapped: Brillig):
        """jabberwock_id=None creates a mome tove."""
        tove = bootstrapped.slithy(
            jabberwock_id=None,
            wabe="github",
            gimble="unknown_user",
        )
        assert tove.jabberwock_id is None

    def test_slithy_with_gyre_bounds(self, bootstrapped: Brillig):
        entity = bootstrapped.beamish()
        tove = bootstrapped.slithy(
            jabberwock_id=entity.id,
            wabe="canvas",
            gimble="592760",
            gyre_from=LAST_MONTH,
            gyre_to=TOMORROW,
        )
        assert tove.gyre_from <= tove.gyre_to  # type: ignore[operator]

    def test_slithy_default_bandersnatch(self, bootstrapped: Brillig):
        tove = bootstrapped.slithy(
            jabberwock_id=None,
            wabe="test",
            gimble="test",
        )
        assert tove.bandersnatch == ROOT_BANDERSNATCH_ID


# -- Resolution (galumph) -------------------------------------------------


class TestGalumph:
    def test_galumph_resolved(self, bootstrapped: Brillig):
        """galumph returns Frabjous when alias resolves to a single entity."""
        entity = bootstrapped.beamish()
        bootstrapped.slithy(
            jabberwock_id=entity.id,
            wabe="github",
            gimble="fsgeek",
        )
        result = bootstrapped.galumph("github", "fsgeek")
        assert isinstance(result, Frabjous)
        assert result.jabberwock.id == entity.id

    def test_galumph_no_match(self, bootstrapped: Brillig):
        """galumph returns empty MomeResult when no alias exists."""
        result = bootstrapped.galumph("github", "nonexistent")
        assert isinstance(result, MomeResult)
        assert result.toves == ()

    def test_galumph_mome_tove(self, bootstrapped: Brillig):
        """galumph returns MomeResult when alias exists but is mome."""
        bootstrapped.slithy(
            jabberwock_id=None,
            wabe="github",
            gimble="mystery_user",
        )
        result = bootstrapped.galumph("github", "mystery_user")
        assert isinstance(result, MomeResult)
        assert len(result.toves) >= 1

    def test_galumph_namespace_normalization(self, bootstrapped: Brillig):
        """'FsGeek' and 'fsgeek' resolve to the same entity."""
        entity = bootstrapped.beamish()
        bootstrapped.slithy(
            jabberwock_id=entity.id,
            wabe="github",
            gimble="fsgeek",
        )
        # Query with different case
        result = bootstrapped.galumph("github", "FsGeek")
        assert isinstance(result, Frabjous)
        assert result.jabberwock.id == entity.id

    def test_galumph_case_variant_resolution(self, bootstrapped: Brillig):
        """Mixed case variants all resolve to the same entity."""
        entity = bootstrapped.beamish()
        bootstrapped.slithy(
            jabberwock_id=entity.id,
            wabe="github",
            gimble="fsgeek",
        )
        for variant in ("FSGEEK", "FsGeek", "fsGeek", "fsgeek"):
            result = bootstrapped.galumph("github", variant)
            assert isinstance(result, Frabjous), f"Failed for variant: {variant}"
            assert result.jabberwock.id == entity.id


# -- Materialization (uffish) ----------------------------------------------


class TestUffish:
    def test_uffish_returns_frabjous(self, bootstrapped: Brillig):
        entity = bootstrapped.beamish()
        view = bootstrapped.uffish(entity.id)
        assert isinstance(view, Frabjous)
        assert view.jabberwock.id == entity.id

    def test_uffish_not_found(self, bootstrapped: Brillig):
        """uffish raises NotFoundError for unknown UUID."""
        with pytest.raises(NotFoundError):
            bootstrapped.uffish(uuid4())

    def test_uffish_includes_all_observations(self, bootstrapped: Brillig):
        entity = bootstrapped.beamish()
        bootstrapped.outgrabe(entity.id, "species", "person")
        bootstrapped.outgrabe(entity.id, "teaching", "CPSC 436c")
        bootstrapped.slithy(entity.id, "github", "fsgeek")
        bootstrapped.slithy(entity.id, "canvas", "592760")

        view = bootstrapped.uffish(entity.id)
        assert len(view.vorpals) == 2
        assert len(view.toves) == 2

    def test_uffish_callooh_is_utc(self, bootstrapped: Brillig):
        entity = bootstrapped.beamish()
        view = bootstrapped.uffish(entity.id)
        assert view.callooh.tzinfo is not None


# -- Mome operations -------------------------------------------------------


class TestMomeVorpals:
    def test_mome_vorpals_returns_unresolved(self, bootstrapped: Brillig):
        bootstrapped.outgrabe(None, "behavioral", "prefers bun")
        bootstrapped.outgrabe(None, "behavioral", "uses vim")
        momes = bootstrapped.mome_vorpals()
        assert len(momes) >= 2
        for m in momes:
            assert m.jabberwock_id is None

    def test_mome_vorpals_excludes_resolved(self, bootstrapped: Brillig):
        entity = bootstrapped.beamish()
        bootstrapped.outgrabe(entity.id, "species", "person")
        bootstrapped.outgrabe(None, "behavioral", "unresolved")
        momes = bootstrapped.mome_vorpals()
        # Only the unresolved one should appear (plus any from bootstrap)
        mome_tulgeys = [m.tulgey for m in momes]
        assert "behavioral" in mome_tulgeys
        assert "species" not in mome_tulgeys


class TestClaimMome:
    def test_claim_mome_creates_claim_event(self, bootstrapped: Brillig):
        """claim_mome creates a new Vorpal with tulgey='claim'."""
        mome_vorpal = bootstrapped.outgrabe(None, "behavioral", "prefers tabs")
        entity = bootstrapped.beamish()

        claim = bootstrapped.claim_mome(mome_vorpal.id, entity.id)
        assert isinstance(claim, Vorpal)
        assert claim.tulgey == "claim"
        assert claim.jabberwock_id == entity.id
        assert claim.snicker_snack["record_id"] == str(mome_vorpal.id)

    def test_claim_mome_does_not_mutate_original(self, bootstrapped: Brillig):
        """The original mome vorpal must remain unchanged after claim."""
        mome_vorpal = bootstrapped.outgrabe(None, "behavioral", "prefers tabs")
        original_id = mome_vorpal.id
        entity = bootstrapped.beamish()

        bootstrapped.claim_mome(mome_vorpal.id, entity.id)

        # The original mome should still be in the mome list
        momes = bootstrapped.mome_vorpals()
        original_still_mome = [m for m in momes if m.id == original_id]
        assert len(original_still_mome) == 1, (
            "Original mome vorpal must remain unchanged after claim_mome"
        )
        assert original_still_mome[0].jabberwock_id is None

    def test_mome_lifecycle(self, bootstrapped: Brillig):
        """Full lifecycle: create mome -> claim -> verify both exist."""
        # 1. Create a mome observation
        mome = bootstrapped.outgrabe(None, "behavioral", "uses emacs")
        assert mome.jabberwock_id is None

        # 2. Create an entity to claim it
        entity = bootstrapped.beamish()

        # 3. Claim the mome
        claim = bootstrapped.claim_mome(mome.id, entity.id)

        # 4. Verify: original mome still exists and is still mome
        momes = bootstrapped.mome_vorpals()
        original_ids = {m.id for m in momes}
        assert mome.id in original_ids

        # 5. Verify: claim event exists in entity's view
        view = bootstrapped.uffish(entity.id)
        claim_vorpals = [v for v in view.vorpals if v.tulgey == "claim"]
        assert len(claim_vorpals) == 1
        assert claim_vorpals[0].id == claim.id


# -- Group traversal (whiffling, add_rath) ---------------------------------


class TestAddRath:
    def test_add_rath_creates_membership(self, bootstrapped: Brillig):
        member = bootstrapped.beamish()
        group = bootstrapped.beamish()
        rath = bootstrapped.add_rath(
            jabberwock_id=member.id,
            borogove_id=group.id,
            mimsy="student",
        )
        assert isinstance(rath, Rath)
        assert rath.jabberwock_id == member.id
        assert rath.borogove_id == group.id
        assert rath.mimsy == "student"

    def test_add_rath_visible_in_uffish(self, bootstrapped: Brillig):
        member = bootstrapped.beamish()
        group = bootstrapped.beamish()
        bootstrapped.add_rath(member.id, group.id, "student")
        view = bootstrapped.uffish(member.id)
        assert len(view.raths) == 1
        assert view.raths[0].borogove_id == group.id


class TestWhiffling:
    def test_whiffling_returns_members(self, bootstrapped: Brillig):
        group = bootstrapped.beamish()
        m1 = bootstrapped.beamish()
        m2 = bootstrapped.beamish()
        bootstrapped.add_rath(m1.id, group.id, "student")
        bootstrapped.add_rath(m2.id, group.id, "ta")

        members = bootstrapped.whiffling(group.id)
        assert len(members) == 2
        member_ids = {f.jabberwock.id for f in members}
        assert m1.id in member_ids
        assert m2.id in member_ids

    def test_whiffling_empty_group(self, bootstrapped: Brillig):
        group = bootstrapped.beamish()
        members = bootstrapped.whiffling(group.id)
        assert members == []

    def test_whiffling_returns_frabjous_objects(self, bootstrapped: Brillig):
        group = bootstrapped.beamish()
        member = bootstrapped.beamish()
        bootstrapped.add_rath(member.id, group.id, "reviewer")
        members = bootstrapped.whiffling(group.id)
        assert all(isinstance(m, Frabjous) for m in members)

    def test_whiffling_deduplicates_members(self, bootstrapped: Brillig):
        """If same member has multiple roles, they appear once in traversal."""
        group = bootstrapped.beamish()
        member = bootstrapped.beamish()
        bootstrapped.add_rath(member.id, group.id, "student")
        bootstrapped.add_rath(member.id, group.id, "reviewer")
        members = bootstrapped.whiffling(group.id)
        assert len(members) == 1


# -- Provenance closure ----------------------------------------------------


class TestProvenanceClosure:
    def test_every_bandersnatch_resolves(self, bootstrapped: Brillig):
        """After bootstrap, every bandersnatch resolves to a Jabberwock."""
        entity = bootstrapped.beamish()
        view = bootstrapped.uffish(entity.id)
        # The entity's bandersnatch should be resolvable
        provider_view = bootstrapped.uffish(view.jabberwock.bandersnatch)
        assert isinstance(provider_view, Frabjous)

    def test_root_bandersnatch_self_referential(self, bootstrapped: Brillig):
        root_view = bootstrapped.uffish(ROOT_BANDERSNATCH_ID)
        assert root_view.jabberwock.bandersnatch == root_view.jabberwock.id


# -- Temporal consistency --------------------------------------------------


class TestTemporalConsistency:
    def test_slithy_gyre_to_before_gyre_from_raises(self, bootstrapped: Brillig):
        """gyre_to < gyre_from in slithy must raise ValueError."""
        entity = bootstrapped.beamish()
        with pytest.raises(Exception, match="gyre_to.*cannot precede"):
            bootstrapped.slithy(
                jabberwock_id=entity.id,
                wabe="test",
                gimble="test",
                gyre_from=TOMORROW,
                gyre_to=YESTERDAY,
            )

    def test_add_rath_gyre_to_before_gyre_from_raises(self, bootstrapped: Brillig):
        """gyre_to < gyre_from in add_rath must raise ValueError."""
        member = bootstrapped.beamish()
        group = bootstrapped.beamish()
        with pytest.raises(Exception, match="gyre_to.*cannot precede"):
            bootstrapped.add_rath(
                jabberwock_id=member.id,
                borogove_id=group.id,
                mimsy="student",
                gyre_from=TOMORROW,
                gyre_to=YESTERDAY,
            )


# -- Event sourcing --------------------------------------------------------


class TestEventSourcing:
    def test_outgrabe_not_deduped(self, bootstrapped: Brillig):
        """Calling outgrabe twice with same params creates TWO events."""
        entity = bootstrapped.beamish()
        v1 = bootstrapped.outgrabe(entity.id, "species", "person")
        v2 = bootstrapped.outgrabe(entity.id, "species", "person")
        assert v1.id != v2.id, "Event-sourced: each call is a new event"

        view = bootstrapped.uffish(entity.id)
        species = [v for v in view.vorpals if v.tulgey == "species"]
        assert len(species) == 2

    def test_slithy_not_deduped(self, bootstrapped: Brillig):
        """Calling slithy twice with same params creates TWO events."""
        entity = bootstrapped.beamish()
        t1 = bootstrapped.slithy(entity.id, "github", "fsgeek")
        t2 = bootstrapped.slithy(entity.id, "github", "fsgeek")
        assert t1.id != t2.id

        view = bootstrapped.uffish(entity.id)
        github_toves = [t for t in view.toves if t.wabe == "github"]
        assert len(github_toves) == 2


# -- brillig vs gyre independence ------------------------------------------


class TestBrilligVsGyre:
    def test_observation_time_differs_from_validity(self, bootstrapped: Brillig):
        """brillig (observation time) and gyre (asserted validity) are independent.

        You can observe today that Tony was a student last semester.
        brillig=today, gyre_from=last September.
        """
        entity = bootstrapped.beamish()
        tove = bootstrapped.slithy(
            jabberwock_id=entity.id,
            wabe="canvas",
            gimble="592760",
            gyre_from=LAST_YEAR,
            gyre_to=LAST_MONTH,
        )
        # brillig (observation time) should be ~now
        # gyre_from/gyre_to are in the past
        assert tove.brillig > tove.gyre_to  # type: ignore[operator]
        assert tove.gyre_from < tove.brillig

    def test_rath_observation_differs_from_membership(self, bootstrapped: Brillig):
        """add_rath: brillig and gyre_from can differ."""
        member = bootstrapped.beamish()
        group = bootstrapped.beamish()
        rath = bootstrapped.add_rath(
            jabberwock_id=member.id,
            borogove_id=group.id,
            mimsy="student",
            gyre_from=LAST_YEAR,
        )
        # brillig is ~now, gyre_from is last year
        assert rath.brillig > rath.gyre_from


# -- Frabjous proof envelope -----------------------------------------------


class TestFrabjousProofEnvelope:
    def test_evidence_ids_contains_all_records(self, bootstrapped: Brillig):
        """evidence_ids must contain IDs of all contributing events."""
        entity = bootstrapped.beamish()
        v = bootstrapped.outgrabe(entity.id, "species", "person")
        t = bootstrapped.slithy(entity.id, "github", "fsgeek")

        view = bootstrapped.uffish(entity.id)
        evidence = set(view.evidence_ids)

        assert entity.id in evidence, "Jabberwock ID should be in evidence"
        assert v.id in evidence, "Vorpal ID should be in evidence"
        assert t.id in evidence, "Tove ID should be in evidence"

    def test_evidence_ids_includes_raths(self, bootstrapped: Brillig):
        entity = bootstrapped.beamish()
        group = bootstrapped.beamish()
        r = bootstrapped.add_rath(entity.id, group.id, "student")

        view = bootstrapped.uffish(entity.id)
        evidence = set(view.evidence_ids)
        assert r.id in evidence, "Rath ID should be in evidence"

    def test_empty_entity_has_minimal_evidence(self, bootstrapped: Brillig):
        """Entity with no observations: evidence contains only the Jabberwock ID."""
        entity = bootstrapped.beamish()
        view = bootstrapped.uffish(entity.id)
        assert len(view.evidence_ids) == 1
        assert view.evidence_ids[0] == entity.id
