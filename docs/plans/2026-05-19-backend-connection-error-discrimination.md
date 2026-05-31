# Discriminate ArangoDBBackend Connection Failure Modes

*Captured 2026-05-19 — verified finding, fix not yet started.*

## The Bug

`ArangoDBBackend._connect_database()` at
`src/yanantin/apacheta/backends/arango.py:104-121` catches
`except Exception as e:` and wraps every failure as a `ConnectionError`
with the message:

> "Cannot connect to ArangoDB database 'X' at Y. Database must be
> provisioned by an admin before the application can use it. Error: ..."

That message is correct for *one* of the failure modes it currently
covers. It is misleading — and operationally dangerous — for the other
two.

| Underlying error | Reality | What the wrapper claims |
|---|---|---|
| HTTP 401 (wrong credentials) | Check credentials | "Database must be provisioned by an admin" |
| Database doesn't exist | Admin must provision | "Database must be provisioned by an admin" ✓ |
| Connection refused / unreachable | Check host/port/network | "Database must be provisioned by an admin" |

The underlying error text *is* preserved in the message tail (e.g.
`Error: [HTTP 401][ERR 11] not authorized to execute this request`),
but the *prefix* primes the wrong diagnosis. Operators read "must be
provisioned" and go looking for admin tooling when the actual problem
is a typo in `pukara.ini`. Anything that pattern-matches on exception
*type* (not message) sees `ConnectionError` and concludes "DB is down"
no matter which of the three actually happened.

## Why This Matters Beyond Hygiene

Tony has flagged this as a recurring class of failure across earlier
AI-driven projects (Indaleko): code written assuming admin-level
privileges fails when run under a least-privilege user, and the
resulting privilege errors get misdiagnosed as connectivity errors.
The reasoning loop then concludes "the database is unreachable" and
proposes restart/reconnect remediations that cannot possibly help.
This wrapper is the structural enabler of that loop. The remediation
guidance is baked into the exception itself.

This finding is also a concrete instance of the broader threat-model
training reflex — see Pukara memory
`feedback_threat_model_default.md` for the meta-pattern. The
schema-extras-and-registration plan
(`pukara/docs/plans/2026-05-16-schema-extras-and-registration.md`)
identified the same reflex showing up at the schema layer. This
plan addresses it at the error-discrimination layer.

## Evidence

A probe (`/tmp/pukara_auth_probe.py`, run 2026-05-17) exercised two
failure modes against a reachable ArangoDB instance:

### Case A — Wrong credentials, real host

```
env PUKARA_ARANGO_USER=definitely_not_a_user
env PUKARA_ARANGO_PASSWORD=wrong_password

app/TestClient RAISED ConnectionError: Cannot connect to ArangoDB
database 'apacheta' at http://192.168.111.125:8529. Database must be
provisioned by an admin before the application can use it. Error:
[HTTP 401][ERR 11] not authorized to execute this request
```

### Case B — No server listening (connection refused)

```
env PUKARA_ARANGO_HOST=http://127.0.0.1:9

app/TestClient RAISED ConnectionError: Cannot connect to ArangoDB
database 'apacheta' at http://127.0.0.1:9. Database must be
provisioned by an admin before the application can use it. Error:
Can't connect to host(s) within limit (3)
```

Both surface as the same exception type with the same misleading
prefix. The discrimination is buried in the trailing `Error: ...`
string, which is human-readable but not machine-actionable.

## The Fix Shape

Replace the blanket `except Exception` with discrimination on the
underlying python-arango exception. The driver carries HTTP status
codes in its exception attributes; that is the right signal to
branch on.

Three distinct exception classes are needed. Suggested:

```python
class BackendAuthError(ConnectionError):
    """Credentials were rejected by the database."""

class BackendUnreachableError(ConnectionError):
    """Could not establish a network connection to the database host."""

class DatabaseNotProvisionedError(ConnectionError):
    """The named database does not exist on a reachable, authenticated host."""
```

(Inheriting from `ConnectionError` preserves backward compatibility
for callers that catch the base class. New code can catch the specific
subclass for fine-grained handling.)

Discrimination logic in `_connect_database`:

- If the underlying exception is a python-arango error with HTTP
  status `401` or `403` → `BackendAuthError`. Message points at
  credentials, not provisioning.
- If the underlying exception is a `ConnectionError`,
  `requests.ConnectionError`, or a python-arango
  `ServerConnectionError` whose cause is a transport failure
  (refused, timeout, DNS) → `BackendUnreachableError`. Message
  points at host/port/network.
- If the underlying exception indicates the database itself is not
  present (status `404` on `db.collections()` or similar) →
  `DatabaseNotProvisionedError`. Keep the existing wording.
- Anything else → fall back to the generic `ConnectionError` with
  a "unexpected backend failure" prefix and the original error.

The actual exception attributes vary by python-arango version; the
implementor will need to read the driver source or experiment. The
probe script can be re-run to verify each case after the fix.

## Files To Change

### `yanantin/src/yanantin/apacheta/backends/arango.py`

- Define the three new exception classes (likely near the top, or
  alongside existing errors in `yanantin/apacheta/interface/errors.py`
  if the convention is to keep all errors centralized).
- Rewrite `_connect_database()` lines 104-121 with the discrimination
  logic above.

### `yanantin/tests/unit/test_arango_independent.py`

- `test_fails_if_database_unreachable` at line 257-268 currently asserts
  `pytest.raises(ConnectionError, match="Cannot connect")`. Update to
  assert the specific subclass — split into three tests, one per
  failure mode. Each should mock python-arango raising the appropriate
  underlying error and assert the right subclass plus its message
  shape. Keep one test that asserts `ConnectionError` (the base)
  catches all three, for the backward-compat contract.

### `yanantin/tests/red_bar/test_least_privilege.py`

- Line 57's comment references "fail with a ConnectionError". Update
  the comment, and decide whether the structural invariant being
  enforced is "any failure" or specifically "auth failure". The
  least-privilege test should arguably assert `BackendAuthError`
  specifically — that pins "the gateway connecting with non-admin
  credentials sees an auth boundary, not a provisioning failure."

### Downstream: pukara

- Pukara's lifespan currently crashes on `ConnectionError` from the
  backend. Once discrimination exists, Pukara can either:
  - **(a)** Continue to fail-stop at startup, but with a clearer log
    line. The agent still sees uvicorn failing to bind; no HTTP
    response at all.
  - **(b)** Start in a degraded mode: the app comes up, every route
    returns 503 with a specific detail derived from the discriminated
    error class. `/health` returns the actual backend state.
    Diagnostic surface for the agent exists.

  Option (b) violates the strict fail-stop principle in Pukara's
  CLAUDE.md. Worth a separate discussion before choosing. The current
  plan does *not* prescribe a choice; it makes the choice possible.

## Open Questions — Resolved 2026-05-31

1. **Where should the new exception classes live?** → **`interface/errors.py`**
   (centralized), so the memory and duckdb backends can raise the same
   types. Note: they inherit from the builtin `ConnectionError`, *not*
   from `ApachetaError`, so they sit alongside the `ApachetaError`
   hierarchy rather than under it. That dual placement is honest about
   their nature — they are connection errors first, Apacheta-domain
   errors only incidentally.
2. **Should `BackendAuthError` inherit from `ConnectionError` or
   `AccessDeniedError`?** → **`ConnectionError`.** The semantic-truth
   argument for `AccessDeniedError` loses to the backward-compat
   contract: `AccessDeniedError` inherits from `ApachetaError` →
   `Exception`, *not* `ConnectionError`. Routing `BackendAuthError`
   through it would silently break every existing `except
   ConnectionError` catch site — the opposite of the compatibility the
   plan requires. The truer-semantics goal is met instead by the
   *message* ("Authentication rejected … this is not a provisioning
   problem"), which is what the reasoning loop actually reads.
3. **How are these errors surfaced through `ApachetaGatewayClient`?**
   → **Deferred.** Still open; out of scope for this commit, which
   fixes discrimination at the backend layer only. The HTTP-mapping
   question lives downstream in pukara (see "Downstream: pukara"
   above) and remains a separate discussion.

## What Was Implemented — 2026-05-31

TDD, by the freshly-decanted instance picking up the orphaned plan.

- Three new exception classes in
  `src/yanantin/apacheta/interface/errors.py`: `BackendAuthError`,
  `BackendUnreachableError`, `DatabaseNotProvisionedError`, all
  subclassing the builtin `ConnectionError`.
- `_connect_database()` now delegates to a new
  `_discriminate_connection_failure()` that branches on the
  python-arango signal: `ServerConnectionError`/`ArangoClientError`
  (transport) → unreachable; `ArangoServerError` with `http_code`
  401/403 → auth; 404 → not-provisioned; anything else → generic
  `ConnectionError` with an honest "unexpected failure" prefix
  (no more false provisioning claim).
- Six new tests in `tests/unit/test_arango_independent.py` (one per
  failure mode, plus the `issubclass(ConnectionError)` backward-compat
  contract and the unknown-failure fallback). Replaced the single
  `test_fails_if_database_unreachable`. Full suite: 1518 passed.

**Follow-up not taken** (kept out of scope to avoid creep): the
red-bar `test_least_privilege.py` is a source-text invariant, not a
behavioral test, so it needed no change — but the plan's suggestion to
add a *behavioral* assertion pinning "non-admin credentials see
`BackendAuthError`, not a provisioning failure" remains a worthwhile
new red-bar test. Logged here rather than silently dropped.

## What Is Already Done

- The bug is verified empirically (probe results above).
- The Pukara-side defaults (`config.py`) were already changed on
  2026-05-16 to default to `apacheta_app` rather than `root`. So
  any deployment using defaults will *hit* this code path with
  non-admin credentials and will, at least once, see the misleading
  "must be provisioned" message. Fixing the wrapper is now on the
  critical path for clean first-run experience.

## Related Reading

- `pukara/memory/feedback_threat_model_default.md` — the broader
  reflex this finding instantiates.
- `pukara/docs/plans/2026-05-16-schema-extras-and-registration.md`
  — same reflex at the schema layer.
- `yanantin/docs/scout_report_indaleko_patterns.md` — Indaleko
  *design patterns*, not the misdiagnosis pattern. The misdiagnosis
  pattern has not previously been documented in yanantin; this plan
  is its first artifact.
- `yanantin/src/yanantin/apacheta/backends/arango.py:104-121` — the
  exact location of the misdiagnosis.

## The Probe Script

The probe used to verify the bug is at `/tmp/pukara_auth_probe.py` on
the original host. It is not checked in — recreate from this plan's
"Evidence" section if needed. A permanent test in
`yanantin/tests/unit/test_arango_independent.py` should subsume the
probe's role after the fix lands.
