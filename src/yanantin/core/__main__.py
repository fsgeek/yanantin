"""CLI for the C0 registration catalog — the first ledger-shaped read tool.

Usage: uv run python -m yanantin.core [--tier test|app] [--json] [list|show <uuid>]

Reads through RegistrationService (the seam that owns the catalog name), never
naming a collection. 'list' shows what has registered; 'show <uuid>' one record.
"""

from __future__ import annotations

import argparse
import json
import sys
from uuid import UUID

from yanantin.core.registration import RegistrationService
from yanantin.infra.config import ApachetaDBConfig


def _row(rec, contributions: int) -> dict:
    # contributes_to lives in the open tail (extra="allow"); the registrar
    # stores it opaquely, the CLI only reads it back. Absent ⇒ [].
    extra = rec.model_extra or {}
    return {
        "registrant_id": str(rec.registrant_id),
        "registrant_name": rec.registrant_name,
        "registrant_kind": rec.registrant_kind,
        "parent_id": str(rec.parent_id) if rec.parent_id else None,
        "contributions": contributions,
        "contributes_to": extra.get("contributes_to", []),
        "description": rec.description,
    }


def _cmd_list(svc: RegistrationService, args: argparse.Namespace) -> None:
    records = svc.get_registrant_list()
    rows = [_row(r, svc.contribution_count(r.registrant_id)) for r in records]
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    if not rows:
        print("(no registrants)")
        return
    header = f"{'name':<24} {'kind':<10} {'contribs':>8}  uuid"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['registrant_name']:<24} {row['registrant_kind']:<10} "
            f"{row['contributions']:>8}  {row['registrant_id']}"
        )


def _cmd_show(svc: RegistrationService, args: argparse.Namespace) -> None:
    rec = svc.lookup_by_identifier(UUID(args.uuid))
    if rec is None:
        msg = f"no registrant with id {args.uuid}"
        if args.json:
            print(json.dumps({"error": msg}))
        else:
            print(msg, file=sys.stderr)
        sys.exit(1)
    row = _row(rec, svc.contribution_count(rec.registrant_id))
    if args.json:
        print(json.dumps(row, indent=2))
        return
    for k, v in row.items():
        print(f"  {k}: {v}")


def main(argv: list[str] | None = None, service: RegistrationService | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="yanantin.core", description="Inspect the C0 registration catalog"
    )
    parser.add_argument("--tier", choices=["test", "app"], default="test",
                        help="DB credential tier (default: test)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="List what has registered (default)")
    p = sub.add_parser("show", help="Show one registrant by UUID")
    p.add_argument("uuid", help="Registrant UUID")
    args = parser.parse_args(argv)

    if service is None:
        service = RegistrationService(db=ApachetaDBConfig().connect(tier=args.tier))

    if args.command == "show":
        _cmd_show(service, args)
    else:  # None (default) or "list"
        _cmd_list(service, args)


if __name__ == "__main__":
    main()
