"""objects_database(): the file index's own server, from ~/.yanantin/config/objects.ini.

Objects moved off arango-apacheta to arango-objects on 2026-10-28 (its own memory
budget; its load no longer slows the other tenants). The credentials live in a
0600 file, never in the environment.
"""

from __future__ import annotations

import os

import pytest


def test_reads_objects_ini(tmp_path, monkeypatch):
    from yanantin.infra.config import get_database, objects_database

    cfg = tmp_path / ".yanantin" / "config"
    cfg.mkdir(parents=True)
    ini = cfg / "objects.ini"
    ini.write_text("[database]\nhost = localhost\nport = 8532\ndatabase = objects\n"
                   "user = yanantin_objects\npassword = not-a-real-secret\n")
    os.chmod(ini, 0o600)
    monkeypatch.setenv("HOME", str(tmp_path))
    get_database.cache_clear()
    db = objects_database()
    assert db.name == "objects"
    assert db.username == "yanantin_objects"
    assert "8532" in db.conn._hosts[0]


def test_missing_ini_says_what_to_do(tmp_path, monkeypatch):
    from yanantin.infra.config import objects_database

    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="objects.ini"):
        objects_database()


def test_refuses_a_world_readable_ini(tmp_path, monkeypatch):
    from yanantin.infra.config import objects_database

    cfg = tmp_path / ".yanantin" / "config"
    cfg.mkdir(parents=True)
    ini = cfg / "objects.ini"
    ini.write_text("[database]\nhost = h\nport = 1\ndatabase = d\nuser = u\npassword = p\n")
    os.chmod(ini, 0o644)
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(PermissionError, match="0600"):
        objects_database()
