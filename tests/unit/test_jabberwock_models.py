"""Unit tests for Jabberwock data models.

Verifies frozen semantics, extra policy (allow for stored records,
forbid for views), naive datetime rejection, temporal ordering,
UUID defaults, and provider UUID determinism for all Jabberwock NER models.

Test author: separate from builder (CI enforces separation).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

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


NOW = datetime.now(timezone.utc)
YESTERDAY = NOW - timedelta(days=1)
TOMORROW = NOW + timedelta(days=1)
PROVIDER = uuid4()


# -- Jabberwock (Entity) ---------------------------------------------------


class TestJabberwock:
    def test_create_valid(self):
        j = Jabberwock(brillig=NOW, bandersnatch=PROVIDER)
        assert isinstance(j.id, UUID)
        assert j.brillig.tzinfo is not None
        assert j.bandersnatch == PROVIDER

    def test_uuid_default_generation(self):
        j1 = Jabberwock(brillig=NOW, bandersnatch=PROVIDER)
        j2 = Jabberwock(brillig=NOW, bandersnatch=PROVIDER)
        assert j1.id != j2.id, "Each Jabberwock should get a unique UUID"

    def test_frozen(self):
        j = Jabberwock(brillig=NOW, bandersnatch=PROVIDER)
        with pytest.raises(ValidationError):
            j.brillig = YESTERDAY  # type: ignore[misc]

    def test_extra_allow(self):
        """Stored records accept unknown fields (event-sourced forward compat)."""
        j = Jabberwock(brillig=NOW, bandersnatch=PROVIDER, species="person")  # type: ignore[call-arg]
        assert j.brillig is not None  # extra field accepted silently

    def test_naive_datetime_rejected(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        with pytest.raises(ValidationError, match="[Nn]aive"):
            Jabberwock(brillig=naive, bandersnatch=PROVIDER)

    def test_timezone_converted_to_utc(self):
        from datetime import timezone as tz

        est = tz(timedelta(hours=-5))
        t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=est)
        j = Jabberwock(brillig=t, bandersnatch=PROVIDER)
        assert j.brillig.tzinfo == timezone.utc


# -- Tove (Alias) ----------------------------------------------------------


class TestTove:
    def test_create_valid(self):
        t = Tove(
            wabe="github",
            gimble="fsgeek",
            gyre_from=YESTERDAY,
            bandersnatch=PROVIDER,
            brillig=NOW,
            jabberwock_id=uuid4(),
        )
        assert isinstance(t.id, UUID)
        assert t.wabe == "github"
        assert t.gimble == "fsgeek"

    def test_mome_tove(self):
        """jabberwock_id=None means the alias is unresolved (mome)."""
        t = Tove(
            wabe="github",
            gimble="unknown_user",
            gyre_from=NOW,
            bandersnatch=PROVIDER,
            brillig=NOW,
            jabberwock_id=None,
        )
        assert t.jabberwock_id is None

    def test_frozen(self):
        t = Tove(
            wabe="github",
            gimble="fsgeek",
            gyre_from=NOW,
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        with pytest.raises(ValidationError):
            t.wabe = "canvas"  # type: ignore[misc]

    def test_extra_allow(self):
        """Stored records accept unknown fields (event-sourced forward compat)."""
        t = Tove(
            wabe="github",
            gimble="fsgeek",
            gyre_from=NOW,
            bandersnatch=PROVIDER,
            brillig=NOW,
            color="red",  # type: ignore[call-arg]
        )
        assert t.wabe == "github"  # extra field accepted silently

    def test_naive_datetime_brillig(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        with pytest.raises(ValidationError, match="[Nn]aive"):
            Tove(
                wabe="github",
                gimble="fsgeek",
                gyre_from=NOW,
                bandersnatch=PROVIDER,
                brillig=naive,
            )

    def test_naive_datetime_gyre_from(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        with pytest.raises(ValidationError, match="[Nn]aive"):
            Tove(
                wabe="github",
                gimble="fsgeek",
                gyre_from=naive,
                bandersnatch=PROVIDER,
                brillig=NOW,
            )

    def test_naive_datetime_gyre_to(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        with pytest.raises(ValidationError, match="[Nn]aive"):
            Tove(
                wabe="github",
                gimble="fsgeek",
                gyre_from=YESTERDAY,
                gyre_to=naive,
                bandersnatch=PROVIDER,
                brillig=NOW,
            )

    def test_gyre_to_before_gyre_from_raises(self):
        """Temporal ordering: gyre_to < gyre_from must raise ValueError."""
        with pytest.raises(ValidationError, match="gyre_to.*cannot precede"):
            Tove(
                wabe="github",
                gimble="fsgeek",
                gyre_from=TOMORROW,
                gyre_to=YESTERDAY,
                bandersnatch=PROVIDER,
                brillig=NOW,
            )

    def test_gyre_to_none_is_valid(self):
        """gyre_to=None means still current -- should not raise."""
        t = Tove(
            wabe="github",
            gimble="fsgeek",
            gyre_from=NOW,
            gyre_to=None,
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        assert t.gyre_to is None

    def test_gyre_to_equal_gyre_from_is_valid(self):
        """Instantaneous validity: gyre_to == gyre_from should be accepted."""
        t = Tove(
            wabe="github",
            gimble="fsgeek",
            gyre_from=NOW,
            gyre_to=NOW,
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        assert t.gyre_to == t.gyre_from


# -- Vorpal (Observation) --------------------------------------------------


class TestVorpal:
    def test_create_valid(self):
        v = Vorpal(
            jabberwock_id=uuid4(),
            tulgey="species",
            snicker_snack="person",
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        assert isinstance(v.id, UUID)
        assert v.tulgey == "species"
        assert v.snicker_snack == "person"

    def test_mome_vorpal(self):
        """jabberwock_id=None means the observation is unresolved (mome)."""
        v = Vorpal(
            jabberwock_id=None,
            tulgey="behavioral",
            snicker_snack="prefers bun over npm",
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        assert v.jabberwock_id is None

    def test_snicker_snack_accepts_dict(self):
        """snicker_snack can be any JSON-serializable value."""
        v = Vorpal(
            jabberwock_id=uuid4(),
            tulgey="claim",
            snicker_snack={"record_id": "abc", "jabberwock_id": "def"},
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        assert isinstance(v.snicker_snack, dict)

    def test_snicker_snack_accepts_list(self):
        v = Vorpal(
            jabberwock_id=uuid4(),
            tulgey="tags",
            snicker_snack=["a", "b", "c"],
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        assert isinstance(v.snicker_snack, list)

    def test_snicker_snack_accepts_int(self):
        v = Vorpal(
            jabberwock_id=uuid4(),
            tulgey="count",
            snicker_snack=42,
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        assert v.snicker_snack == 42

    def test_frozen(self):
        v = Vorpal(
            jabberwock_id=uuid4(),
            tulgey="species",
            snicker_snack="person",
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        with pytest.raises(ValidationError):
            v.tulgey = "other"  # type: ignore[misc]

    def test_extra_allow(self):
        """Stored records accept unknown fields (event-sourced forward compat)."""
        v = Vorpal(
            jabberwock_id=uuid4(),
            tulgey="species",
            snicker_snack="person",
            bandersnatch=PROVIDER,
            brillig=NOW,
            confidence=0.9,  # type: ignore[call-arg]
        )
        assert v.tulgey == "species"  # extra field accepted silently

    def test_naive_datetime_rejected(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        with pytest.raises(ValidationError, match="[Nn]aive"):
            Vorpal(
                jabberwock_id=uuid4(),
                tulgey="species",
                snicker_snack="person",
                bandersnatch=PROVIDER,
                brillig=naive,
            )


# -- Rath (Membership edge) ------------------------------------------------


class TestRath:
    def test_create_valid(self):
        r = Rath(
            jabberwock_id=uuid4(),
            borogove_id=uuid4(),
            mimsy="student",
            gyre_from=YESTERDAY,
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        assert isinstance(r.id, UUID)
        assert r.mimsy == "student"

    def test_frozen(self):
        r = Rath(
            jabberwock_id=uuid4(),
            borogove_id=uuid4(),
            mimsy="student",
            gyre_from=NOW,
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        with pytest.raises(ValidationError):
            r.mimsy = "ta"  # type: ignore[misc]

    def test_extra_allow(self):
        """Stored records accept unknown fields (event-sourced forward compat)."""
        r = Rath(
            jabberwock_id=uuid4(),
            borogove_id=uuid4(),
            mimsy="student",
            gyre_from=NOW,
            bandersnatch=PROVIDER,
            brillig=NOW,
            weight=1.0,  # type: ignore[call-arg]
        )
        assert r.mimsy == "student"  # extra field accepted silently

    def test_naive_datetime_brillig(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        with pytest.raises(ValidationError, match="[Nn]aive"):
            Rath(
                jabberwock_id=uuid4(),
                borogove_id=uuid4(),
                mimsy="student",
                gyre_from=NOW,
                bandersnatch=PROVIDER,
                brillig=naive,
            )

    def test_naive_datetime_gyre_from(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        with pytest.raises(ValidationError, match="[Nn]aive"):
            Rath(
                jabberwock_id=uuid4(),
                borogove_id=uuid4(),
                mimsy="student",
                gyre_from=naive,
                bandersnatch=PROVIDER,
                brillig=NOW,
            )

    def test_naive_datetime_gyre_to(self):
        naive = datetime(2026, 1, 1, 12, 0, 0)
        with pytest.raises(ValidationError, match="[Nn]aive"):
            Rath(
                jabberwock_id=uuid4(),
                borogove_id=uuid4(),
                mimsy="student",
                gyre_from=YESTERDAY,
                gyre_to=naive,
                bandersnatch=PROVIDER,
                brillig=NOW,
            )

    def test_gyre_to_before_gyre_from_raises(self):
        with pytest.raises(ValidationError, match="gyre_to.*cannot precede"):
            Rath(
                jabberwock_id=uuid4(),
                borogove_id=uuid4(),
                mimsy="student",
                gyre_from=TOMORROW,
                gyre_to=YESTERDAY,
                bandersnatch=PROVIDER,
                brillig=NOW,
            )

    def test_gyre_to_none_is_valid(self):
        r = Rath(
            jabberwock_id=uuid4(),
            borogove_id=uuid4(),
            mimsy="student",
            gyre_from=NOW,
            gyre_to=None,
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        assert r.gyre_to is None


# -- Frabjous (Resolved view) ----------------------------------------------


class TestFrabjous:
    def _make_jabberwock(self) -> Jabberwock:
        return Jabberwock(brillig=NOW, bandersnatch=PROVIDER)

    def test_create_valid(self):
        j = self._make_jabberwock()
        f = Frabjous(jabberwock=j, callooh=NOW)
        assert f.jabberwock.id == j.id
        assert f.toves == ()
        assert f.vorpals == ()
        assert f.raths == ()
        assert f.evidence_ids == ()
        assert f.excluded_count == 0

    def test_with_proof_envelope(self):
        """evidence_ids carries the proof envelope -- all contributing record IDs."""
        j = self._make_jabberwock()
        ids = (uuid4(), uuid4(), uuid4())
        f = Frabjous(jabberwock=j, callooh=NOW, evidence_ids=ids, excluded_count=2)
        assert f.evidence_ids == ids
        assert f.excluded_count == 2

    def test_frozen(self):
        j = self._make_jabberwock()
        f = Frabjous(jabberwock=j, callooh=NOW)
        with pytest.raises(ValidationError):
            f.excluded_count = 5  # type: ignore[misc]

    def test_extra_forbid(self):
        j = self._make_jabberwock()
        with pytest.raises(ValidationError):
            Frabjous(jabberwock=j, callooh=NOW, confidence=0.9)  # type: ignore[call-arg]

    def test_naive_datetime_callooh(self):
        j = self._make_jabberwock()
        naive = datetime(2026, 1, 1, 12, 0, 0)
        with pytest.raises(ValidationError, match="[Nn]aive"):
            Frabjous(jabberwock=j, callooh=naive)

    def test_with_toves_and_vorpals(self):
        j = self._make_jabberwock()
        t = Tove(
            jabberwock_id=j.id,
            wabe="github",
            gimble="fsgeek",
            gyre_from=NOW,
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        v = Vorpal(
            jabberwock_id=j.id,
            tulgey="species",
            snicker_snack="person",
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        f = Frabjous(
            jabberwock=j,
            callooh=NOW,
            toves=(t,),
            vorpals=(v,),
            evidence_ids=(j.id, t.id, v.id),
        )
        assert len(f.toves) == 1
        assert len(f.vorpals) == 1
        assert len(f.evidence_ids) == 3


# -- MomeResult (Partial resolution) ---------------------------------------


class TestMomeResult:
    def test_create_empty(self):
        m = MomeResult()
        assert m.toves == ()
        assert m.candidates == ()
        assert m.mome_vorpals == ()

    def test_create_populated(self):
        t = Tove(
            wabe="github",
            gimble="unknown",
            gyre_from=NOW,
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        v = Vorpal(
            jabberwock_id=None,
            tulgey="behavioral",
            snicker_snack="something",
            bandersnatch=PROVIDER,
            brillig=NOW,
        )
        m = MomeResult(toves=(t,), mome_vorpals=(v,))
        assert len(m.toves) == 1
        assert len(m.mome_vorpals) == 1

    def test_frozen(self):
        m = MomeResult()
        with pytest.raises(ValidationError):
            m.toves = ()  # type: ignore[misc]

    def test_extra_forbid(self):
        with pytest.raises(ValidationError):
            MomeResult(confidence=0.5)  # type: ignore[call-arg]


# -- Provider UUID constants -----------------------------------------------


class TestProviderConstants:
    def test_deterministic_uuids(self):
        """Provider UUIDs are deterministic -- same every time via uuid5."""
        from uuid import NAMESPACE_DNS, uuid5

        assert JABBERWOCK_PROVIDER == uuid5(NAMESPACE_DNS, "yanantin.jabberwock.entity")
        assert TOVE_PROVIDER == uuid5(NAMESPACE_DNS, "yanantin.jabberwock.tove")
        assert VORPAL_PROVIDER == uuid5(NAMESPACE_DNS, "yanantin.jabberwock.vorpal")
        assert RATH_PROVIDER == uuid5(NAMESPACE_DNS, "yanantin.jabberwock.rath")

    def test_root_bandersnatch_deterministic(self):
        """ROOT_BANDERSNATCH_ID is deterministic -- same every time."""
        from uuid import NAMESPACE_DNS, uuid5

        assert ROOT_BANDERSNATCH_ID == uuid5(NAMESPACE_DNS, "yanantin.jabberwock.root")

    def test_root_bandersnatch_consistent_across_imports(self):
        """Importing ROOT_BANDERSNATCH_ID twice gives the same value."""
        from yanantin.jabberwock.models import ROOT_BANDERSNATCH_ID as r1
        from yanantin.jabberwock.models import ROOT_BANDERSNATCH_ID as r2

        assert r1 == r2

    def test_provider_uuids_are_distinct(self):
        """Each provider UUID must be unique."""
        providers = {JABBERWOCK_PROVIDER, TOVE_PROVIDER, VORPAL_PROVIDER, RATH_PROVIDER}
        assert len(providers) == 4, "Provider UUIDs must be distinct from each other"

    def test_root_bandersnatch_distinct_from_providers(self):
        """ROOT_BANDERSNATCH_ID is not a provider UUID -- it's an entity."""
        providers = {JABBERWOCK_PROVIDER, TOVE_PROVIDER, VORPAL_PROVIDER, RATH_PROVIDER}
        assert ROOT_BANDERSNATCH_ID not in providers
