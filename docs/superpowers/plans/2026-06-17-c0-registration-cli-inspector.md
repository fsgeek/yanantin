# C0 Registration CLI Inspector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first ledger-shaped read tool for yanantin — a CLI that lists what has registered in the C0 base catalog, going through a library seam that owns the well-known catalog name so the CLI never speaks a collection name.

**Architecture:** Add a thin `RegistrationService` to `core/registration.py` (the Indaleko `get_provider_list()` seam, minus any persisted service-UUID) that owns the semantic constant `"core_registrants"` in code and reaches it only through the obfuscator's `collection_name()`. Add `src/yanantin/core/__main__.py` as a house-style argparse CLI that constructs the service over a live DB handle and prints the registrant table. The opaque collection name is the only per-installation anchor at rest — no new obfuscator verb, no service-identity value persisted.

**Tech Stack:** Python 3.14, uv-managed, ArangoDB (python-arango driver), pydantic, pytest.

## Global Constraints

- Python 3.14, uv-managed; run tests with `uv run pytest`.
- Builder/tester separation is CI-enforced; red-bar tests live in `tests/red_bar/`.
- Live DB tests run against `apacheta_test` (test-tier creds), marked `pytestmark = pytest.mark.integration`. Do NOT mock the DB for storage behavior.
- The base catalog semantic name `"core_registrants"` is a constant **in code only**; it must reach storage only through `obfuscator.collection_name()`. No naked semantic constant at rest.
- No new obfuscator verb. No persisted base-service UUID (rejected in the spec).
- Match existing CLI house style: `argparse`, `cmd_*`/`_cmd_*` handlers, `def main(...)`, `uv run python -m yanantin.<pkg>`, a `--json` flag.
- Frequent commits: one commit per task.

---

### Task 1: `RegistrationService` — the catalog seam

**Files:**
- Modify: `src/yanantin/core/registration.py` (append a module constant + class after `Registrar`)
- Test: `tests/integration/test_core_registration_service.py` (create)

**Interfaces:**
- Consumes (from existing `Registrar`, already in the file):
  - `Registrar(db: StandardDatabase, catalog_collection: str, name: str, description: str, obfuscator: StorageObfuscator | None = None, owned_collection: str | None = None)`
  - `Registrar.register(registrant_id: UUID, registrant_name: str, registrant_kind: str, description: str, **extra) -> RegistrantRecord`
  - `Registrar.lookup_by_identifier(registrant_id: UUID) -> RegistrantRecord | None`
  - `Registrar.list_registrants() -> list[RegistrantRecord]`
  - `Registrar.list_contributions(contributor_id: UUID | None = None) -> list[dict]`
- Produces (later tasks rely on these exact names/types):
  - module constant `BASE_REGISTRANT_CATALOG: str = "core_registrants"`
  - `RegistrationService(db: StandardDatabase, obfuscator: StorageObfuscator | None = None)`
  - `RegistrationService.base_registrar -> Registrar` (attribute, exposes `register` for tests/tools)
  - `RegistrationService.get_registrant_list() -> list[RegistrantRecord]`
  - `RegistrationService.lookup_by_identifier(registrant_id: UUID) -> RegistrantRecord | None`
  - `RegistrationService.lookup_by_name(name: str) -> RegistrantRecord | None`
  - `RegistrationService.contribution_count(registrant_id: UUID) -> int`

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_core_registration_service.py`. Reuse the live-handle pattern from `tests/integration/test_core_registration.py` (the `live_db` fixture builds a real `apacheta_test` handle).

```python
"""RegistrationService — the catalog seam the CLI reads through (gh #1, C0)."""

import uuid

import pytest

from yanantin.core.registration import (
    BASE_REGISTRANT_CATALOG,
    RegistrationService,
)
from yanantin.infra.config import ApachetaDBConfig, get_database

pytestmark = pytest.mark.integration


@pytest.fixture
def live_db():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return get_database(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=creds["username"],
        password=creds["password"],
    )


class _PrefixObfuscator:
    """Non-transparent stand-in: rewrites collection AND field names so the
    base catalog lands under a unique, isolated, obfuscated name per test."""

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    def collection_name(self, semantic: str) -> str:
        return f"{self._prefix}{semantic}"

    def field_name(self, semantic: str) -> str:
        return f"{self._prefix}{semantic}"

    def field_path(self, parts):
        return ".".join(self.field_name(p) for p in parts)

    def reverse_field(self, opaque: str) -> str:
        return opaque[len(self._prefix):] if opaque.startswith(self._prefix) else opaque

    def obfuscate_document(self, doc: dict) -> dict:
        return {(k if k.startswith("_") else self.field_name(k)): v for k, v in doc.items()}

    def deobfuscate_document(self, doc: dict) -> dict:
        return {(k if k.startswith("_") else self.reverse_field(k)): v for k, v in doc.items()}

    @property
    def is_transparent(self) -> bool:
        return False


@pytest.fixture
def service(live_db):
    """A RegistrationService whose base catalog is an isolated obfuscated
    collection, torn down after."""
    obf = _PrefixObfuscator(f"svc_{uuid.uuid4().hex}_")
    svc = RegistrationService(db=live_db, obfuscator=obf)
    yield svc
    stored = obf.collection_name(BASE_REGISTRANT_CATALOG)
    if live_db.has_collection(stored):
        live_db.delete_collection(stored)


def test_base_catalog_created_on_construction(service, live_db):
    obf = service.base_registrar._obfuscator
    stored = obf.collection_name(BASE_REGISTRANT_CATALOG)
    assert live_db.has_collection(stored)


def test_round_trips_a_registrant_through_all_three_verbs(service):
    rid = uuid.uuid4()
    service.base_registrar.register(
        registrant_id=rid,
        registrant_name="linux-local-fs",
        registrant_kind="provider",
        description="local filesystem storage provider",
    )
    listed = service.get_registrant_list()
    assert [r.registrant_id for r in listed] == [rid]
    assert service.lookup_by_identifier(rid).registrant_name == "linux-local-fs"
    assert service.lookup_by_name("linux-local-fs").registrant_id == rid


def test_lookup_by_name_unknown_returns_none_not_raise(service):
    assert service.lookup_by_name("no-such-provider") is None


def test_contribution_count_reflects_contributions(service):
    rid = uuid.uuid4()
    service.base_registrar.register(
        registrant_id=rid,
        registrant_name="counter",
        registrant_kind="provider",
        description="contributes twice",
    )
    assert service.contribution_count(rid) == 0
    service.base_registrar.contribute(contributor_id=rid, path="/a")
    service.base_registrar.contribute(contributor_id=rid, path="/b")
    assert service.contribution_count(rid) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_core_registration_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'BASE_REGISTRANT_CATALOG'` / `RegistrationService`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/yanantin/core/registration.py` (after the `Registrar` class). The service owns the semantic catalog name and delegates; `lookup_by_name` filters the listed records on the unobfuscated `registrant_name` value; `contribution_count` counts the base registrar's owned-collection contributions for that id.

```python
BASE_REGISTRANT_CATALOG = "core_registrants"
"""Semantic name of the base catalog. A constant IN CODE only — it reaches
storage solely through obfuscator.collection_name(), so the per-installation
opaque name is the only anchor at rest (no persisted service-UUID; the threat
model is third-party-custodian compromise, see the design doc)."""


class RegistrationService:
    """The Indaleko get_provider_list() seam: owns the well-known base-catalog
    name so callers (the CLI, future tools) never speak a collection name.

    Minus Indaleko's persisted service_uuid — yanantin persists no service
    identity; the opaque base-catalog name is the per-installation anchor.
    """

    def __init__(
        self,
        db: StandardDatabase,
        obfuscator: StorageObfuscator | None = None,
    ) -> None:
        self.base_registrar = Registrar(
            db=db,
            catalog_collection=BASE_REGISTRANT_CATALOG,
            name="core registration service",
            description="the base registrant catalog",
            obfuscator=obfuscator,
        )

    def get_registrant_list(self) -> list[RegistrantRecord]:
        """Every registrant in the base catalog (the get_provider_list verb)."""
        return self.base_registrar.list_registrants()

    def lookup_by_identifier(self, registrant_id: UUID) -> RegistrantRecord | None:
        return self.base_registrar.lookup_by_identifier(registrant_id)

    def lookup_by_name(self, name: str) -> RegistrantRecord | None:
        """First registrant whose name matches, or None. Names are values
        (unobfuscated), so this is a cheap match over the listed records —
        the verb a human inspector wants (names, not UUIDs)."""
        for r in self.get_registrant_list():
            if r.registrant_name == name:
                return r
        return None

    def contribution_count(self, registrant_id: UUID) -> int:
        """How many data records this registrant owns in the base registrar's
        owned collection. The one place v1 touches the data path — a count
        column for the inspector, not a dump."""
        return len(self.base_registrar.list_contributions(registrant_id))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_core_registration_service.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/core/registration.py tests/integration/test_core_registration_service.py
git commit -m "feat(c0): RegistrationService — the catalog seam the CLI reads through"
```

---

### Task 2: `core` CLI — list and show

**Files:**
- Create: `src/yanantin/core/__main__.py`
- Test: `tests/integration/test_core_cli.py` (create)

**Interfaces:**
- Consumes (from Task 1 and existing config):
  - `RegistrationService(db, obfuscator=None)`, `.get_registrant_list()`, `.lookup_by_identifier(UUID)`, `.contribution_count(UUID)`, `.base_registrar`
  - `RegistrantRecord` fields: `registrant_id: UUID`, `registrant_name: str`, `registrant_kind: str`, `description: str`, `parent_id: UUID | None`
  - `ApachetaDBConfig().connect(tier: str) -> StandardDatabase` (tier in `{"test","app"}`)
- Produces:
  - `main(argv: list[str] | None = None) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_core_cli.py`. Drive `main()` with an explicit argv (no `sys.argv` monkeypatch needed), capture stdout via `capsys`. The CLI must accept an injected service for testability so the test points it at an isolated, torn-down catalog rather than the shared default `core_registrants`.

```python
"""core CLI — the first ledger-shaped read tool (gh #1, C0)."""

import json
import uuid

import pytest

from yanantin.core.__main__ import main
from yanantin.core.registration import BASE_REGISTRANT_CATALOG, RegistrationService
from yanantin.infra.config import ApachetaDBConfig, get_database

pytestmark = pytest.mark.integration


class _PrefixObfuscator:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    def collection_name(self, semantic: str) -> str:
        return f"{self._prefix}{semantic}"

    def field_name(self, semantic: str) -> str:
        return f"{self._prefix}{semantic}"

    def field_path(self, parts):
        return ".".join(self.field_name(p) for p in parts)

    def reverse_field(self, opaque: str) -> str:
        return opaque[len(self._prefix):] if opaque.startswith(self._prefix) else opaque

    def obfuscate_document(self, doc: dict) -> dict:
        return {(k if k.startswith("_") else self.field_name(k)): v for k, v in doc.items()}

    def deobfuscate_document(self, doc: dict) -> dict:
        return {(k if k.startswith("_") else self.reverse_field(k)): v for k, v in doc.items()}

    @property
    def is_transparent(self) -> bool:
        return False


@pytest.fixture
def populated_service():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    db = get_database(
        host=cfg.host_url, db_name="apacheta_test",
        username=creds["username"], password=creds["password"],
    )
    obf = _PrefixObfuscator(f"cli_{uuid.uuid4().hex}_")
    svc = RegistrationService(db=db, obfuscator=obf)
    rid = uuid.uuid4()
    svc.base_registrar.register(
        registrant_id=rid, registrant_name="linux-local-fs",
        registrant_kind="provider", description="local fs provider",
    )
    yield svc, rid
    stored = obf.collection_name(BASE_REGISTRANT_CATALOG)
    if db.has_collection(stored):
        db.delete_collection(stored)


def test_list_prints_registrant_name(populated_service, capsys):
    svc, _ = populated_service
    main(["list"], service=svc)
    out = capsys.readouterr().out
    assert "linux-local-fs" in out


def test_list_is_default_command(populated_service, capsys):
    svc, _ = populated_service
    main([], service=svc)
    assert "linux-local-fs" in capsys.readouterr().out


def test_list_json_parses_and_carries_fields(populated_service, capsys):
    svc, rid = populated_service
    main(["--json", "list"], service=svc)
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["registrant_name"] == "linux-local-fs"
    assert rows[0]["registrant_id"] == str(rid)
    assert rows[0]["contributions"] == 0


def test_show_prints_full_record(populated_service, capsys):
    svc, rid = populated_service
    main(["show", str(rid)], service=svc)
    out = capsys.readouterr().out
    assert "linux-local-fs" in out
    assert "local fs provider" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_core_cli.py -v`
Expected: FAIL — `ModuleNotFoundError`/`ImportError` for `yanantin.core.__main__.main`.

- [ ] **Step 3: Write minimal implementation**

Create `src/yanantin/core/__main__.py`. The `service` kwarg is injected by tests; when absent, `main` builds one over a live handle via `connect(tier)`. House style: argparse, `_cmd_*` handlers, `--json`.

```python
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
    return {
        "registrant_id": str(rec.registrant_id),
        "registrant_name": rec.registrant_name,
        "registrant_kind": rec.registrant_kind,
        "parent_id": str(rec.parent_id) if rec.parent_id else None,
        "contributions": contributions,
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
        print(f"no registrant with id {args.uuid}", file=sys.stderr)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_core_cli.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Smoke-test the real entry point**

Run: `uv run python -m yanantin.core list`
Expected: prints the table header and any registrants in the live default `core_registrants` catalog (likely empty: `(no registrants)`), exit 0 — proves the no-injection path builds a real handle.

- [ ] **Step 6: Commit**

```bash
git add src/yanantin/core/__main__.py tests/integration/test_core_cli.py
git commit -m "feat(c0): core CLI inspector — list/show the registration catalog"
```

---

### Task 3: File the two Pukara findings as issues

**Files:** none (issue tracker only)

The spec recorded two latent leaks in Pukara's `SchemaMap` surfaced during brainstorming. File them so they survive this session (deferred-work-lives-in-issues).

- [ ] **Step 1: File the cache-miss passthrough leak**

```bash
gh issue create --repo fsgeek/pukara \
  --title "SchemaMap._obfuscate_recursive passes unmapped keys through on field-cache miss (silent label leak)" \
  --body "$(cat <<'EOF'
`_obfuscate_recursive` (schema_map.py ~line 239) maps a document key only when it is already in `_field_cache`; on a miss it passes the key through **unmapped**. If the cache was not pre-populated by prior `field_name()` calls for that field, the semantic label lands in storage in plaintext — defeating label obfuscation exactly where it is supposed to hold (third-party-custodian threat model).

Surfaced during yanantin C0 CLI-inspector brainstorming (2026-06-17).

Suggested direction: derive on miss (compute + cache) rather than passthrough, or make passthrough an explicit, asserted decision rather than a silent default.
EOF
)"
```

- [ ] **Step 2: File the double-mechanism divergence**

```bash
gh issue create --repo fsgeek/pukara \
  --title "Two parallel field-mapping mechanisms (explicit field_name vs recursive obfuscate_document) — reconcile" \
  --body "$(cat <<'EOF'
Field obfuscation happens two ways: explicit per-key `field_name(k)` mapping at some call sites (e.g. yanantin `activity/backends/arango.py:140`) and the recursive whole-doc `obfuscate_document` at others. The recursive path is the fragile one (see the cache-miss passthrough leak issue). Worth reconciling onto one mechanism so the obfuscation guarantee is uniform.

Surfaced during yanantin C0 CLI-inspector brainstorming (2026-06-17).
EOF
)"
```

- [ ] **Step 3: Verify the issues exist**

Run: `gh issue list --repo fsgeek/pukara --limit 5`
Expected: both new issues appear.

---

## Self-Review

**1. Spec coverage:**
- RegistrationService + the three verbs + contribution_count → Task 1. ✓
- "opaque collection name is the only anchor / no identifier verb / no persisted UUID" → enforced by Task 1 construction (catalog reached via `collection_name`) and the base-catalog-created test. ✓
- CLI `list` (default) + `show <uuid>` + `--json` → Task 2. ✓
- CLI is integration (live handle), `main()` resolves handle via `connect("test")` → Task 2 (with an injectable `service` for isolated testing — a justified deviation so tests don't pollute the shared default catalog). ✓
- Two Pukara findings filed → Task 3. ✓
- Out-of-scope items (no discovery scan, no `--raw`, no contribution dump, no recursive tree) → not built. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; every run step shows the command and expected result. ✓

**3. Type consistency:** `RegistrationService`, `get_registrant_list`, `lookup_by_identifier`, `lookup_by_name`, `contribution_count`, `base_registrar`, `BASE_REGISTRANT_CATALOG`, `main(argv, service)` are spelled identically across Task 1 (produces) and Task 2 (consumes). `RegistrantRecord` field names match `registration.py` as read. ✓

**One deviation from the spec, made explicit:** the spec described `main()` resolving its own handle. The plan adds an optional `service=` injection so the CLI test can use an isolated, torn-down catalog instead of writing into the shared live `core_registrants`. The no-injection path (real `connect`) is still present and smoke-tested in Task 2 Step 5. This serves the test-isolation concern (gh #24's spirit) without changing the shipped behavior.
