"""Run the Jabberwock NER system.

    uv run python -m yanantin.jabberwock                          # status
    uv run python -m yanantin.jabberwock bootstrap                # bootstrap root
    uv run python -m yanantin.jabberwock create                   # new entity
    uv run python -m yanantin.jabberwock observe <id> name Alice  # observe
    uv run python -m yanantin.jabberwock alias <id> email a@b.c   # alias
    uv run python -m yanantin.jabberwock resolve email a@b.c      # resolve
    uv run python -m yanantin.jabberwock show <id>                # full view
    uv run python -m yanantin.jabberwock unresolved               # mome vorpals
    uv run python -m yanantin.jabberwock claim <rec> <entity>     # claim mome
    uv run python -m yanantin.jabberwock group add <id> <grp> role
    uv run python -m yanantin.jabberwock group members <grp>

Default store: duckdb (deliberate -- testing path that paves the way for ArangoDB).
"""

from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

_STORE_CHOICES = ["memory", "duckdb", "arango"]
_LINE = "\u2500" * 38


def _parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        print(f"  Error: '{value}' is not a valid UUID", file=sys.stderr)
        sys.exit(1)


def _entity_id(value: str) -> UUID | None:
    """Parse entity ID; 'mome' -> None."""
    return None if value.lower() == "mome" else _parse_uuid(value)


def _provider(args: argparse.Namespace) -> UUID | None:
    p = getattr(args, "provider", None)
    return _parse_uuid(p) if p else None


def _open(args: argparse.Namespace):
    from yanantin.collector.pipeline import open_store
    from yanantin.jabberwock import Brillig
    store = open_store(args.store)
    brillig = Brillig(store)
    brillig.bootstrap()
    return store, brillig


def _out(args, title: str, data: dict, lines: list[str]) -> None:
    """Unified output: JSON or text with header."""
    if args.json:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"\n  Jabberwock \u2014 {title}\n  {_LINE}")
        for line in lines:
            print(line)
        print()


def _fmt_frabjous(f) -> tuple[dict, list[str]]:
    data = f.model_dump(mode="json")
    lines = [
        f"  Entity: {f.jabberwock.id}",
        f"  Created: {f.jabberwock.brillig.isoformat()}",
        f"  Provider: {f.jabberwock.bandersnatch}",
    ]
    if f.toves:
        lines.append(f"  Aliases ({len(f.toves)}):")
        lines.extend(f"    {t.wabe}:{t.gimble}" for t in f.toves)
    if f.vorpals:
        lines.append(f"  Observations ({len(f.vorpals)}):")
        lines.extend(f"    {v.tulgey}:{v.snicker_snack}" for v in f.vorpals)
    if f.raths:
        lines.append(f"  Memberships ({len(f.raths)}):")
        lines.extend(f"    {r.borogove_id}:{r.mimsy}" for r in f.raths)
    lines.append(f"  Evidence: {len(f.evidence_ids)} records")
    lines.append(f"  Resolved: {f.callooh.isoformat()}")
    return data, lines


# -- Subcommand handlers ---------------------------------------------------


def _cmd_default(args: argparse.Namespace) -> None:
    from yanantin.collector.pipeline import open_store
    from yanantin.jabberwock import (
        JABBERWOCK_PROVIDER, RATH_PROVIDER, TOVE_PROVIDER, VORPAL_PROVIDER, Brillig,
    )
    store = open_store(args.store)
    brillig = Brillig(store)
    root = brillig.bootstrap()
    c = {
        "entities": len(list(store.query_range(provider_id=JABBERWOCK_PROVIDER))),
        "aliases": len(list(store.query_range(provider_id=TOVE_PROVIDER))),
        "observations": len(list(store.query_range(provider_id=VORPAL_PROVIDER))),
        "memberships": len(list(store.query_range(provider_id=RATH_PROVIDER))),
    }
    mome = len(brillig.mome_vorpals())
    _out(args, "NER", {"root": str(root.id), "backend": args.store, **c, "unresolved": mome}, [
        f"  Backend:      {args.store}",
        f"  Root:         {root.id}",
        f"  Entities:     {c['entities']}",
        f"  Aliases:      {c['aliases']}",
        f"  Observations: {c['observations']}",
        f"  Memberships:  {c['memberships']}",
        f"  Unresolved:   {mome}",
    ])


def _cmd_bootstrap(args: argparse.Namespace) -> None:
    _, brillig = _open(args)
    root = brillig.bootstrap()
    _out(args, "Bootstrap",
         {"root": str(root.id), "created": root.brillig.isoformat()},
         [f"  Root: {root.id}", f"  Created: {root.brillig.isoformat()}"])


def _cmd_create(args: argparse.Namespace) -> None:
    _, brillig = _open(args)
    entity = brillig.beamish(bandersnatch=_provider(args))
    _out(args, "Create",
         {"id": str(entity.id), "created": entity.brillig.isoformat()},
         [f"  Entity: {entity.id}", f"  Created: {entity.brillig.isoformat()}"])


def _cmd_observe(args: argparse.Namespace) -> None:
    _, brillig = _open(args)
    v = brillig.outgrabe(
        jabberwock_id=_entity_id(args.entity_id),
        tulgey=args.category, snicker_snack=args.value,
        bandersnatch=_provider(args),
    )
    target = str(v.jabberwock_id) if v.jabberwock_id else None
    _out(args, "Observe",
         {"id": str(v.id), "entity": target, "category": v.tulgey, "value": v.snicker_snack},
         [f"  Vorpal: {v.id}", f"  Entity: {target or 'mome'}", f"  {v.tulgey}: {v.snicker_snack}"])


def _cmd_alias(args: argparse.Namespace) -> None:
    _, brillig = _open(args)
    t = brillig.slithy(
        jabberwock_id=_entity_id(args.entity_id),
        wabe=args.namespace, gimble=args.identifier,
        bandersnatch=_provider(args),
    )
    target = str(t.jabberwock_id) if t.jabberwock_id else None
    _out(args, "Alias",
         {"id": str(t.id), "entity": target, "namespace": t.wabe, "identifier": t.gimble},
         [f"  Tove: {t.id}", f"  Entity: {target or 'mome'}", f"  {t.wabe}:{t.gimble}"])


def _cmd_resolve(args: argparse.Namespace) -> None:
    from yanantin.jabberwock import Frabjous
    _, brillig = _open(args)
    result = brillig.galumph(args.namespace, args.identifier)
    if isinstance(result, Frabjous):
        data, lines = _fmt_frabjous(result)
        _out(args, "Resolve (Frabjous)", data, lines)
    else:
        data = result.model_dump(mode="json")
        lines = [
            f"  Matching toves: {len(result.toves)}",
            f"  Candidates: {len(result.candidates)}",
            f"  Unresolved observations: {len(result.mome_vorpals)}",
        ]
        for t in result.toves:
            lines.append(f"    {t.wabe}:{t.gimble} -> {t.jabberwock_id or 'mome'}")
        _out(args, "Resolve (Mome)", data, lines)


def _cmd_show(args: argparse.Namespace) -> None:
    _, brillig = _open(args)
    try:
        f = brillig.uffish(_parse_uuid(args.entity_id))
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        sys.exit(1)
    data, lines = _fmt_frabjous(f)
    _out(args, "Show", data, lines)


def _cmd_unresolved(args: argparse.Namespace) -> None:
    _, brillig = _open(args)
    momes = brillig.mome_vorpals()
    data = [{"id": str(v.id), "category": v.tulgey, "value": v.snicker_snack,
             "observed": v.brillig.isoformat()} for v in momes]
    if not momes:
        _out(args, "Unresolved", data, ["  No unresolved observations."])
    else:
        lines = [f"  Count: {len(momes)}"]
        lines.extend(f"    [{v.tulgey}] {v.snicker_snack}  ({v.id})" for v in momes)
        _out(args, "Unresolved", data, lines)


def _cmd_claim(args: argparse.Namespace) -> None:
    _, brillig = _open(args)
    rec = _parse_uuid(args.record_id)
    eid = _parse_uuid(args.entity_id)
    v = brillig.claim_mome(record_id=rec, jabberwock_id=eid, bandersnatch=_provider(args))
    _out(args, "Claim",
         {"claim_id": str(v.id), "record_id": str(rec), "entity_id": str(eid)},
         [f"  Claim: {v.id}", f"  Record: {rec}", f"  Entity: {eid}"])


def _cmd_group_add(args: argparse.Namespace) -> None:
    _, brillig = _open(args)
    eid, gid = _parse_uuid(args.entity_id), _parse_uuid(args.group_id)
    r = brillig.add_rath(jabberwock_id=eid, borogove_id=gid, mimsy=args.role,
                         bandersnatch=_provider(args))
    _out(args, "Group Add",
         {"id": str(r.id), "entity": str(eid), "group": str(gid), "role": r.mimsy},
         [f"  Rath: {r.id}", f"  Entity: {eid}", f"  Group: {gid}", f"  Role: {r.mimsy}"])


def _cmd_group_members(args: argparse.Namespace) -> None:
    _, brillig = _open(args)
    gid = _parse_uuid(args.group_id)
    members = brillig.whiffling(gid)
    if args.json:
        all_data = [_fmt_frabjous(m)[0] for m in members]
        print(json.dumps(all_data, indent=2, default=str))
    else:
        lines = [f"  Group: {gid}", f"  Members: {len(members)}"]
        for m in members:
            _, mlines = _fmt_frabjous(m)
            lines.append("")
            lines.extend(mlines)
            lines.append("  " + "\u2500" * 20)
        _out(args, "Group Members", {}, lines)


# -- Parser ----------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Jabberwock \u2014 Named Entity Resolution")
    parser.add_argument("--store", choices=_STORE_CHOICES, default="duckdb",
                        help="Backend store (default: duckdb)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("bootstrap", help="Bootstrap root entity")

    p = sub.add_parser("create", help="Create a new entity")
    p.add_argument("--provider", default=None, help="Provider UUID (default: root)")

    p = sub.add_parser("observe", help="Observe a fact about an entity")
    p.add_argument("entity_id", help="Entity UUID or 'mome'")
    p.add_argument("category", help="Observation category (tulgey)")
    p.add_argument("value", help="Observation value (snicker_snack)")
    p.add_argument("--provider", default=None, help="Provider UUID (default: root)")

    p = sub.add_parser("alias", help="Create an alias for an entity")
    p.add_argument("entity_id", help="Entity UUID or 'mome'")
    p.add_argument("namespace", help="Namespace (wabe)")
    p.add_argument("identifier", help="Identifier (gimble)")
    p.add_argument("--provider", default=None, help="Provider UUID (default: root)")

    p = sub.add_parser("resolve", help="Resolve entity by alias")
    p.add_argument("namespace", help="Namespace (wabe)")
    p.add_argument("identifier", help="Identifier (gimble)")

    p = sub.add_parser("show", help="Show full entity view")
    p.add_argument("entity_id", help="Entity UUID")

    sub.add_parser("unresolved", help="List unresolved observations")

    p = sub.add_parser("claim", help="Connect mome record to entity")
    p.add_argument("record_id", help="Mome record UUID")
    p.add_argument("entity_id", help="Target entity UUID")
    p.add_argument("--provider", default=None, help="Provider UUID (default: root)")

    gp = sub.add_parser("group", help="Group operations")
    gsub = gp.add_subparsers(dest="group_command")
    p = gsub.add_parser("add", help="Add membership edge")
    p.add_argument("entity_id", help="Member entity UUID")
    p.add_argument("group_id", help="Group entity UUID")
    p.add_argument("role", help="Role within group (mimsy)")
    p.add_argument("--provider", default=None, help="Provider UUID (default: root)")
    p = gsub.add_parser("members", help="Show group members")
    p.add_argument("group_id", help="Group entity UUID")

    args = parser.parse_args()
    handlers = {
        None: _cmd_default, "bootstrap": _cmd_bootstrap, "create": _cmd_create,
        "observe": _cmd_observe, "alias": _cmd_alias, "resolve": _cmd_resolve,
        "show": _cmd_show, "unresolved": _cmd_unresolved, "claim": _cmd_claim,
    }
    if args.command in handlers:
        handlers[args.command](args)
    elif args.command == "group":
        gc = getattr(args, "group_command", None)
        if gc == "add":
            _cmd_group_add(args)
        elif gc == "members":
            _cmd_group_members(args)
        else:
            gp.print_help()


if __name__ == "__main__":
    main()
