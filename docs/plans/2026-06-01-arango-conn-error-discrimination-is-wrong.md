# The arango connection-error discrimination is partly WRONG (found by going live)

*2026-06-01. The 2026-05-31 fix (`_discriminate_connection_failure` in
`apacheta/backends/arango.py`) was "verified" by MOCKED tests that fed the
discriminator synthetic exceptions matching my BELIEFS about how python-arango
presents failures. Two of those beliefs are false. Live recon against the real
`apacheta_test` container found both in seconds. The mocks tested the
discriminator against my assumptions, not against the database.*

## Defect 1 — missing database does NOT produce a 404

**Belief baked into the code:** "If the database doesn't exist → HTTP 404 →
`DatabaseNotProvisionedError`."

**Reality:** a reachable, *authenticated* connection to a nonexistent database
raises `CollectionListError` with **`http_code=401`** (error_code 11), NOT 404.
ArangoDB rejects database-scoped access before reporting "no such database."

**Consequence:** the `404 -> DatabaseNotProvisionedError` branch is effectively
**unreachable**. A missing database hits the `401/403 -> BackendAuthError`
branch instead — so the code tells the operator "check your credentials" when
the real problem is "the database isn't provisioned." This is the EXACT
misdiagnosis the morning's fix claimed to eliminate, reintroduced one layer
deeper. (Distinguishing the two may require inspecting `error_code` / the
message, or a separate existence probe — needs real investigation, not another
assumption.)

## Defect 2 — a refused connection is not a python-arango exception

**Belief baked into the code:** transport failure →
`ServerConnectionError`/`ArangoClientError` → `BackendUnreachableError`.

**Reality:** a refused connection (dead host/port) raises a builtin
**`ConnectionAbortedError`** (or `ConnectionRefusedError`/`urllib3`/`requests`
transport types), which is NOT a subclass of `ServerConnectionError` or
`ArangoClientError`. So the `BackendUnreachableError` branch **never fires** for
a real refused connection; it falls through to the plain `ConnectionError`
fallback ("Unexpected failure").

**Consequence:** "host unreachable" is misreported as a generic unexpected
failure rather than the actionable "check host/port/network."

## Why the mocks hid both

`test_arango_conn_errors.py` constructed `MagicMock`/`ArangoServerError` objects
with `http_code` set to the values I EXPECTED (403, 404) and exception types I
EXPECTED (`ServerConnectionError`). The discriminator dutifully branched on
them and the tests passed — proving only that the function maps the inputs I
imagined to the outputs I wanted. The real driver produces DIFFERENT inputs.
The mock tested the mirror, not the database.

## The fix (next builder/tester cycle)

1. Branch on what the driver ACTUALLY raises: builtin connection errors
   (`ConnectionError` family) + transport types → unreachable; `http_code`
   401/403 → auth; missing-db distinguished by `error_code`/message or an
   existence probe, not by 404.
2. Tests are LIVE (real `apacheta_test`): bad creds → real auth failure; dead
   host → real refused connection; nonexistent db on the reachable authed
   server → real CollectionListError(401). Each must FAIL if the DB is down.
3. Re-run the live recon in this doc to re-derive the real exception shapes
   before coding; do not assume.
