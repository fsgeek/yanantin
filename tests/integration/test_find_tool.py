"""Blind contract tests for docs/design-find-tool.md's Python find API.

Live apacheta_test only: every test owns its Objects, view, registrants and
activity collections, and runs with both semantic and obfuscated field names.
Imports of the future API stay inside tests so an unavailable DB can still skip.
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

import pytest

from tests.integration._obfuscators import PrefixObfuscator

ARANGO_HOST = os.environ.get("YANANTIN_ARANGO_HOST", "http://localhost:8529")
ARANGO_DB = os.environ.get("YANANTIN_ARANGO_DB", "apacheta_test")
ARANGO_USER = os.environ.get("YANANTIN_ARANGO_USER", "apacheta_test")
ARANGO_PASSWORD = os.environ.get("YANANTIN_ARANGO_PASSWORD", "")
FIND_PROVIDER = uuid5(NAMESPACE_DNS, "yanantin.find")
UTC = timezone.utc


def _dt(value):
    """Accept either the JSON timestamp or its decoded Python representation."""
    return datetime.fromisoformat(value) if isinstance(value, str) else value


@pytest.fixture(scope="module")
def db():
    from arango import ArangoClient

    try:
        handle = ArangoClient(hosts=ARANGO_HOST).db(
            ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASSWORD)
        handle.version()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"ArangoDB test database not available: {e}")
    return handle


def _insert(objects, docs):
    objects.coll.insert_many([objects.obf.obfuscate_document(doc) for doc in docs])
    # Explicitly publish test writes to ArangoSearch, without sleeping or
    # requiring a wait_for_sync argument absent from the public find API.
    list(objects.db.aql.execute(
        "FOR d IN @@view SEARCH true OPTIONS {waitForSync: true} "
        "COLLECT WITH COUNT INTO n RETURN n",
        bind_vars={"@view": objects.view},
    ))


@pytest.fixture(params=["plain", "obfuscated"])
def objects(request, db):
    from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
    from yanantin.activity.models import FactRecord
    from yanantin.core.collection_definition import CollectionDefinition
    from yanantin.core.khipu import Khipu
    from yanantin.core.registration import RegistrantRecord
    from yanantin.core.storage_obfuscator import TransparentObfuscator
    from yanantin.recorder.storage.objects_definition import (
        OBJECTS_DEFINITION, ensure_objects_find_view)

    tag = uuid4().hex
    obf = PrefixObfuscator(f"f{tag}_") if request.param == "obfuscated" else TransparentObfuscator()
    name, view = f"find_objects_t_{tag}", f"find_view_t_{tag}"
    registrants = f"find_registrants_t_{tag}"
    facts, anchors = f"find_facts_t_{tag}", f"find_anchors_t_{tag}"
    sources = {key: uuid4() for key in ("desktop", "laptop", "wsl", "unwalked")}
    machines = {
        "desktop": "wam-desktop", "laptop": "travel-laptop",
        "wsl": str(sources["wsl"])[:8], "unwalked": "unwalked-host",
    }
    activity = None
    try:
        khipu = Khipu(db, obf)
        coll = khipu.watay(name, OBJECTS_DEFINITION)
        ensure_objects_find_view(db, obf, collection=name, view=view)
        registrations = khipu.watay(registrants, CollectionDefinition(schema=None))
        for key, source in sources.items():
            # Earlier parentheses are deliberately not the hostname suffix.
            label = ("linux-local-storage (v1) collector" if key == "wsl" else
                     f"linux-local-storage (v1) collector ({machines[key]})")
            record = RegistrantRecord(
                registrant_id=source, registrant_name=label,
                registrant_kind="provider", description="find test storage source",
            ).model_dump(mode="json")
            registrations.insert(obf.obfuscate_document({"_key": str(source), **record}))

        activity = ArangoDBActivityStreamStore(
            host=ARANGO_HOST, db_name=ARANGO_DB, username=ARANGO_USER,
            password=ARANGO_PASSWORD, obfuscator=obf,
            facts_collection=facts, anchors_collection=anchors,
        )
        env = SimpleNamespace(
            db=db, obf=obf, coll=coll, collection=name, view=view,
            registrants=registrants, activity=activity, sources=sources, machines=machines,
        )
        # Same URI on two machines is two objects, with different size and time.
        rows = [
            ("file:///srv/a/.ssh/config", "config", "desktop", "2026-10-01T00:00:00Z", 101),
            ("file:///srv/a/.ssh/config", "config", "laptop", "2026-10-03T00:00:00Z", 303),
            ("file:///srv/b/projects/x/.ssh/known_hosts", "known_hosts", "desktop", "2026-09-01T00:00:00Z", 0),
            ("file:///srv/c/openssh/config", "config", "desktop", "2026-10-02T00:00:00Z", 202),
            ("file:///srv/d/ssh/config", "config", "laptop", "2026-10-04T00:00:00Z", 404),
            ("file:///srv/e/.config/app/config", "config", "laptop", "2026-08-01T00:00:00Z", 80),
            ("file:///srv/a/.ssh/projects/config", "config", "desktop", "2026-10-05T00:00:00Z", 505),
            ("file:///srv/projects/.ssh/notes", "notes", "laptop", "2026-10-06T00:00:00Z", 606),
            # The filename itself must not satisfy a directory condition.
            ("file:///srv/projects/.ssh", ".ssh", "desktop", "2026-10-07T00:00:00Z", 707),
            ("file:///srv/unknown/config", "config", "wsl", "2026-10-08T00:00:00Z", 808),
            ("file:///srv/empty/report", "report", "unwalked", "2026-10-09T00:00:00Z", 909),
        ]
        _insert(env, [
            {"uri": uri, "label": label, "source": str(sources[source]),
             "modified": modified, "size": size,
             # Opposite chronology catches accidentally filtering on birth time.
             "created": "2020-01-01T00:00:00Z"}
            for uri, label, source, modified, size in rows
        ])

        def landing(source, landed_day, walk):
            activity.store_fact(FactRecord(
                provider_id=sources[source],
                timestamp=datetime(2026, 11, landed_day, tzinfo=UTC),
                data={} if walk is None else {"walk": walk},
            ))

        # Max started, rather than latest fact, and only all-names walks count.
        landing("desktop", 1, {"all_names": True, "started": "2026-10-25T12:00:00+00:00"})
        landing("desktop", 2, {"all_names": True, "started": "2026-10-20T12:00:00+00:00"})
        landing("desktop", 3, {"all_names": False, "started": "2026-10-30T12:00:00+00:00"})
        landing("desktop", 4, None)
        landing("laptop", 1, {"all_names": True, "started": "2026-10-24T09:00:00+00:00"})
        landing("laptop", 2, {"all_names": True})  # incomplete metadata
        landing("wsl", 1, {"all_names": True, "started": "2026-10-23T08:00:00+00:00"})
        landing("unwalked", 1, {"all_names": False, "started": "2026-10-31T00:00:00+00:00"})
        yield env
    finally:
        if activity is not None:
            activity.close()
        db.delete_view(view, ignore_missing=True)  # view names are not obfuscated
        for semantic in (name, registrants, facts, anchors):
            db.delete_collection(obf.collection_name(semantic), ignore_missing=True)


def _query(**kwargs):
    from yanantin.find import CompiledQuery

    return CompiledQuery(**kwargs)


def _find(objects, **kwargs):
    from yanantin.find import find_objects

    return find_objects(
        objects.db, _query(**kwargs), activity=objects.activity,
        obfuscator=objects.obf, collection=objects.collection,
        view=objects.view, registrants=objects.registrants,
    )


def _coverage(objects, result):
    expected = {
        objects.machines["desktop"]: datetime(2026, 10, 25, 12, tzinfo=UTC),
        objects.machines["laptop"]: datetime(2026, 10, 24, 9, tzinfo=UTC),
        objects.machines["wsl"]: datetime(2026, 10, 23, 8, tzinfo=UTC),
        objects.machines["unwalked"]: None,
    }
    assert isinstance(result.coverage, list)
    assert len(result.coverage) == len(expected)
    assert all(set(row) == {"machine", "last_walk"} for row in result.coverage)
    # Unlike hit timestamps, coverage explicitly promises Python datetimes.
    assert {row["machine"]: row["last_walk"] for row in result.coverage} == expected


@pytest.mark.parametrize("kwargs", [
    {}, {"limit": 0}, {"limit": 99}, {"path_segments": (), "machines": ()},
])
def test_no_condition_is_refused(objects, kwargs):
    with pytest.raises(ValueError):
        _query(**kwargs)


def test_negative_limit_is_refused(objects):
    with pytest.raises(ValueError):
        _query(name="config", limit=-1)


def test_query_defaults_and_frozen_fields(objects):
    query = _query(name="config")
    assert query.name == "config"
    assert query.name_contains is None
    assert query.path_segments == ()
    assert query.modified_after is None and query.modified_before is None
    assert query.machines == ()
    assert query.limit == 20
    with pytest.raises((AttributeError, ValueError)):
        query.limit = 1
    assert query.limit == 20


def test_summary_only_counts_every_machine_and_parent_directory(objects):
    result = _find(objects, name="config", limit=0)
    assert result.total_matched == 7
    assert result.by_machine == {"wam-desktop": 3, "travel-laptop": 3, objects.machines["wsl"]: 1}
    assert result.top_directories[0] == ("file:///srv/a/.ssh", 2)
    assert dict(result.top_directories) == {
        "file:///srv/a/.ssh": 2, "file:///srv/c/openssh": 1,
        "file:///srv/d/ssh": 1, "file:///srv/e/.config/app": 1,
        "file:///srv/a/.ssh/projects": 1, "file:///srv/unknown": 1,
    }
    assert len(result.top_directories) == 6
    assert result.hits == []
    _coverage(objects, result)


def test_limit_changes_hits_without_truncating_summary(objects):
    summary = _find(objects, name="config", limit=0)
    result = _find(objects, name="config", limit=2)
    assert (result.total_matched, result.by_machine, dict(result.top_directories)) == (
        summary.total_matched, summary.by_machine, dict(summary.top_directories))
    assert [hit["uri"] for hit in result.hits] == [
        "file:///srv/unknown/config", "file:///srv/a/.ssh/projects/config"]


def test_hits_keep_machine_size_and_modified_for_shared_uris(objects):
    result = _find(objects, name="config", path_segments=(".ssh",))
    assert result.total_matched == 3
    assert result.by_machine == {"wam-desktop": 2, "travel-laptop": 1}
    assert all(set(hit) == {"uri", "machine", "modified", "size"} for hit in result.hits)
    assert [(hit["uri"], hit["machine"], _dt(hit["modified"]), hit["size"])
            for hit in result.hits] == [
        ("file:///srv/a/.ssh/projects/config", "wam-desktop", datetime(2026, 10, 5, tzinfo=UTC), 505),
        ("file:///srv/a/.ssh/config", "travel-laptop", datetime(2026, 10, 3, tzinfo=UTC), 303),
        ("file:///srv/a/.ssh/config", "wam-desktop", datetime(2026, 10, 1, tzinfo=UTC), 101),
    ]


def test_name_and_substring_agree_but_only_substring_matches_longer_names(objects):
    exact = _find(objects, name="config")
    contains = _find(objects, name_contains="config")
    assert exact.total_matched == contains.total_matched == 7
    assert exact.hits == contains.hits
    _insert(objects, [
        {"uri": f"file:///srv/extra/{label}", "label": label,
         "source": str(objects.sources["desktop"]), "modified": "2026-10-10T00:00:00Z", "size": 1}
        for label in ("config.old", "myconfig")
    ])
    assert _find(objects, name="config").total_matched == 7
    assert _find(objects, name_contains="config").total_matched == 9
    assert _find(objects, name="config.old", name_contains="myconfig").total_matched == 0


def test_segments_are_exact_directories_and_all_are_required(objects):
    result = _find(objects, path_segments=(".ssh",))
    assert result.total_matched == 5
    assert {hit["uri"] for hit in result.hits} == {
        "file:///srv/a/.ssh/config", "file:///srv/b/projects/x/.ssh/known_hosts",
        "file:///srv/a/.ssh/projects/config", "file:///srv/projects/.ssh/notes",
    }
    result = _find(objects, path_segments=("projects", ".ssh"))
    assert result.total_matched == 3
    assert {hit["uri"] for hit in result.hits} == {
        "file:///srv/b/projects/x/.ssh/known_hosts", "file:///srv/a/.ssh/projects/config",
        "file:///srv/projects/.ssh/notes",
    }
    zero_size = next(hit for hit in result.hits if hit["uri"].endswith("known_hosts"))
    assert zero_size["size"] == 0


@pytest.mark.parametrize("conditions, expected", [
    ({"modified_after": datetime(2026, 10, 1, tzinfo=UTC)}, 6),
    ({"modified_before": datetime(2026, 10, 5, tzinfo=UTC)}, 5),
    ({"modified_after": datetime(2026, 10, 1, tzinfo=UTC),
      "modified_before": datetime(2026, 10, 5, tzinfo=UTC)}, 4),
    ({"modified_after": datetime(2026, 10, 1, tzinfo=UTC),
      "modified_before": datetime(2026, 10, 1, tzinfo=UTC)}, 0),
])
def test_modified_window_is_lower_inclusive_upper_exclusive(objects, conditions, expected):
    result = _find(objects, name="config", **conditions)
    assert result.total_matched == expected
    for hit in result.hits:
        modified = _dt(hit["modified"])
        if "modified_after" in conditions:
            assert modified >= conditions["modified_after"]
        if "modified_before" in conditions:
            assert modified < conditions["modified_before"]


def test_time_alone_uses_modified_and_respects_timezone_offsets(objects):
    result = _find(
        objects,
        modified_after=datetime(2026, 10, 1, 5, tzinfo=timezone(timedelta(hours=5))),
        modified_before=datetime(2026, 10, 3, 5, tzinfo=timezone(timedelta(hours=5))),
    )
    assert result.total_matched == 2
    assert [hit["uri"] for hit in result.hits] == [
        "file:///srv/c/openssh/config", "file:///srv/a/.ssh/config"]


def test_machine_filter_uses_registrant_hostnames_and_short_id_fallback(objects):
    assert _find(objects, machines=("wam-desktop",)).total_matched == 5
    assert _find(objects, machines=("wam-desktop", "travel-laptop")).total_matched == 9
    result = _find(objects, name="config", machines=(objects.machines["wsl"],))
    assert result.total_matched == 1
    assert result.by_machine == {objects.machines["wsl"]: 1}
    assert result.hits[0]["machine"] == objects.machines["wsl"]
    # An unknown machine raises, naming the known ones (design: Decisions 6); an
    # empty result would read as "no such file there" (e.g. "gazelle" is pop-os).
    with pytest.raises(ValueError, match="unknown-host"):
        _find(objects, machines=("unknown-host",))


def test_all_conditions_intersect(objects):
    result = _find(
        objects, name="config", name_contains="onfi", path_segments=("srv", ".ssh"),
        machines=("wam-desktop",), modified_after=datetime(2026, 10, 1, tzinfo=UTC),
        modified_before=datetime(2026, 10, 5, tzinfo=UTC),
    )
    assert result.total_matched == 1
    assert result.by_machine == {"wam-desktop": 1}
    assert [hit["uri"] for hit in result.hits] == ["file:///srv/a/.ssh/config"]


def test_zero_results_still_describe_all_indexed_machines(objects):
    result = _find(objects, name="not-present", machines=("wam-desktop",))
    assert result.total_matched == 0
    assert result.by_machine == {}
    assert result.top_directories == []
    assert result.hits == []
    _coverage(objects, result)
    assert objects.activity.get_fact(result.fact_id).data["total_matched"] == 0


def test_coverage_uses_latest_complete_all_names_walk_not_latest_fact(objects):
    result = _find(objects, name="report")
    assert result.total_matched == 1
    _coverage(objects, result)
    # Find's newly appended fact is not an indexed machine on the next call.
    _coverage(objects, _find(objects, name="report", limit=0))


def test_default_twenty_hits_are_newest_and_total_is_unlimited(objects):
    _insert(objects, [
        {"uri": f"file:///srv/many/{i}/bulk", "label": "bulk",
         "source": str(objects.sources["desktop"]), "size": i,
         "modified": f"2026-10-{i + 1:02d}T00:00:00Z"}
        for i in range(25)
    ])
    result = _find(objects, name="bulk")
    assert result.total_matched == 25
    assert result.by_machine == {"wam-desktop": 25}
    assert len(result.hits) == 20
    assert [hit["size"] for hit in result.hits] == list(range(24, 4, -1))


def test_top_ten_directories_count_the_full_match_set(objects):
    _insert(objects, [
        {"uri": f"file:///srv/diversity/d{directory}/diversity{item}", "label": f"diversity{item}",
         "source": str(objects.sources["desktop"]), "size": item,
         "modified": "2026-10-01T00:00:00Z"}
        for directory in range(1, 13) for item in range(directory)
    ])
    result = _find(objects, name_contains="diversity", limit=1)
    assert result.total_matched == 78
    assert len(result.hits) == 1
    assert result.top_directories == [
        (f"file:///srv/diversity/d{i}", i) for i in range(12, 2, -1)]


@pytest.mark.parametrize("dominant_count, expected", [
    (20, [("file:///threshold/shared", 40)]),
    (21, [("file:///threshold/shared/d00", 21)] + [
        (f"file:///threshold/shared/d{i:02d}", 1) for i in range(1, 10)]),
    (22, [("file:///threshold/shared/d00", 22)] + [
        (f"file:///threshold/shared/d{i:02d}", 1) for i in range(1, 10)]),
], ids=["below-75-percent", "exactly-75-percent", "above-75-percent"])
def test_top_directories_threshold_is_inclusive_and_uses_all_matches(
        objects, dominant_count, expected):
    # At depth 3 the top ten hold 29, 30 or 31 of 40 matches. Only the
    # below-threshold case must roll up to depth 2; no single bucket has 75%.
    directories = [0] * dominant_count + list(range(1, 41 - dominant_count))
    _insert(objects, [
        {"uri": f"file:///threshold/shared/d{directory:02d}/threshold-probe-{item}",
         "label": f"threshold-probe-{item}", "source": str(objects.sources["desktop"]),
         "size": 1, "modified": "2026-10-01T00:00:00Z"}
        for item, directory in enumerate(directories)
    ])
    result = _find(objects, name_contains="threshold-probe", limit=1)
    assert result.total_matched == 40
    assert len(result.hits) == 1
    assert result.top_directories == expected


def test_top_directories_choose_the_deepest_qualifying_depth(objects):
    # Depth 5 has twelve buckets of two (top ten: 20/24); depth 6 splits
    # every match into its own bucket (top ten: 10/24). Shallower depths
    # also qualify, but depth 5 is the deepest that does.
    _insert(objects, [
        {"uri": f"file:///deepest/shared/project/cache/g{group:02d}/l{leaf}/deepest-probe",
         "label": "deepest-probe", "source": str(objects.sources["desktop"]),
         "size": 1, "modified": "2026-10-01T00:00:00Z"}
        for group in reversed(range(12)) for leaf in range(2)
    ])
    result = _find(objects, name="deepest-probe", limit=0)
    assert result.total_matched == 24
    assert result.top_directories == [
        (f"file:///deepest/shared/project/cache/g{group:02d}", 2)
        for group in range(10)
    ]


def test_top_directories_never_go_beyond_six_components(objects):
    # Depths 7 and 8 still qualify (10/12), so the cap alone must stop
    # descent at component 6, "five". The filename is not a component.
    _insert(objects, [
        {"uri": f"file:///cap/one/two/three/four/five/b{branch:02d}/leaf/cap-probe",
         "label": "cap-probe", "source": str(objects.sources["desktop"]),
         "size": 1, "modified": "2026-10-01T00:00:00Z"}
        for branch in range(12)
    ])
    result = _find(objects, name="cap-probe", limit=0)
    assert result.total_matched == 12
    assert result.top_directories == [("file:///cap/one/two/three/four/five", 12)]


def test_top_directories_keep_whole_directories_for_shallow_hits(objects):
    _insert(objects, [
        {"uri": uri, "label": "shallow-probe",
         "source": str(objects.sources["desktop"]), "size": 1,
         "modified": "2026-10-01T00:00:00Z"}
        for uri in (
            "file:///shallow-probe",
            "file:///shallow/shallow-probe",
            "file:///shallow/middle/short/shallow-probe",
            "file:///shallow/two/three/four/five/six/a/shallow-probe",
            "file:///shallow/two/three/four/five/six/b/shallow-probe",
        )
    ])
    result = _find(objects, name="shallow-probe", limit=0)
    assert result.total_matched == 5
    assert result.top_directories == [
        ("file:///shallow/two/three/four/five/six", 2),
        ("file:///", 1),
        ("file:///shallow", 1),
        ("file:///shallow/middle/short", 1),
    ]


def test_top_directories_shallow_hits_contribute_to_the_threshold(objects):
    # At depth 6, the shallow bucket's 21 matches plus nine deep singletons
    # reach exactly 30/40. Ignoring shallow hits when choosing the depth
    # would incorrectly reject depth 6 and roll up the deep directories.
    directories = ["file:///short"] * 21 + [
        f"file:///mixed/shared/three/four/five/d{item:02d}" for item in range(19)
    ]
    _insert(objects, [
        {"uri": f"{directory}/shallow-threshold-{item}",
         "label": f"shallow-threshold-{item}",
         "source": str(objects.sources["desktop"]), "size": 1,
         "modified": "2026-10-01T00:00:00Z"}
        for item, directory in enumerate(directories)
    ])
    result = _find(objects, name_contains="shallow-threshold-", limit=0)
    assert result.total_matched == 40
    assert result.top_directories == [("file:///short", 21)] + [
        (f"file:///mixed/shared/three/four/five/d{item:02d}", 1) for item in range(9)
    ]


def test_top_directories_depth_one_always_qualifies(objects):
    # Even at depth 1 the top ten cover only 10/16 matches. The fallback
    # must return those ten first-component buckets, with ties by name.
    _insert(objects, [
        {"uri": f"file:///fallback{directory:02d}/child/leaf/fallback-probe",
         "label": "fallback-probe", "source": str(objects.sources["desktop"]),
         "size": 1, "modified": "2026-10-01T00:00:00Z"}
        for directory in reversed(range(16))
    ])
    result = _find(objects, name="fallback-probe", limit=0)
    assert result.total_matched == 16
    assert result.top_directories == [
        (f"file:///fallback{directory:02d}", 1) for directory in range(10)
    ]


def test_top_directories_order_by_count_then_name_before_ten_bucket_cutoff(objects):
    # Twelve buckets qualify (top ten: 22/26). Eleven tie for the nine
    # remaining slots after zeta, whose larger count outranks its name.
    names = ("theta", "mu", "lambda", "kappa", "iota", "gamma", "eta",
             "epsilon", "delta", "beta", "alpha", "zeta")
    _insert(objects, [
        {"uri": f"file:///ties/shared/{name}/ties-probe{item}",
         "label": f"ties-probe{item}", "source": str(objects.sources["desktop"]),
         "size": 1, "modified": "2026-10-01T00:00:00Z"}
        for name in names for item in range(4 if name == "zeta" else 2)
    ])
    result = _find(objects, name_contains="ties-probe", limit=0)
    assert result.total_matched == 26
    assert result.top_directories == [
        ("file:///ties/shared/zeta", 4),
        ("file:///ties/shared/alpha", 2),
        ("file:///ties/shared/beta", 2),
        ("file:///ties/shared/delta", 2),
        ("file:///ties/shared/epsilon", 2),
        ("file:///ties/shared/eta", 2),
        ("file:///ties/shared/gamma", 2),
        ("file:///ties/shared/iota", 2),
        ("file:///ties/shared/kappa", 2),
        ("file:///ties/shared/lambda", 2),
    ]


@pytest.mark.parametrize("condition", ["name", "name_contains", "path_segments", "machines"])
def test_query_values_are_literal_even_with_quotes_and_wildcards(objects, condition):
    value = "odd'\"\\%_ OR true"
    uri = f"file:///srv/{value}/{value}"
    distractor = "odd'\"\\anythingX OR true"
    _insert(objects, [
        {"uri": uri, "label": value, "source": str(objects.sources["desktop"]),
         "size": 17, "modified": "2026-10-01T00:00:00Z"},
        # LIKE-style interpretation of % and _ would also select this row.
        {"uri": f"file:///srv/distractor/{distractor}", "label": distractor,
         "source": str(objects.sources["desktop"]), "size": 18,
         "modified": "2026-10-01T00:00:00Z"},
    ])
    argument = (value,) if condition in ("path_segments", "machines") else value
    if condition == "machines":  # unknown machines raise (design: Decisions 6)
        with pytest.raises(ValueError, match="unknown machine"):
            _find(objects, **{condition: argument})
        return
    result = _find(objects, **{condition: argument})
    assert result.total_matched == (0 if condition == "machines" else 1)
    assert [hit["uri"] for hit in result.hits] == ([] if condition == "machines" else [uri])


def test_each_call_records_one_fact_with_query_summary_and_returned_uris(objects):
    from yanantin.find import FIND_PROVIDER_ID

    assert FIND_PROVIDER_ID == FIND_PROVIDER
    before = objects.activity.count_facts()
    query_args = {
        "name": "config", "name_contains": "onfi", "path_segments": (".ssh",),
        "machines": ("wam-desktop",), "modified_after": datetime(2026, 10, 1, tzinfo=UTC),
        "modified_before": datetime(2026, 10, 6, tzinfo=UTC), "limit": 1,
    }
    result = _find(objects, **query_args)
    assert isinstance(result.fact_id, UUID)
    assert result.duplicate_of is None
    assert objects.activity.count_facts() == before + 1
    assert objects.activity.count_facts(FIND_PROVIDER) == 1
    fact = objects.activity.get_fact(result.fact_id)
    assert fact.provider_id == FIND_PROVIDER
    data = fact.data
    assert data["total_matched"] == result.total_matched == 2
    assert data["by_machine"] == result.by_machine == {"wam-desktop": 2}
    assert data["returned"] == [hit["uri"] for hit in result.hits]
    assert data["duplicate_of"] is None
    assert "query_shape" in data
    assert isinstance(data["elapsed_ms"], (int, float))
    assert math.isfinite(data["elapsed_ms"]) and data["elapsed_ms"] >= 0
    recorded = data["query"]
    for key in ("name", "name_contains", "limit"):
        assert recorded[key] == query_args[key]
    for key in ("path_segments", "machines"):
        assert tuple(recorded[key]) == query_args[key]
    for key in ("modified_after", "modified_before"):
        assert _dt(recorded[key]) == query_args[key]


def test_duplicate_chain_ignores_limit_and_set_order_and_uses_most_recent(objects):
    from yanantin.activity.models import FactRecord

    args = {"name": "config", "path_segments": ("srv", ".ssh"),
            "machines": ("wam-desktop", "travel-laptop")}
    first = _find(objects, **args, limit=0)
    second = _find(
        objects, name="config", path_segments=(".ssh", "srv"),
        machines=("travel-laptop", "wam-desktop"), limit=2,
    )
    # An unrelated intervening fact must not become the duplicate target.
    unrelated = _find(objects, name="known_hosts")
    # Even an identical shape from a different provider is not find history.
    objects.activity.store_fact(FactRecord(
        provider_id=objects.sources["desktop"], timestamp=datetime.now(UTC),
        data=objects.activity.get_fact(second.fact_id).data,
    ))
    third = _find(objects, **args, limit=20)
    assert first.duplicate_of is None and unrelated.duplicate_of is None
    assert second.duplicate_of == first.fact_id
    assert third.duplicate_of == second.fact_id
    facts = [objects.activity.get_fact(result.fact_id) for result in (first, second, third)]
    assert facts[0].data["query_shape"] == facts[1].data["query_shape"] == facts[2].data["query_shape"]
    assert UUID(str(facts[1].data["duplicate_of"])) == first.fact_id
    assert UUID(str(facts[2].data["duplicate_of"])) == second.fact_id
    assert facts[0].data["returned"] == []
    assert len({first.fact_id, second.fact_id, third.fact_id, unrelated.fact_id}) == 4
    assert objects.activity.count_facts(FIND_PROVIDER) == 4


def test_every_condition_participates_in_query_shape(objects):
    args = {
        "name": "config", "name_contains": "conf", "path_segments": ("srv",),
        "machines": ("wam-desktop",), "modified_after": datetime(2026, 9, 1, tzinfo=UTC),
        "modified_before": datetime(2026, 11, 1, tzinfo=UTC), "limit": 0,
    }
    first = _find(objects, **args)
    shapes = [objects.activity.get_fact(first.fact_id).data["query_shape"]]
    for key, changed in (
        ("name", "known_hosts"), ("name_contains", "onfi"),
        ("path_segments", (".ssh",)), ("machines", ("travel-laptop",)),
        ("modified_after", datetime(2026, 9, 2, tzinfo=UTC)),
        ("modified_before", datetime(2026, 10, 31, tzinfo=UTC)),
    ):
        result = _find(objects, **{**args, key: changed})
        assert result.duplicate_of is None, key
        shape = objects.activity.get_fact(result.fact_id).data["query_shape"]
        assert all(shape != earlier for earlier in shapes), key
        shapes.append(shape)
    assert _find(objects, **args).duplicate_of == first.fact_id


def test_find_result_is_frozen(objects):
    from yanantin.find import FindResult

    result = _find(objects, name="config")
    assert isinstance(result, FindResult)
    with pytest.raises((AttributeError, ValueError)):
        result.total_matched = 999
    assert result.total_matched == 7


@pytest.mark.parametrize("conditions", [
    {"name": "config"}, {"path_segments": (".ssh",)},
    {"modified_after": datetime(2026, 10, 1, tzinfo=UTC)},
])
def test_missing_view_raises_even_when_an_index_could_answer(objects, conditions):
    # Establish a working call first: an unrelated import/setup error cannot
    # satisfy the intentionally unspecified exception type for a missing view.
    assert _find(objects, **conditions).total_matched > 0
    objects.db.delete_view(objects.view)
    with pytest.raises(Exception):
        _find(objects, **conditions)
    assert objects.view not in {view["name"] for view in objects.db.views()}


# Added by the steward after the blind tests, from the live index (2026-11-09):
# the landing's recorder registers itself in the same catalog, but it holds no
# files, so it must not be offered as a machine.
def test_the_recorder_is_not_a_machine(objects):
    from yanantin.core.registration import RegistrantRecord
    from yanantin.recorder.storage.local.linux.registration import RECORDER_ID

    record = RegistrantRecord(
        registrant_id=RECORDER_ID, registrant_name="linux-local-storage recorder",
        registrant_kind="provider", description="records snapshots",
    ).model_dump(mode="json")
    objects.db.collection(objects.obf.collection_name(objects.registrants)).insert(
        objects.obf.obfuscate_document({"_key": str(RECORDER_ID), **record}))
    result = _find(objects, name="config")
    assert str(RECORDER_ID)[:8] not in {row["machine"] for row in result.coverage}
    with pytest.raises(ValueError, match="unknown machine"):
        _find(objects, machines=(str(RECORDER_ID)[:8],))


# Added by the steward (2026-11-09): people name machines by their ssh alias, and
# the index knows them by hostname (Tony's gazelle is pop-os). The nightly refresh
# writes the alias it connected with into each walk's manifest; find accepts it.
def test_a_machine_can_be_asked_for_by_the_alias_its_walk_recorded(objects):
    from yanantin.activity.models import FactRecord

    objects.activity.store_fact(FactRecord(
        provider_id=objects.sources["desktop"], timestamp=datetime(2026, 11, 9, tzinfo=UTC),
        data={"walk": {"all_names": True, "started": "2026-11-09T04:30:00+00:00", "alias": "ubuntu24"}},
    ))
    by_alias = _find(objects, name="config", machines=("ubuntu24",))
    by_host = _find(objects, name="config", machines=("wam-desktop",))
    assert by_alias.total_matched == by_host.total_matched > 0
    assert set(by_alias.by_machine) == {"wam-desktop"}
    with pytest.raises(ValueError, match=r"wam-desktop \(ubuntu24\)"):
        _find(objects, machines=("nonesuch",))
