# Database Setup Tooling

*Design spec for `yanantin.infra` — ArangoDB container and database lifecycle management.*

*2026-04-15. Approach B: clean reimplementation using Indaleko's `db/` as reference.*

## Problem

Yanantin's ArangoDB backends are fully implemented and tested, but standing
up a working database requires manual steps: running a Docker container,
creating databases, creating users with correct permissions, configuring
connection parameters. No tooling exists to automate this. The integration
tests hardcode a specific server IP and connect with admin credentials,
which is poor security posture.

## Prior Art

- `indaleko-test/utils/misc/i_docker.py` — Docker SDK container/volume lifecycle
- `indaleko-test/db/db_config.py` — Singleton config, credential generation,
  database/user setup via python-arango, health-check polling
- `indaleko-test/db/db_setup.py` — Orchestrator wiring Docker + config + DB init
- `Mallku/scripts/initialize_arangodb.py` — Database/user/collection init

## Module Structure

```
src/yanantin/infra/
    __init__.py
    docker.py         — Docker SDK wrapper (container/volume lifecycle)
    config.py         — Singleton config (credential tiers, INI storage)
    orchestrator.py   — Wire docker + config + DB init
    __main__.py       — CLI: uv run python -m yanantin.infra
```

Four files, each with one job. `docker.py` knows about containers.
`config.py` knows about credentials and connection parameters.
`orchestrator.py` knows the sequence. `__main__.py` is the CLI.

## Credential Tiers

Three tiers, one source of truth. The principle: application code and tests
never hold admin credentials. The path of least resistance goes through
Pukara; direct access requires deliberate effort.

| Tier | User | Database | Stored in | Used by |
|------|------|----------|-----------|---------|
| Admin | `root` / random | `_system` | `~/.yanantin/config/db.ini` (0600) | Setup tool only |
| Test | `apacheta_test` / random | `apacheta_test` | `.env` in project root | Tests, local dev |
| Production | random / random | `apacheta` | Pukara `config/pukara.ini` | Pukara gateway |

Production username is randomized (same pattern as Indaleko) — a
compromised password alone isn't enough without also knowing the
username. Test username remains fixed (`apacheta_test`) since the test
database contains no sensitive data and discoverability aids debugging.

`~/.yanantin/config/db.ini` is the master credential store for all three
tiers. It is the source of truth created at setup time. Pukara's config
copies the app credentials from `db.ini` — it does not generate its own.
The `.env` file extracts only the test credentials. The separation is
about *exposure*, not about independent credential management: `db.ini`
(0600, outside project tree) holds everything; `.env` (in project,
gitignored) and Pukara's config each expose only what their consumers need.

### Config File Format

INI file at `~/.yanantin/config/db.ini`, permissions 0600:

```ini
[database]
database = apacheta
timestamp = 20260415120000
host = localhost
port = 8529
ssl = false
admin_user = root
admin_passwd = <random>
app_user = <random>
app_password = <random>
test_user = apacheta_test
test_password = <random>
container = arango-yanantin-20260415120000
volume = yanantin-db-20260415120000
```

Container and volume fields are absent for remote instances.

### .env Output

Written to project root (already in `.gitignore`). Contains test
credentials only:

```bash
YANANTIN_ARANGO_HOST=http://localhost:8529
YANANTIN_ARANGO_DB=apacheta_test
YANANTIN_ARANGO_USER=apacheta_test
YANANTIN_ARANGO_PASSWORD=<random>
```

## Config Singleton

`ApachetaDBConfig` — singleton class following Indaleko's pattern. Once a
config is loaded, every component in the process gets the same database
connection. No accidental split-brain.

Key behaviors:
- If config file exists: load it
- If config file doesn't exist: generate new config with random credentials, save it
- Exposes `get_admin_credentials()`, `get_test_credentials()`, `get_app_credentials()`
- Connection helper: `connect(tier)` returns a connected `python-arango` database object
- SSL/TLS support for remote connections
- `start(timeout=60)` — poll health endpoint until ready, then connect

## Docker Lifecycle

`ApachetaDocker` — thin wrapper around the `docker` Python SDK.

Methods:
- `pull_image()` — pull `arangodb/arangodb:latest`, return whether image changed
- `create_container(name, volume, password, port=8529)` — create with volume mount,
  port mapping, root password, `restart_policy={"Name": "unless-stopped"}`
- `start_container(name)` / `stop_container(name)`
- `container_status(name)` — returns running / stopped / not-found
- `delete_container(name, force=False)` — force-stops first if running
- `create_volume(name)` / `delete_volume(name)`
- `update_container(name)` — pull new image, preserve volume and password, recreate
- `reset_volume(name)` — wipe data, keep container config
- `list_containers()` / `list_volumes()` — filtered to `yanantin-` prefixed names

Container naming: `arango-yanantin-{timestamp}`.
Volume naming: `yanantin-db-{timestamp}`.

Note: Indaleko's `create_container` has a bug in `restart_policy` — it
passes `{self.container_name: "unless-stopped"}` but Docker expects
`{"Name": "unless-stopped"}`. Fixed in this implementation.

## Orchestrator

`ApachetaDBSetup` — wires Docker + config + database initialization.

### `setup` command (from nothing to working database)

1. Generate config with random credentials
2. Save to `~/.yanantin/config/db.ini` with 0600 permissions
3. Pull ArangoDB image
4. Create volume, create container, start container
5. Poll health endpoint until ready (with timeout)
6. Connect as admin to `_system`
7. Create `apacheta` database, create `apacheta_app` user, grant rw on `apacheta`
8. Create `apacheta_test` database, create `apacheta_test` user, grant rw on `apacheta_test`
9. Verify both connections work with least-privilege credentials
10. Write `.env` with test credentials only
11. Print summary

### `check` command

- If config exists: load, verify container running, verify DB reachable,
  verify credentials work
- If no config: tell user to run setup

### `start` / `stop`

Container lifecycle. Config must exist.

### `status`

Container state + DB reachability + which databases exist.

### `reset --rebuild`

Stop container, delete volume, regenerate passwords, re-setup.
Requires confirmation.

### `connect --remote --host X --port Y [--ssl]`

Create config for an existing remote instance. No Docker management.
Runs steps 6-10 against the remote server (requires admin credentials
to be provided).

### Default behavior

No subcommand: if config exists, `check`; if not, `setup`.

## CLI

```
uv run python -m yanantin.infra [command]

commands:
  setup              Stand up ArangoDB from nothing
  check              Verify everything is working
  start              Start the container
  stop               Stop the container
  status             Show container and database state
  reset --rebuild    Wipe and recreate (with confirmation)
  connect            Configure for remote instance
    --host HOST
    --port PORT
    --ssl
    --admin-password   (prompted if not provided)
```

## Integration Test Changes

### Current env var names (to be retired)

The integration tests currently use:
- `ARANGO_ADMIN_USER`, `ARANGO_ADMIN_PASSWORD` — admin credentials (removed entirely)
- `ARANGO_TEST_USER`, `ARANGO_TEST_PASSWORD` — test user credentials
- `YANANTIN_ARANGO_HOST` — already uses the standard prefix

### New env var names (standardized)

All variables use the `YANANTIN_ARANGO_` prefix:
- `YANANTIN_ARANGO_HOST` — unchanged
- `YANANTIN_ARANGO_DB` — database name (was hardcoded `apacheta_test`)
- `YANANTIN_ARANGO_USER` — test user (replaces `ARANGO_TEST_USER`)
- `YANANTIN_ARANGO_PASSWORD` — test password (replaces `ARANGO_TEST_PASSWORD`)

The `ARANGO_ADMIN_*` variables are removed entirely. Tests never need
admin credentials.

### Current state
- `test_arango_real.py` and `test_arango_activity.py` hardcode `192.168.111.125:8529`
- Tests connect as admin to `_system`, create/drop databases per session
- Test runner holds root credentials

### After this work
- Tests read `YANANTIN_ARANGO_*` from `.env`
- Tests connect as `apacheta_test` to `apacheta_test` — no admin access
- Tests truncate collections for isolation (rw permits)
- If database unreachable or credentials fail, tests skip
- No hardcoded IPs

This is the structural impediment: the test runner physically cannot
reach the production database because it doesn't have the credentials.

### Wiring

The caller is responsible for reading env vars and passing them to
backend constructors. The config singleton provides credential values
via `get_test_credentials()` / `get_app_credentials()` for programmatic
use. The `.env` file provides them for test/CLI use. The backend
constructors (`ArangoDBBackend.__init__`, `ArangoDBActivityStreamStore.__init__`)
continue to accept `host`, `db_name`, `username`, `password` as
parameters — no refactoring needed.

### Recovery

If `db.ini` is lost while the container persists, the root password is
unrecoverable. Recovery path: `docker rm` the container (data survives
on the volume), then `setup` creates a new container with a new root
password against the existing volume.

## Dependencies

Already installed:
- `docker` 7.1.0 — Docker SDK
- `python-arango` 8.2.6 — ArangoDB client

No new dependencies required.

## Related Issues

- fsgeek/yanantin#1 — Replace static collection lists with dynamic registration
  (separable, not part of this work)

## Security Model

The threat is not external attackers. It is accidental bypass of Pukara
by builder subagents, test fixtures, or convenience scripts that connect
directly to ArangoDB with credentials they shouldn't have.

Structural defenses:
- `db.ini` is the master credential store, outside project tree, 0600 permissions
- `.env` contains only test credentials — the only thing tests can see
- Pukara copies app credentials from `db.ini` into its own config
- Path of least resistance goes through Pukara
- Direct production access requires reading `db.ini` or Pukara's config (deliberate)

This is not absolute security. It is structural impediment that makes
accidental bypass expensive enough that the "why would I?" question
applies. Security is cost-benefit, not binary.
