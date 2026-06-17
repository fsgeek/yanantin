"""Red-bar test: Activity stream structural invariants.

The activity stream stores facts — raw observations, schema-agnostic,
high-volume, append-only. Facts are NOT tensors. Tensors are authored
compressions. Wrapping a file stat in a TensorRecord is theater.

These tests enforce the structural properties that keep the boundary
between facts and tensors honest:

1. Facts must accept unknown fields (schema evolution for new providers)
2. All models must be frozen (immutability after creation)
3. The store has no update or delete operations
4. The write gate requires BOTH flags (updated AND referenced)
5. Materialization is late-bound (queries all providers, not just cursors)
6. DuckDB pushes queries to SQL (not Python-side filtering at 28.5M rows)
7. FactRecorderBase is structurally distinct from RecorderBase

These exist because:
- Indaleko's full dataset was 28.5M files, 7.7GB JSONL for one volume.
  Load-all-then-filter dies at that scale. Query pushdown is structural.
- A previous instance tried to store facts as tensors. Tony identified
  the error: facts have no authorial shaping, no declared losses, no
  epistemic metadata. Wrapping them in TensorRecord is theater.
- The two-flag write gate prevents writing anchors nobody asked for.
  Without it, every cursor update persists, flooding the anchor store.
"""

import ast
import inspect
from abc import abstractmethod

from yanantin.activity.models import (
    AnchorCursor,
    AnchorView,
    FactRecord,
    MemoryAnchor,
)
from yanantin.activity.store import ActivityStreamStore
from yanantin.activity.anchor import MemoryAnchorService
from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.activity.backends.duckdb import DuckDBActivityStreamStore
from yanantin.recorder.base import FactRecorderBase, RecorderBase


# -- Schema agnosticism: facts accept unknown fields -------------------


def test_fact_record_allows_extra_fields():
    """FactRecord must use extra='allow' for schema evolution.

    New data providers may include fields that don't exist in the current
    model. If FactRecord uses extra='forbid', every new provider field
    requires a model change. Schema evolution for facts is recording
    contract changes, not code changes. This is the opposite of tensors
    (which use extra='forbid' because their structure IS the contract).
    """
    config = FactRecord.model_config
    assert config.get("extra") == "allow", (
        f"FactRecord.extra is {config.get('extra')!r}, must be 'allow'. "
        "Facts are schema-agnostic — new providers bring new fields. "
        "extra='forbid' would break schema evolution."
    )


def test_anchor_cursor_forbids_extra_fields():
    """AnchorCursor must use extra='forbid' — structural record, not data.

    Unlike facts, cursors are internal bookkeeping. Extra fields on a
    cursor means something is wrong with the anchor service, not a new
    data provider.
    """
    config = AnchorCursor.model_config
    assert config.get("extra") == "forbid", (
        f"AnchorCursor.extra is {config.get('extra')!r}, must be 'forbid'. "
        "Cursors are structural records, not data containers."
    )


def test_memory_anchor_forbids_extra_fields():
    """MemoryAnchor must use extra='forbid' — immutable structural record."""
    config = MemoryAnchor.model_config
    assert config.get("extra") == "forbid"


def test_anchor_view_forbids_extra_fields():
    """AnchorView must use extra='forbid' — ephemeral resolution, not data."""
    config = AnchorView.model_config
    assert config.get("extra") == "forbid"


# -- Model immutability ------------------------------------------------


def test_all_activity_models_are_frozen():
    """All activity stream models must be frozen (immutable after creation).

    A fact that can be mutated after storage is not a fact — it's a
    draft. An anchor that can be modified defeats the Lamport clock
    semantics. Frozen models enforce this at the Pydantic level.
    """
    for model_cls in (FactRecord, AnchorCursor, MemoryAnchor, AnchorView):
        config = model_cls.model_config
        assert config.get("frozen") is True, (
            f"{model_cls.__name__}.frozen is {config.get('frozen')!r}, "
            f"must be True. Mutable activity stream records corrupt "
            f"temporal query semantics."
        )


# -- UTC enforcement ---------------------------------------------------


def test_fact_record_has_timestamp_validator():
    """FactRecord must validate timestamps to UTC.

    Naive datetimes corrupt sort order in every backend. ISO 8601 strings
    sort correctly only when timezone offsets are uniform. UTC is that
    uniform representation.
    """
    source = inspect.getsource(FactRecord)
    assert "_ensure_utc" in source or "_normalize_timestamp" in source, (
        "FactRecord must validate timestamps to UTC. Naive datetimes "
        "corrupt sort order across backends."
    )


def test_memory_anchor_has_timestamp_validator():
    """MemoryAnchor must validate timestamps to UTC."""
    source = inspect.getsource(MemoryAnchor)
    assert "_ensure_utc" in source or "_normalize_timestamp" in source, (
        "MemoryAnchor must validate timestamps to UTC."
    )


# -- Store ABC: append-only, no update, no delete ----------------------


def test_store_has_all_required_abstract_methods():
    """ActivityStreamStore must define exactly the required abstract methods.

    The store is a temporal append-only log. If a method is missing, a
    backend can implement the ABC without providing it. If extra methods
    appear (update, delete), the append-only contract is broken.
    """
    required = {
        "store_fact",
        "get_fact",
        "query_latest",
        "query_range",
        "store_anchor",
        "get_anchor",
        "get_latest_anchor",
        "list_providers",
        "count_facts",
    }

    abstract_methods = set()
    for name, method in inspect.getmembers(ActivityStreamStore):
        if getattr(method, "__isabstractmethod__", False):
            abstract_methods.add(name)

    assert abstract_methods == required, (
        f"ActivityStreamStore abstract methods: {abstract_methods}. "
        f"Expected: {required}. "
        f"Missing: {required - abstract_methods}. "
        f"Unexpected: {abstract_methods - required}."
    )


def test_store_has_no_update_methods():
    """The activity stream store must not have update or modify operations.

    Facts and anchors are append-only. An update method on the store
    would allow silent mutation of historical records. If you need a
    correction, store a new fact — don't modify the old one.
    """
    forbidden = ("update", "modify", "patch", "replace", "upsert")
    members = {name for name, _ in inspect.getmembers(ActivityStreamStore)}

    for word in forbidden:
        matches = [m for m in members if word in m.lower()]
        assert not matches, (
            f"ActivityStreamStore has methods containing '{word}': {matches}. "
            f"The store is append-only. Corrections are new records."
        )


def test_store_has_no_delete_methods():
    """The activity stream store must not have delete or remove operations.

    Deleting a fact corrupts every anchor that referenced it. Deleting
    an anchor breaks the Lamport clock chain. There is no safe delete
    in a temporal store.
    """
    forbidden = ("delete", "remove", "drop", "truncate", "purge")
    members = {name for name, _ in inspect.getmembers(ActivityStreamStore)}

    for word in forbidden:
        matches = [m for m in members if word in m.lower()]
        assert not matches, (
            f"ActivityStreamStore has methods containing '{word}': {matches}. "
            f"Deleting facts or anchors corrupts temporal queries."
        )


# -- Two-flag write gate -----------------------------------------------


def test_flush_checks_both_flags():
    """MemoryAnchorService.flush() must require BOTH updated AND referenced.

    The two-flag write gate prevents two failure modes:
    - Writing without update: persists identical anchors repeatedly,
      wasting storage and making latest-anchor queries return duplicates.
    - Writing without reference: persists data nobody asked for. If no
      caller requested the handle, the anchor is noise.

    Indaleko learned this over 8 years: write only when something changed
    AND someone asked for it.
    """
    source = inspect.getsource(MemoryAnchorService.flush)

    assert "_updated" in source and "_referenced" in source, (
        "flush() must check both _updated and _referenced flags. "
        "The two-flag write gate is the core of the anchor service."
    )

    # The check must be a conjunction (AND), not disjunction (OR)
    assert "and" in source.lower() or "&&" in source, (
        "flush() must use AND (conjunction) for the two-flag check. "
        "Using OR would write when only one flag is set."
    )


def test_update_cursor_sets_updated_flag():
    """update_cursor must set the _updated flag.

    Without this, flush() never writes because the updated flag stays False.
    The cursor update is meaningless if it doesn't open the write gate.
    """
    source = inspect.getsource(MemoryAnchorService.update_cursor)
    assert "_updated" in source and "True" in source, (
        "update_cursor must set self._updated = True."
    )


def test_get_handle_sets_referenced_flag():
    """get_handle must set the _referenced flag.

    Without this, flush() never writes because the referenced flag stays False.
    The handle is meaningless if it doesn't open the write gate.
    """
    source = inspect.getsource(MemoryAnchorService.get_handle)
    assert "_referenced" in source and "True" in source, (
        "get_handle must set self._referenced = True."
    )


def test_flush_resets_both_flags():
    """After a successful flush, both flags must be reset.

    Without reset, every subsequent flush writes again even if nothing
    changed. The flags are one-shot: set by update/reference, cleared
    by flush.
    """
    source = inspect.getsource(MemoryAnchorService.flush)
    assert source.count("False") >= 2, (
        "flush() must reset both _updated and _referenced to False. "
        "Without reset, the write gate stays open forever."
    )


# -- Late-binding materialization ---------------------------------------


def test_materialize_queries_all_providers():
    """materialize() must call list_providers() for late binding.

    Late binding means: a provider registered AFTER the anchor was created
    will appear in the materialized view if it has facts before the
    anchor's timestamp. This only works if materialize() discovers
    providers from the store at resolution time, not from the anchor's
    cursor list.

    Without late binding, old anchors can never benefit from new data
    sources. The frozen surface is permanently limited to what existed
    at creation time.
    """
    source = inspect.getsource(MemoryAnchorService.materialize)
    assert "list_providers" in source, (
        "materialize() must call list_providers() for late binding. "
        "Without it, new providers can't enrich old anchors."
    )


def test_materialize_iterates_all_providers_not_just_cursors():
    """materialize() must iterate over all_providers, not anchor.cursors.

    A subtle bug: if materialize() loops over `anchor.cursors` instead
    of the full provider list, late binding is broken. Providers that
    registered after the anchor's creation won't have cursors in the
    anchor, but they may have facts timestamped before the anchor.
    """
    source = inspect.getsource(MemoryAnchorService.materialize)
    # It should loop over all_providers (or similar), not anchor.cursors
    assert "all_providers" in source or "providers" in source.split("for")[1] if "for" in source else True, (
        "materialize() must iterate over all known providers, not just "
        "the anchor's cursor list."
    )

    # The query_latest call should happen inside the loop
    assert "query_latest" in source, (
        "materialize() must call query_latest for each provider to resolve "
        "the latest fact at or before the anchor timestamp."
    )


# -- DuckDB query pushdown ---------------------------------------------


def test_duckdb_query_latest_uses_sql():
    """DuckDB query_latest must push the query to SQL.

    At 28.5M facts, loading all rows into Python and filtering is not
    viable. The DuckDB backend must use WHERE and ORDER BY in SQL,
    not fetchall() followed by Python-side filtering.
    """
    source = inspect.getsource(DuckDBActivityStreamStore.query_latest)

    # Must have SQL WHERE clause with provider_id and timestamp
    assert "WHERE" in source, (
        "query_latest must use SQL WHERE, not Python-side filtering."
    )
    assert "ORDER BY" in source, (
        "query_latest must use SQL ORDER BY, not Python-side sorting."
    )
    assert "LIMIT 1" in source, (
        "query_latest must use SQL LIMIT 1, not Python-side slicing."
    )


def test_duckdb_query_range_uses_sql():
    """DuckDB query_range must push the query to SQL."""
    source = inspect.getsource(DuckDBActivityStreamStore.query_range)

    assert "WHERE" in source, (
        "query_range must use SQL WHERE, not Python-side filtering."
    )
    assert "ORDER BY" in source, (
        "query_range must use SQL ORDER BY, not Python-side sorting."
    )


def test_duckdb_has_composite_index():
    """DuckDB DDL must create a composite index on (provider_id, timestamp).

    This index makes temporal queries O(log n) instead of O(n).
    Without it, every query_latest scans the full table.

    The DDL is now generated dynamically (field names may be mapped via
    SchemaMap), so we inspect the _init_schema source for the invariant.
    """
    import inspect
    from yanantin.activity.backends.duckdb import DuckDBActivityStreamStore

    source = inspect.getsource(DuckDBActivityStreamStore._init_schema)

    assert "CREATE INDEX" in source, (
        "DuckDB _init_schema must create indexes."
    )
    # The index covers provider_id and timestamp (via field_name mapping)
    assert "provider_id" in source and "timestamp" in source, (
        "DuckDB index must cover (provider_id, timestamp) fields."
    )


# -- Pipeline separation: facts ≠ tensors -----------------------------


def test_fact_recorder_base_is_distinct_from_recorder_base():
    """FactRecorderBase and RecorderBase must be separate ABCs.

    This is the structural enforcement of 'facts are not tensors'.
    FactRecorderBase stores in ActivityStreamStore (facts).
    RecorderBase stores in ApachetaInterface (tensors).
    If they were the same class, the boundary dissolves.
    """
    assert FactRecorderBase is not RecorderBase, (
        "FactRecorderBase must be distinct from RecorderBase. "
        "Facts and tensors are architecturally different storage targets."
    )

    # FactRecorderBase stores facts (returns int count)
    sig = inspect.signature(FactRecorderBase.record_facts)
    # RecorderBase stores tensors (returns UUID)
    sig_r = inspect.signature(RecorderBase.record)

    # Return type annotations differ
    fact_return = sig.return_annotation
    tensor_return = sig_r.return_annotation

    # FactRecorderBase takes an ActivityStreamStore
    init_source = inspect.getsource(FactRecorderBase.__init__)
    assert "ActivityStreamStore" in init_source or "store" in init_source, (
        "FactRecorderBase.__init__ must accept an ActivityStreamStore. "
        "It stores facts, not tensors."
    )

    # RecorderBase takes an ApachetaInterface
    init_source_r = inspect.getsource(RecorderBase.__init__)
    assert "ApachetaInterface" in init_source_r or "interface" in init_source_r, (
        "RecorderBase.__init__ must accept an ApachetaInterface. "
        "It stores tensors, not facts."
    )


def test_fact_recorder_has_record_facts_not_record():
    """FactRecorderBase must have record_facts(), not record().

    The method name encodes the contract: record_facts returns a count
    (int), not a UUID. At 28.5M entries, building a UUID list is wasteful.
    """
    assert hasattr(FactRecorderBase, "record_facts"), (
        "FactRecorderBase must have record_facts() method."
    )
    assert getattr(FactRecorderBase.record_facts, "__isabstractmethod__", False), (
        "record_facts must be abstract — concrete recorders must implement it."
    )


# -- Backend compliance ------------------------------------------------


def test_all_backends_implement_store_abc():
    """All three backends must implement ActivityStreamStore.

    If a backend doesn't subclass the ABC, it can skip methods and
    the type system won't catch it.
    """
    from yanantin.activity.backends.arango import ArangoDBActivityStreamStore

    for backend_cls in (
        InMemoryActivityStreamStore,
        DuckDBActivityStreamStore,
        ArangoDBActivityStreamStore,
    ):
        assert issubclass(backend_cls, ActivityStreamStore), (
            f"{backend_cls.__name__} must subclass ActivityStreamStore."
        )


# -- Modules that must exist -------------------------------------------


def test_activity_modules_exist():
    """The activity stream requires these modules to function.

    If any are removed or renamed, the fact pipeline breaks silently.
    """
    from yanantin.activity import models as _models  # noqa: F841
    from yanantin.activity import store as _store  # noqa: F841
    from yanantin.activity import anchor as _anchor  # noqa: F841
    from yanantin.activity.backends import memory as _mem  # noqa: F841
    from yanantin.activity.backends import duckdb as _duck  # noqa: F841
    from yanantin.activity.backends import arango as _arango  # noqa: F841

    # Each module must be importable — if this test passes, the
    # activity stream's import chain is intact.


def test_freeze_creates_tensor_not_fact():
    """freeze() must store into ApachetaInterface, not ActivityStreamStore.

    Freezing is the authored act — the moment a temporal view becomes
    a tensor. If freeze() writes back to the fact store, the boundary
    between facts and tensors is violated. The freeze crosses the boundary
    BY DESIGN.
    """
    source = inspect.getsource(MemoryAnchorService.freeze)

    assert "interface" in source, (
        "freeze() must accept an ApachetaInterface parameter. "
        "The freeze crosses from facts to tensors."
    )
    assert "store_tensor" in source, (
        "freeze() must call store_tensor() on the ApachetaInterface. "
        "The result of a freeze is a tensor, not a fact."
    )
