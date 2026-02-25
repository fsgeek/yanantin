"""Run the Yanantin query pipeline.

    uv run python -m yanantin.query --store duckdb --stats
    uv run python -m yanantin.query --store arango --providers
    uv run python -m yanantin.query --store duckdb --provider <uuid>
    uv run python -m yanantin.query --store duckdb --provider <uuid> --after 2026-02-20
    uv run python -m yanantin.query --store duckdb --search "config" --field path
    uv run python -m yanantin.query --store arango --search "*.py" --field path --glob
    uv run python -m yanantin.query --store arango --summarize
    uv run python -m yanantin.query --store duckdb --json --record

Environment variables for ArangoDB backend:
    YANANTIN_ARANGO_HOST     (default: http://localhost:8529)
    YANANTIN_ARANGO_DB       (default: apacheta)
    YANANTIN_ARANGO_USER     (default: "")
    YANANTIN_ARANGO_PASSWORD (default: "")

Environment variables for DuckDB backend:
    YANANTIN_DUCKDB_PATH     (default: ~/.local/share/yanantin/activity.duckdb)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from uuid import UUID

from yanantin.query.models import ContentFilter, QuerySpec


_STORE_CHOICES = ["memory", "duckdb", "arango"]


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO datetime string into a timezone-aware datetime."""
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_uuid(value: str | None) -> UUID | None:
    """Parse a UUID string, or return None."""
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        print(f"  Error: '{value}' is not a valid UUID", file=sys.stderr)
        sys.exit(1)


def _print_stats(stats: dict, as_json: bool) -> None:
    """Print store statistics."""
    if as_json:
        print(json.dumps(stats, indent=2))
    else:
        print()
        print("  Query Pipeline \u2014 Store Statistics")
        print("  " + "\u2500" * 40)
        print(f"  Total facts: {stats['total_facts']:,}")
        print(f"  Providers:   {stats['provider_count']}")
        print()
        if stats["providers"]:
            print("  Per provider:")
            for pid, count in stats["providers"].items():
                print(f"    {pid}  ({count:,} facts)")
            print()


def _print_providers(providers: list[dict], as_json: bool) -> None:
    """Print provider listing."""
    if as_json:
        print(json.dumps(providers, indent=2))
    else:
        print()
        print("  Query Pipeline \u2014 Providers")
        print("  " + "\u2500" * 40)
        if not providers:
            print("  No providers found.")
        else:
            for p in providers:
                print(f"  {p['provider_id']}  ({p['fact_count']:,} facts)")
        print()


def _print_result(result, as_json: bool) -> None:
    """Print query results."""
    from yanantin.query.models import QueryResult

    if as_json:
        print(result.model_dump_json(indent=2))
    else:
        print()
        print("  Query Pipeline \u2014 Results")
        print("  " + "\u2500" * 40)
        print(f"  Query ID:    {result.query_id}")
        print(f"  Matched:     {result.total_matched:,}")
        print(f"  Returned:    {result.returned_count:,}")
        print(f"  Time:        {result.execution_time_ms:.1f}ms")
        print()

        if result.summary:
            s = result.summary
            print("  Summary:")
            print(f"    Total:      {s.total_count:,}")
            print(f"    Providers:  {len(s.providers)}")
            if s.time_range:
                print(f"    From:       {s.time_range[0].isoformat()}")
                print(f"    To:         {s.time_range[1].isoformat()}")
            if s.sample_data_keys:
                print(f"    Data keys:  {', '.join(s.sample_data_keys)}")
            if s.top_content_hashes:
                print("    Top hashes:")
                for h, c in list(s.top_content_hashes.items())[:5]:
                    print(f"      {h}: {c:,}")
            print()

        if result.facts:
            print("  Facts:")
            for f in result.facts[:20]:
                ts = f.get("timestamp", "?")
                pid = f.get("provider_id", "?")
                keys = list(f.get("data", {}).keys())
                print(f"    [{ts}] provider={pid[:12]}... keys={keys}")
            if len(result.facts) > 20:
                print(f"    ... and {len(result.facts) - 20} more")
            print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query pipeline \u2014 structured queries against the activity stream",
    )
    parser.add_argument(
        "--store", choices=_STORE_CHOICES, required=True,
        help="Backend to query (memory, duckdb, arango)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--record", action="store_true", help="Record query as a fact")

    # Mode flags
    parser.add_argument("--stats", action="store_true", help="Show store statistics")
    parser.add_argument("--providers", action="store_true", help="List providers")

    # Query construction
    parser.add_argument("--provider", default=None, help="Filter by provider UUID")
    parser.add_argument("--after", default=None, help="Start time (ISO datetime)")
    parser.add_argument("--before", default=None, help="End time (ISO datetime)")
    parser.add_argument("--search", default=None, help="Content search value")
    parser.add_argument("--field", default=None, help="Field dot-path for content filter")
    parser.add_argument("--glob", action="store_true", help="Use glob matching for --search")
    parser.add_argument("--content-hash", default=None, help="Filter by content hash")
    parser.add_argument("--limit", type=int, default=100, help="Max results (default: 100)")
    parser.add_argument("--offset", type=int, default=0, help="Result offset for pagination")
    parser.add_argument("--summarize", action="store_true", help="Return summary instead of facts")

    args = parser.parse_args()

    from yanantin.collector.pipeline import open_store
    from yanantin.query.engine import QueryEngine

    store = open_store(args.store)
    engine = QueryEngine(store)

    # Stats mode
    if args.stats:
        stats = engine.get_stats()
        _print_stats(stats, args.json)
        if args.record:
            _record_stats_query(store, args)
        return

    # Providers mode
    if args.providers:
        providers = engine.list_providers()
        _print_providers(providers, args.json)
        return

    # Build a QuerySpec from CLI args
    content_filters: list[ContentFilter] = []
    if args.search is not None:
        if args.field is None:
            print("  Error: --search requires --field", file=sys.stderr)
            sys.exit(1)
        op = "glob" if args.glob else "contains"
        content_filters.append(ContentFilter(field=args.field, op=op, value=args.search))

    spec = QuerySpec(
        provider_id=_parse_uuid(args.provider),
        start=_parse_datetime(args.after),
        end=_parse_datetime(args.before),
        content_filters=tuple(content_filters),
        content_hash=args.content_hash,
        limit=args.limit,
        offset=args.offset,
        summarize=args.summarize,
    )

    result = engine.execute(spec)
    _print_result(result, args.json)

    if args.record:
        from yanantin.query.recorder import QueryFactRecorder

        recorder = QueryFactRecorder(store)
        fact_id = recorder.record_query(result)
        if args.json:
            print(json.dumps({"recorded": True, "fact_id": str(fact_id)}))
        else:
            print(f"  Recorded query as fact {fact_id}")
            print()


def _record_stats_query(store, args) -> None:
    """Record a stats query as a fact."""
    from yanantin.query.models import QueryResult, QuerySpec
    from yanantin.query.recorder import QueryFactRecorder

    # Create a minimal QueryResult for the stats call
    spec = QuerySpec(summarize=True)
    result = QueryResult(
        query_id=spec.id,
        spec=spec,
        total_matched=0,
        returned_count=0,
        execution_time_ms=0.0,
    )

    recorder = QueryFactRecorder(store)
    fact_id = recorder.record_query(result)
    if args.json:
        print(json.dumps({"recorded": True, "fact_id": str(fact_id)}))
    else:
        print(f"  Recorded query as fact {fact_id}")
        print()


if __name__ == "__main__":
    main()
