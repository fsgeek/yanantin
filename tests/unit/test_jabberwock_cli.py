"""Unit tests for the Jabberwock CLI (__main__.py).

Tests each subcommand by calling main() with mocked sys.argv.
All tests use --store memory (no DuckDB/ArangoDB dependency).
Output captured via capsys.

Multi-step tests (resolve, show after create, claim, group members)
mock open_store to return a shared InMemoryActivityStreamStore so
data persists across CLI invocations within a single test.

Test author: separate from builder (CI enforces separation).
"""

from __future__ import annotations

import json
import sys
from unittest.mock import patch

import pytest

from yanantin.activity.backends.memory import InMemoryActivityStreamStore


# -- Fixtures --------------------------------------------------------------


@pytest.fixture
def shared_store():
    """A shared InMemoryActivityStreamStore that persists across CLI calls."""
    return InMemoryActivityStreamStore()


# -- Helpers ---------------------------------------------------------------


def _run(monkeypatch, capsys, argv: list[str], store=None) -> str:
    """Run main() with the given argv, return captured stdout.

    If store is provided, mock open_store to return it (shared state).
    """
    monkeypatch.setattr(sys, "argv", ["jabberwock"] + argv)
    from yanantin.jabberwock.__main__ import main
    if store is not None:
        with patch("yanantin.collector.pipeline.open_store", return_value=store):
            main()
    else:
        main()
    return capsys.readouterr().out


def _run_json(monkeypatch, capsys, argv: list[str], store=None) -> dict | list:
    """Run main() with --json, return parsed JSON output."""
    out = _run(monkeypatch, capsys, ["--store", "memory", "--json"] + argv, store=store)
    return json.loads(out)


def _run_text(monkeypatch, capsys, argv: list[str], store=None) -> str:
    """Run main() with --store memory, return text output."""
    return _run(monkeypatch, capsys, ["--store", "memory"] + argv, store=store)


# -- Default command -------------------------------------------------------


class TestDefaultCommand:
    def test_default_shows_status(self, monkeypatch, capsys):
        out = _run_text(monkeypatch, capsys, [])
        assert "Root:" in out
        assert "Backend:" in out
        assert "memory" in out

    def test_default_json(self, monkeypatch, capsys):
        data = _run_json(monkeypatch, capsys, [])
        assert "root" in data
        assert "entities" in data
        assert "aliases" in data
        assert "observations" in data
        assert "memberships" in data
        assert "unresolved" in data
        # root must be a valid UUID string
        from uuid import UUID
        UUID(data["root"])


# -- Bootstrap -------------------------------------------------------------


class TestBootstrap:
    def test_bootstrap_outputs_root(self, monkeypatch, capsys):
        out = _run_text(monkeypatch, capsys, ["bootstrap"])
        assert "Root:" in out
        assert "Created:" in out

    def test_bootstrap_idempotent(self, monkeypatch, capsys, shared_store):
        """Running bootstrap twice on the same store returns the same root UUID."""
        data1 = _run_json(monkeypatch, capsys, ["bootstrap"], store=shared_store)
        data2 = _run_json(monkeypatch, capsys, ["bootstrap"], store=shared_store)
        assert data1["root"] == data2["root"]

    def test_bootstrap_json(self, monkeypatch, capsys):
        data = _run_json(monkeypatch, capsys, ["bootstrap"])
        assert "root" in data
        assert "created" in data


# -- Create ----------------------------------------------------------------


class TestCreate:
    def test_create_outputs_uuid(self, monkeypatch, capsys):
        out = _run_text(monkeypatch, capsys, ["create"])
        assert "Entity:" in out
        assert "Created:" in out

    def test_create_json(self, monkeypatch, capsys):
        data = _run_json(monkeypatch, capsys, ["create"])
        assert "id" in data
        assert "created" in data
        from uuid import UUID
        UUID(data["id"])  # must be valid UUID


# -- Observe ---------------------------------------------------------------


class TestObserve:
    def test_observe_creates_vorpal(self, monkeypatch, capsys, shared_store):
        """Create entity then observe on the same store."""
        entity_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        eid = entity_data["id"]

        out = _run_text(monkeypatch, capsys, ["observe", eid, "species", "person"],
                        store=shared_store)
        assert "Vorpal:" in out
        assert "species" in out
        assert "person" in out

    def test_observe_json(self, monkeypatch, capsys, shared_store):
        entity_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        eid = entity_data["id"]

        data = _run_json(monkeypatch, capsys, ["observe", eid, "name", "Alice"],
                         store=shared_store)
        assert data["category"] == "name"
        assert data["value"] == "Alice"
        assert data["entity"] == eid

    def test_observe_mome_entity(self, monkeypatch, capsys):
        """'mome' as entity_id produces null jabberwock_id."""
        data = _run_json(monkeypatch, capsys, ["observe", "mome", "behavioral", "prefers-tabs"])
        assert data["entity"] is None
        assert data["category"] == "behavioral"
        assert data["value"] == "prefers-tabs"


# -- Alias -----------------------------------------------------------------


class TestAlias:
    def test_alias_creates_tove(self, monkeypatch, capsys, shared_store):
        entity_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        eid = entity_data["id"]

        out = _run_text(monkeypatch, capsys,
                        ["alias", eid, "email", "ALICE@Example.COM"],
                        store=shared_store)
        assert "Tove:" in out
        # Normalized: lowercase
        assert "alice@example.com" in out

    def test_alias_json(self, monkeypatch, capsys, shared_store):
        entity_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        eid = entity_data["id"]

        data = _run_json(monkeypatch, capsys, ["alias", eid, "github", "FsGeek"],
                         store=shared_store)
        assert data["namespace"] == "github"
        # Gimble should be normalized to lowercase
        assert data["identifier"] == "fsgeek"
        assert data["entity"] == eid


# -- Resolve ---------------------------------------------------------------


class TestResolve:
    def test_resolve_found(self, monkeypatch, capsys, shared_store):
        """Create entity + alias, resolve by alias -> Frabjous."""
        entity_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        eid = entity_data["id"]

        _run_text(monkeypatch, capsys, ["alias", eid, "github", "testuser"],
                  store=shared_store)

        out = _run_text(monkeypatch, capsys, ["resolve", "github", "testuser"],
                        store=shared_store)
        assert "Frabjous" in out
        assert "Entity:" in out

    def test_resolve_found_json(self, monkeypatch, capsys, shared_store):
        entity_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        eid = entity_data["id"]

        _run_json(monkeypatch, capsys, ["alias", eid, "github", "testuser2"],
                  store=shared_store)

        data = _run_json(monkeypatch, capsys, ["resolve", "github", "testuser2"],
                         store=shared_store)
        # Frabjous has a jabberwock key
        assert "jabberwock" in data
        assert data["jabberwock"]["id"] == eid

    def test_resolve_not_found(self, monkeypatch, capsys):
        """Resolve nonexistent alias -> MomeResult."""
        out = _run_text(monkeypatch, capsys, ["resolve", "github", "nonexistent"])
        assert "Mome" in out
        assert "Matching toves:" in out


# -- Show ------------------------------------------------------------------


class TestShow:
    def test_show_entity(self, monkeypatch, capsys, shared_store):
        entity_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        eid = entity_data["id"]

        out = _run_text(monkeypatch, capsys, ["show", eid], store=shared_store)
        assert "Entity:" in out
        assert eid in out

    def test_show_json(self, monkeypatch, capsys, shared_store):
        entity_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        eid = entity_data["id"]

        data = _run_json(monkeypatch, capsys, ["show", eid], store=shared_store)
        assert "jabberwock" in data
        assert data["jabberwock"]["id"] == eid

    def test_show_not_found(self, monkeypatch, capsys):
        """Show nonexistent entity -> error exit."""
        from uuid import uuid4
        fake_id = str(uuid4())
        monkeypatch.setattr(sys, "argv", [
            "jabberwock", "--store", "memory", "show", fake_id,
        ])
        from yanantin.jabberwock.__main__ import main
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


# -- Unresolved ------------------------------------------------------------


class TestUnresolved:
    def test_unresolved_lists_momes(self, monkeypatch, capsys, shared_store):
        """Create mome vorpal, list it in unresolved."""
        _run_text(monkeypatch, capsys, ["observe", "mome", "behavioral", "prefers-vim"],
                  store=shared_store)

        out = _run_text(monkeypatch, capsys, ["unresolved"], store=shared_store)
        assert "Count:" in out
        assert "behavioral" in out

    def test_unresolved_json_with_momes(self, monkeypatch, capsys, shared_store):
        _run_json(monkeypatch, capsys, ["observe", "mome", "behavioral", "uses-emacs"],
                  store=shared_store)

        data = _run_json(monkeypatch, capsys, ["unresolved"], store=shared_store)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["category"] == "behavioral"

    def test_unresolved_empty(self, monkeypatch, capsys):
        """No momes -> empty list message."""
        out = _run_text(monkeypatch, capsys, ["unresolved"])
        assert "No unresolved" in out

    def test_unresolved_empty_json(self, monkeypatch, capsys):
        data = _run_json(monkeypatch, capsys, ["unresolved"])
        assert isinstance(data, list)
        assert len(data) == 0


# -- Claim -----------------------------------------------------------------


class TestClaim:
    def test_claim_mome(self, monkeypatch, capsys, shared_store):
        """Create mome vorpal, create entity, claim the mome."""
        mome_data = _run_json(monkeypatch, capsys,
                              ["observe", "mome", "behavioral", "prefers-tabs"],
                              store=shared_store)
        mome_id = mome_data["id"]

        entity_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        eid = entity_data["id"]

        out = _run_text(monkeypatch, capsys, ["claim", mome_id, eid],
                        store=shared_store)
        assert "Claim:" in out
        assert "Record:" in out
        assert "Entity:" in out

    def test_claim_json(self, monkeypatch, capsys, shared_store):
        mome_data = _run_json(monkeypatch, capsys,
                              ["observe", "mome", "test", "val"],
                              store=shared_store)
        mome_id = mome_data["id"]

        entity_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        eid = entity_data["id"]

        data = _run_json(monkeypatch, capsys, ["claim", mome_id, eid],
                         store=shared_store)
        assert data["record_id"] == mome_id
        assert data["entity_id"] == eid
        assert "claim_id" in data


# -- Group -----------------------------------------------------------------


class TestGroup:
    def test_group_add(self, monkeypatch, capsys, shared_store):
        """Add membership edge between entity and group."""
        member_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        group_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        mid = member_data["id"]
        gid = group_data["id"]

        out = _run_text(monkeypatch, capsys,
                        ["group", "add", mid, gid, "student"],
                        store=shared_store)
        assert "Rath:" in out
        assert "Entity:" in out
        assert "Group:" in out
        assert "Role:" in out
        assert "student" in out

    def test_group_add_json(self, monkeypatch, capsys, shared_store):
        member_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        group_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        mid = member_data["id"]
        gid = group_data["id"]

        data = _run_json(monkeypatch, capsys,
                         ["group", "add", mid, gid, "ta"],
                         store=shared_store)
        assert data["entity"] == mid
        assert data["group"] == gid
        assert data["role"] == "ta"

    def test_group_members(self, monkeypatch, capsys, shared_store):
        """Add member then resolve group members."""
        member_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        group_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        mid = member_data["id"]
        gid = group_data["id"]

        _run_text(monkeypatch, capsys,
                  ["group", "add", mid, gid, "student"],
                  store=shared_store)

        out = _run_text(monkeypatch, capsys, ["group", "members", gid],
                        store=shared_store)
        assert "Group:" in out
        assert "Members:" in out
        assert "1" in out

    def test_group_members_json(self, monkeypatch, capsys, shared_store):
        member_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        group_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        mid = member_data["id"]
        gid = group_data["id"]

        _run_json(monkeypatch, capsys,
                  ["group", "add", mid, gid, "student"],
                  store=shared_store)

        data = _run_json(monkeypatch, capsys, ["group", "members", gid],
                         store=shared_store)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["jabberwock"]["id"] == mid

    def test_group_members_empty(self, monkeypatch, capsys, shared_store):
        """Group with no members."""
        group_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        gid = group_data["id"]

        out = _run_text(monkeypatch, capsys, ["group", "members", gid],
                        store=shared_store)
        assert "Members: 0" in out

    def test_group_members_empty_json(self, monkeypatch, capsys, shared_store):
        group_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        gid = group_data["id"]

        data = _run_json(monkeypatch, capsys, ["group", "members", gid],
                         store=shared_store)
        assert isinstance(data, list)
        assert len(data) == 0


# -- Help ------------------------------------------------------------------


class TestHelp:
    def test_help_flag(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["jabberwock", "--help"])
        from yanantin.jabberwock.__main__ import main
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0


# -- End-to-end flow -------------------------------------------------------


class TestEndToEnd:
    def test_full_flow(self, monkeypatch, capsys, shared_store):
        """Create entity -> observe species -> alias -> resolve -> verify."""
        # 1. Create entity
        entity_data = _run_json(monkeypatch, capsys, ["create"], store=shared_store)
        eid = entity_data["id"]
        assert eid

        # 2. Observe species
        obs_data = _run_json(monkeypatch, capsys,
                             ["observe", eid, "species", "person"],
                             store=shared_store)
        assert obs_data["category"] == "species"
        assert obs_data["entity"] == eid

        # 3. Alias
        alias_data = _run_json(monkeypatch, capsys,
                               ["alias", eid, "github", "TestUser42"],
                               store=shared_store)
        assert alias_data["identifier"] == "testuser42"  # normalized
        assert alias_data["entity"] == eid

        # 4. Resolve by alias
        resolved = _run_json(monkeypatch, capsys,
                             ["resolve", "github", "testuser42"],
                             store=shared_store)
        assert "jabberwock" in resolved
        assert resolved["jabberwock"]["id"] == eid

        # 5. Verify observations in resolved view
        vorpals = resolved.get("vorpals", [])
        species_obs = [v for v in vorpals if v["tulgey"] == "species"]
        assert len(species_obs) == 1
        assert species_obs[0]["snicker_snack"] == "person"

        # 6. Verify alias in resolved view
        toves = resolved.get("toves", [])
        github_toves = [t for t in toves if t["wabe"] == "github"]
        assert len(github_toves) == 1
        assert github_toves[0]["gimble"] == "testuser42"
