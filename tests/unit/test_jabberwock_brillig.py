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
        """The original mome vorpal record is unchanged, but excluded from mome_vorpals().

        Event sourcing: the original record persists with jabberwock_id=None.
        But mome_vorpals() now filters claimed records -- a claimed mome is
        no longer "still walking." The record is immutable; the view is not.
        """
        mome_vorpal = bootstrapped.outgrabe(None, "behavioral", "prefers tabs")
        original_id = mome_vorpal.id
        entity = bootstrapped.beamish()

        bootstrapped.claim_mome(mome_vorpal.id, entity.id)

        # The claimed mome should NOT appear in the unresolved list
        momes = bootstrapped.mome_vorpals()
        mome_ids = {m.id for m in momes}
        assert original_id not in mome_ids, (
            "Claimed mome must be excluded from mome_vorpals() -- "
            "it is no longer unresolved"
        )

    def test_mome_lifecycle(self, bootstrapped: Brillig):
        """Full lifecycle: create mome -> claim -> mome disappears from unresolved.

        After claim, three things are true:
        1. The mome is excluded from mome_vorpals() (no longer unresolved).
        2. The claim event is in evidence_ids (proof envelope).
        3. The claim event is NOT in vorpals (structural, not observation).
        """
        # 1. Create a mome observation
        mome = bootstrapped.outgrabe(None, "behavioral", "uses emacs")
        assert mome.jabberwock_id is None

        # 2. Create an entity to claim it
        entity = bootstrapped.beamish()

        # 3. Claim the mome
        claim = bootstrapped.claim_mome(mome.id, entity.id)

        # 4. Verify: claimed mome is excluded from the unresolved list
        momes = bootstrapped.mome_vorpals()
        mome_ids = {m.id for m in momes}
        assert mome.id not in mome_ids, (
            "Claimed mome must not appear in mome_vorpals()"
        )

        # 5. Verify: claim event is in evidence but NOT in vorpals
        view = bootstrapped.uffish(entity.id)
        assert claim.id in set(view.evidence_ids), (
            "Claim event must be in evidence_ids (proof envelope)"
        )
        claim_in_vorpals = [v for v in view.vorpals if v.tulgey == "claim"]
        assert len(claim_in_vorpals) == 0, (
            "Claim events must be filtered from vorpals tuple"
        )


class TestMomeVorpalsExclusion:
    """Tests that mome_vorpals() correctly excludes claimed records."""

    def test_mome_vorpals_excludes_claimed(self, bootstrapped: Brillig):
        """After claim_mome, the mome Vorpal must not appear in mome_vorpals()."""
        mome = bootstrapped.outgrabe(None, "behavioral", "loves cats")
        entity = bootstrapped.beamish()

        # Before claim: mome is in the unresolved list
        momes_before = bootstrapped.mome_vorpals()
        assert mome.id in {m.id for m in momes_before}

        # Claim it
        bootstrapped.claim_mome(mome.id, entity.id)

        # After claim: mome is excluded
        momes_after = bootstrapped.mome_vorpals()
        assert mome.id not in {m.id for m in momes_after}, (
            "Claimed mome must be excluded from mome_vorpals()"
        )

    def test_mome_vorpals_still_returns_unclaimed(self, bootstrapped: Brillig):
        """Unclaimed momes must still appear after a different mome is claimed.

        Regression guard: claiming one mome must not suppress others.
        """
        mome_a = bootstrapped.outgrabe(None, "behavioral", "prefers spaces")
        mome_b = bootstrapped.outgrabe(None, "behavioral", "prefers tabs")
        entity = bootstrapped.beamish()

        # Claim only mome_a
        bootstrapped.claim_mome(mome_a.id, entity.id)

        momes = bootstrapped.mome_vorpals()
        mome_ids = {m.id for m in momes}
        assert mome_a.id not in mome_ids, "Claimed mome_a must be excluded"
        assert mome_b.id in mome_ids, "Unclaimed mome_b must still appear"


class TestUffishClaimFiltering:
    """Tests that uffish() filters claim Vorpals from the vorpals tuple."""

    def test_uffish_excludes_claim_vorpals(self, bootstrapped: Brillig):
        """Claim Vorpals (tulgey='claim') must NOT appear in Frabjous.vorpals."""
        mome = bootstrapped.outgrabe(None, "behavioral", "night owl")
        entity = bootstrapped.beamish()
        bootstrapped.claim_mome(mome.id, entity.id)

        view = bootstrapped.uffish(entity.id)
        claim_in_vorpals = [v for v in view.vorpals if v.tulgey == "claim"]
        assert len(claim_in_vorpals) == 0, (
            "Claim events are structural, not observations -- "
            "they must not appear in vorpals"
        )

    def test_uffish_claim_in_evidence_ids(self, bootstrapped: Brillig):
        """Claim events must be in evidence_ids (proof envelope)."""
        mome = bootstrapped.outgrabe(None, "behavioral", "morning person")
        entity = bootstrapped.beamish()
        claim = bootstrapped.claim_mome(mome.id, entity.id)

        view = bootstrapped.uffish(entity.id)
        assert claim.id in set(view.evidence_ids), (
            "Claim event ID must be in evidence_ids for provenance"
        )

    def test_uffish_excluded_count_tracks_claims(self, bootstrapped: Brillig):
        """excluded_count must reflect the number of filtered claim events."""
        entity = bootstrapped.beamish()

        # No claims yet
        view_before = bootstrapped.uffish(entity.id)
        assert view_before.excluded_count == 0

        # Create two momes and claim them both to this entity
        mome_a = bootstrapped.outgrabe(None, "behavioral", "uses dvorak")
        mome_b = bootstrapped.outgrabe(None, "behavioral", "uses qwerty")
        bootstrapped.claim_mome(mome_a.id, entity.id)
        bootstrapped.claim_mome(mome_b.id, entity.id)

        view_after = bootstrapped.uffish(entity.id)
        assert view_after.excluded_count == 2, (
            "Two claim events were created -- excluded_count must be 2"
        )


class TestFrabjousSortOrder:
    """Tests that Frabjous collections are sorted by brillig descending."""

    def test_vorpals_sorted_newest_first(self, bootstrapped: Brillig):
        """Frabjous.vorpals must be sorted by brillig descending (newest first)."""
        import time

        entity = bootstrapped.beamish()
        # Create observations with small delays to ensure distinct timestamps
        bootstrapped.outgrabe(entity.id, "species", "person")
        time.sleep(0.01)
        bootstrapped.outgrabe(entity.id, "teaching", "CPSC 436c")
        time.sleep(0.01)
        bootstrapped.outgrabe(entity.id, "office", "ICICS 389")

        view = bootstrapped.uffish(entity.id)
        assert len(view.vorpals) == 3

        # Verify descending order by brillig
        timestamps = [v.brillig for v in view.vorpals]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1], (
                f"vorpals[{i}].brillig ({timestamps[i]}) must be >= "
                f"vorpals[{i + 1}].brillig ({timestamps[i + 1]})"
            )

    def test_toves_sorted_newest_first(self, bootstrapped: Brillig):
        """Frabjous.toves must be sorted by brillig descending (newest first)."""
        import time

        entity = bootstrapped.beamish()
        bootstrapped.slithy(entity.id, "github", "fsgeek")
        time.sleep(0.01)
        bootstrapped.slithy(entity.id, "canvas", "592760")
        time.sleep(0.01)
        bootstrapped.slithy(entity.id, "email", "tony@example.com")

        view = bootstrapped.uffish(entity.id)
        assert len(view.toves) == 3

        timestamps = [t.brillig for t in view.toves]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1], (
                f"toves[{i}].brillig ({timestamps[i]}) must be >= "
                f"toves[{i + 1}].brillig ({timestamps[i + 1]})"
            )


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


class TestWorldTimeAndImport:
    """gh #41 (Vorpal world time through the public API) and gh #42 (backfill)."""

    def test_outgrabe_carries_world_time_into_the_view(self, bootstrapped):
        entity = bootstrapped.beamish()
        may8 = datetime(2026, 5, 8, tzinfo=timezone.utc)
        v = bootstrapped.outgrabe(entity.id, "state_tokens", 55389, gyre_from=may8, gyre_to=may8)
        assert v.brillig > may8  # recorded now, true then
        [seen] = bootstrapped.uffish(entity.id).vorpals
        assert (seen.gyre_from, seen.gyre_to) == (may8, may8)

    def test_import_record_keeps_its_own_id_and_event_time(self, bootstrapped):
        entity = bootstrapped.beamish()
        then = datetime(2025, 1, 2, 3, 4, tzinfo=timezone.utc)
        record = Vorpal(id=uuid4(), jabberwock_id=entity.id, tulgey="edition",
                        snicker_snack="1997", bandersnatch=entity.id, brillig=then)
        bootstrapped.import_record(record)
        [seen] = bootstrapped.uffish(entity.id).vorpals
        assert (seen.id, seen.brillig) == (record.id, then)

    def test_import_record_refuses_non_jabberwock_records(self, bootstrapped):
        with pytest.raises(TypeError):
            bootstrapped.import_record(object())


class TestAtWorldTime:
    """gh #41 follow-up, specified by levadura: views at a world time, never by default.

    Valid at t means gyre_from <= t < gyre_to; a missing side is unbounded; a record
    with no gyre is valid at every t. at=None filters nothing.
    """

    Y1997 = datetime(1997, 1, 1, tzinfo=timezone.utc)
    Y2010 = datetime(2010, 1, 1, tzinfo=timezone.utc)
    Y2025 = datetime(2025, 1, 1, tzinfo=timezone.utc)

    def test_galumph_resolves_what_the_name_meant_then(self, bootstrapped):
        old, new = bootstrapped.beamish(), bootstrapped.beamish()
        bootstrapped.slithy(old.id, "cfr.12.202", "the act", gyre_from=self.Y1997, gyre_to=self.Y2010)
        bootstrapped.slithy(new.id, "cfr.12.202", "the act", gyre_from=self.Y2010)
        assert bootstrapped.galumph("cfr.12.202", "the act", at=self.Y1997).jabberwock.id == old.id
        assert bootstrapped.galumph("cfr.12.202", "the act", at=self.Y2010).jabberwock.id == new.id  # half-open
        assert bootstrapped.galumph("cfr.12.202", "the act", at=self.Y2025).jabberwock.id == new.id
        assert len(bootstrapped.galumph("cfr.12.202", "the act").candidates) == 2  # at=None: no filtering

    def test_two_valid_at_t_is_ambiguous_not_a_pick(self, bootstrapped):
        a, b = bootstrapped.beamish(), bootstrapped.beamish()
        bootstrapped.slithy(a.id, "w", "x", gyre_from=self.Y1997)
        bootstrapped.slithy(b.id, "w", "x", gyre_from=self.Y2010)
        assert len(bootstrapped.galumph("w", "x", at=self.Y2025).candidates) == 2

    def test_uffish_at_filters_and_counts_what_it_left_out(self, bootstrapped):
        e = bootstrapped.beamish()
        bootstrapped.outgrabe(e.id, "tokens", 1, gyre_from=self.Y1997, gyre_to=self.Y2010)
        bootstrapped.outgrabe(e.id, "tokens", 2, gyre_from=self.Y2010)
        bootstrapped.outgrabe(e.id, "species", "act")  # no gyre: valid at every t
        then = bootstrapped.uffish(e.id, at=self.Y1997)
        assert sorted(str(v.snicker_snack) for v in then.vorpals) == ["1", "act"]
        assert then.excluded_count == 1
        assert len(bootstrapped.uffish(e.id).vorpals) == 3

    def test_unbounded_sides(self, bootstrapped):
        e = bootstrapped.beamish()
        bootstrapped.outgrabe(e.id, "until", "x", gyre_to=self.Y2010)
        assert len(bootstrapped.uffish(e.id, at=self.Y1997).vorpals) == 1
        assert len(bootstrapped.uffish(e.id, at=self.Y2025).vorpals) == 0

    def test_naive_at_rejected(self, bootstrapped):
        e = bootstrapped.beamish()
        with pytest.raises(ValueError):
            bootstrapped.uffish(e.id, at=datetime(2025, 1, 1))

    def test_uffish_at_filters_raths_too(self, bootstrapped):
        e, ed1997 = bootstrapped.beamish(), bootstrapped.beamish()
        bootstrapped.add_rath(e.id, ed1997.id, "volume", gyre_from=self.Y1997, gyre_to=self.Y2010)
        assert len(bootstrapped.uffish(e.id, at=self.Y1997).raths) == 1
        assert len(bootstrapped.uffish(e.id, at=self.Y2025).raths) == 0

    def test_galumph_at_also_filters_the_view_it_returns(self, bootstrapped):
        e = bootstrapped.beamish()
        bootstrapped.slithy(e.id, "w", "x", gyre_from=self.Y1997)
        bootstrapped.outgrabe(e.id, "meaning", "old", gyre_from=self.Y1997, gyre_to=self.Y2010)
        bootstrapped.outgrabe(e.id, "meaning", "new", gyre_from=self.Y2010)
        view = bootstrapped.galumph("w", "x", at=self.Y1997)
        assert [v.snicker_snack for v in view.vorpals] == ["old"]

    def test_gyreless_alias_is_valid_at_every_time(self, bootstrapped):
        """gh #47: no gyre given means unbounded, not 'from when it was recorded'."""
        e = bootstrapped.beamish()
        tove = bootstrapped.slithy(e.id, "act", "federal deposit insurance act")
        assert tove.gyre_from is None
        far_past = datetime(1990, 1, 1, tzinfo=timezone.utc)
        assert bootstrapped.galumph("act", "federal deposit insurance act", at=far_past).jabberwock.id == e.id

    def test_gyreless_rath_is_valid_at_every_time(self, bootstrapped):
        e, group = bootstrapped.beamish(), bootstrapped.beamish()
        rath = bootstrapped.add_rath(e.id, group.id, "volume")
        assert rath.gyre_from is None
        assert len(bootstrapped.uffish(e.id, at=datetime(1990, 1, 1, tzinfo=timezone.utc)).raths) == 1


# -- gh #46: resolution pushes its match down to the store ----------------


class _CountingStore(InMemoryActivityStreamStore):
    """A real in-memory store that records which providers were scanned whole."""

    def __init__(self) -> None:
        super().__init__()
        self.full_scans: list = []

    def query_range(self, provider_id, start=None, end=None):
        self.full_scans.append(provider_id)
        return super().query_range(provider_id, start, end)


class TestResolutionDoesNotScan:
    """galumph/uffish/whiffling must not load every record of a type (gh #46)."""

    @pytest.fixture
    def counted(self):
        store = _CountingStore()
        b = Brillig(store)
        b.bootstrap()
        e, group = b.beamish(), b.beamish()
        b.slithy(e.id, "w", "x")
        b.outgrabe(e.id, "species", "act")
        b.add_rath(e.id, group.id, "member")
        store.full_scans.clear()
        return b, store, e, group

    def test_galumph_resolved(self, counted):
        b, store, e, _ = counted
        assert b.galumph("w", "x").jabberwock.id == e.id
        assert store.full_scans == []

    def test_galumph_no_alias(self, counted):
        b, store, _, _ = counted
        assert isinstance(b.galumph("w", "nothing"), MomeResult)
        assert store.full_scans == []

    def test_uffish(self, counted):
        b, store, e, _ = counted
        assert len(b.uffish(e.id).raths) == 1
        assert store.full_scans == []

    def test_whiffling(self, counted):
        b, store, e, group = counted
        assert [f.jabberwock.id for f in b.whiffling(group.id)] == [e.id]
        assert store.full_scans == []


class TestGalumphOnDuckDB:
    """levadura's backend: the same answers through DuckDB's pushed-down match."""

    @pytest.fixture
    def duck(self):
        from yanantin.activity.backends.duckdb import DuckDBActivityStreamStore

        store = DuckDBActivityStreamStore(":memory:")
        b = Brillig(store)
        b.bootstrap()
        yield b
        store.close()

    def test_resolved_with_projections(self, duck):
        e = duck.beamish()
        duck.slithy(e.id, "act.name", "Bank Holding Company Act")
        duck.slithy(e.id, "act.short", "BHC Act")
        duck.outgrabe(e.id, "species", "act")
        view = duck.galumph("act.short", "BHC Act")
        assert view.jabberwock.id == e.id
        assert {t.wabe for t in view.toves} == {"act.name", "act.short"}
        assert [v.snicker_snack for v in view.vorpals] == ["act"]

    def test_two_meanings_are_candidates(self, duck):
        a, b = duck.beamish(), duck.beamish()
        duck.slithy(a.id, "act.short", "the Act")
        duck.slithy(b.id, "act.short", "the Act")
        found = duck.galumph("act.short", "the Act")
        assert isinstance(found, MomeResult)
        assert {c.id for c in found.candidates} == {a.id, b.id}

    def test_wabe_scopes_the_name(self, duck):
        a, b = duck.beamish(), duck.beamish()
        duck.slithy(a.id, "cfr.12.225", "Act")
        duck.slithy(b.id, "cfr.12.226", "Act")
        assert duck.galumph("cfr.12.225", "Act").jabberwock.id == a.id
        assert duck.galumph("cfr.12.226", "Act").jabberwock.id == b.id

    def test_mome_tove(self, duck):
        duck.slithy(None, "w", "unknown")
        found = duck.galumph("w", "unknown")
        assert isinstance(found, MomeResult)
        assert len(found.toves) == 1 and found.candidates == ()

    def test_at_world_time(self, duck):
        y1997 = datetime(1997, 6, 1, tzinfo=timezone.utc)
        y2010 = datetime(2010, 6, 1, tzinfo=timezone.utc)
        old, new = duck.beamish(), duck.beamish()
        duck.slithy(old.id, "w", "x", gyre_to=y2010)
        duck.slithy(new.id, "w", "x", gyre_from=y2010)
        assert duck.galumph("w", "x", at=y1997).jabberwock.id == old.id
        assert duck.galumph("w", "x", at=y2010).jabberwock.id == new.id

    def test_gyreless_alias_valid_in_the_past(self, duck):
        e = duck.beamish()
        duck.slithy(e.id, "act", "federal deposit insurance act")
        far_past = datetime(1990, 1, 1, tzinfo=timezone.utc)
        assert duck.galumph("act", "federal deposit insurance act", at=far_past).jabberwock.id == e.id
