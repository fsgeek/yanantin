"""Red-bar test: Least privilege invariant.

The ArangoDB backend must never escalate to admin privileges.
Application code connects to its target database with the credentials
it's given. Database creation, user management, and backups are admin
operations done separately with root — never by the application.

These tests exist because the original backend connected to _system
to auto-create databases. That required root. A flatworm noticed.
"""

import ast
import inspect
import re
from pathlib import Path

import pytest

from yanantin.apacheta.backends.arango import ArangoDBBackend


# ── The backend never touches _system ────────────────────────────────


def test_backend_source_has_no_system_database_reference():
    """The ArangoDB backend source must not reference '_system'.

    Connecting to _system requires admin privileges. The backend
    should connect directly to its target database. Database
    provisioning is an admin task done outside the application.
    """
    source_file = Path(inspect.getfile(ArangoDBBackend))
    source = source_file.read_text()

    # Remove comments and docstrings for accurate scanning
    tree = ast.parse(source)
    string_literals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            string_literals.append(node.value)

    system_refs = [s for s in string_literals if "_system" in s]
    assert not system_refs, (
        f"ArangoDB backend references '_system' in string literals: {system_refs}. "
        f"The backend must connect directly to its target database, "
        f"never to _system. Database creation is an admin operation."
    )


def test_backend_connect_does_not_create_databases():
    """The backend must not have database creation logic.

    If the target database doesn't exist, the backend should fail-stop
    with a ConnectionError, not try to create it. Creating databases
    requires admin privileges the application should never have.
    """
    source_file = Path(inspect.getfile(ArangoDBBackend))
    source = source_file.read_text()

    assert "create_database" not in source, (
        "ArangoDB backend contains 'create_database'. "
        "The backend must fail-stop if the database doesn't exist, "
        "not try to create it. That's an admin operation."
    )


def test_backend_default_username_is_not_root():
    """The default username must not be 'root'.

    Root should only be used for admin operations (database creation,
    user management, backups). Application access uses a dedicated
    least-privilege user.
    """
    sig = inspect.signature(ArangoDBBackend.__init__)
    username_default = sig.parameters["username"].default

    assert username_default != "root", (
        f"ArangoDB backend defaults username to '{username_default}'. "
        f"Default should be empty or a non-root user. "
        f"Root credentials are for admin operations only."
    )


# ── Config templates don't encourage root ────────────────────────────


def test_pukara_config_template_does_not_use_root():
    """The Pukara config template must not suggest root as the username.

    Config templates are what people copy. If the template says 'root',
    that's what gets deployed. The template should show the
    least-privilege user pattern.
    """
    # Pukara is a sibling project — derive from this project's root
    project_root = Path(__file__).resolve().parents[2]
    template = project_root.parent / "pukara" / "config" / "pukara.ini.template"
    if not template.exists():
        pytest.skip("Pukara config template not found")

    content = template.read_text()
    # Find the username line in the [arango] section
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("username") and "=" in stripped:
            value = stripped.split("=", 1)[1].strip()
            assert value != "root", (
                f"Pukara config template uses 'root' as username. "
                f"Templates should show least-privilege users. "
                f"Root is for admin operations only."
            )


# ── Integration tests use dedicated test users ───────────────────────


def test_integration_tests_use_dedicated_test_user():
    """Integration tests must not use root for test operations.

    Root is acceptable for test DATABASE creation/teardown (admin op).
    All actual test operations must use a dedicated test user with
    access only to the test database.
    """
    test_file = Path("tests/integration/test_arango_real.py")
    if not test_file.exists():
        pytest.skip("Integration test file not found")

    content = test_file.read_text()

    # The backend fixture should use test credentials, not admin
    # Look for ArangoDBBackend constructor calls
    backend_calls = re.findall(
        r'ArangoDBBackend\([^)]*username\s*=\s*(\w+)',
        content,
    )
    for var_name in backend_calls:
        assert "ADMIN" not in var_name, (
            f"Integration test creates ArangoDBBackend with {var_name}. "
            f"Backend instances in tests must use least-privilege test "
            f"credentials, not admin credentials."
        )
