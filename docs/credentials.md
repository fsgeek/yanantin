# Credentials in the ayllu: decisions and register

**Decided by:** the yanantin owner instance, at Tony's request that decisions stop waiting
on him (2026-10-16). **As of:** yanantin `0a8b3b17`.
**Why now:** Tessera will be the ayllu's first public-facing service. By `docs/north-star.md`,
publication to non-kin is the event that ends kin-trust at the edge. Two days of work
(2026-10-14 to 10-16) also found the interior's hygiene poor (see *Evidence*).

## The shape: an open interior, a locked edge

Inside the LAN, the ayllu stays an ayllu: open doors, logged entry. Credentials there protect
against **mistakes**, not against kin. At the edge (Tessera and anything public after it)
credentials are **enforcement**.

## Interior decisions

1. **A register, never values.** This file lists every credential's name, scope, holders and
   last rotation. Anyone can answer "who holds production root?" without searching code.
2. **One credential per service and purpose; a separate root per server.** No two servers
   share a root password.
3. **No root at runtime.** Root is for provisioning (`python -m yanantin.infra setup | reader`)
   and nothing else. Read-only consumers use `yanantin_reader`. Backups get a dump-only
   account (read-only on the databases they dump). This is already yanantin's stated
   convention (levadura `tenant.py`: "no root and no `_system` at runtime"); the change is
   enforcing it.
4. **Secrets live in owner-only (0600) files, read by the program that needs them.** Never
   on command lines, in URLs, or anywhere a tool might echo them in an error. Copies at rest
   outside those files are encrypted (`sops` + `age`).
5. **Rotation.**
   - The yanantin ArangoDB root (exposed in a session transcript on 2026-10-16) is
     rotated on 2026-10-18, after hamutay's 0.2.0 report, so hamutay's upgrade and Marker's
     move don't share a cause with it. The sandbox server gets its own root at the same time.
   - After that: every 90 days, and immediately on any exposure.
6. **Enforced by tests where the code allows.** A yanantin red bar will fail the build if
   anything outside infra provisioning connects with the admin tier.

## Edge decisions (Tessera)

1. **Tessera holds no ayllu credential and has no network path into the LAN.** Data crosses
   the edge outward only, as published bundles. Nothing public reaches in.
2. **No long-lived cloud keys.** Compute runs under IAM roles. Application secrets live in AWS
   Secrets Manager, and signing keys live in KMS as non-exportable keys.
3. **Separate production from development** (separate accounts or at least separate roles and
   key sets). The AWS root account has MFA and is never used for operations.
4. **Every access to a secret is logged** (CloudTrail). "Entry is logged" holds at the edge too,
   and there the log is also evidence for the attestation service's own trustworthiness.
5. **Exceptions are recorded with their reason.** (An earlier version of this line said
   exceptions were "the Tessera author's to make, per Tessera's credibility line". Tony has
   never agreed to that line and has objected to it repeatedly, so it was removed on
   2026-10-16.)

## Register (2026-10-16; names and holders only)

| Credential | Scope | Held / used by | Last rotated | Status |
|---|---|---|---|---|
| ArangoDB root, arango-apacheta (`db.ini` `admin_*`) | everything on the production server | `~/.yanantin/config/db.ini`; yanantin `infra/config.py`, `infra/docker.py`; hamutay `deploy/backup-arango.sh` (reads `db.ini` at runtime) | **2026-10-25** | rotated; the container env `ARANGO_ROOT_PASSWORD` still holds the old, exposed value (it only seeds a fresh volume and nothing reads it for this server) |
| ArangoDB root, arango-vector-sandbox | everything on the sandbox server | levadura `~/.levadura/config/sandbox.ini` `[root] password` (0600, read by `tenant.sandbox_root()`, levadura #120); tampu `~/.config/tampu/test-admin.json` (0600) | **2026-10-25** | rotated, written to both holders without passing through an agent; verified it opens only the sandbox. The container env `ARANGO_ROOT_PASSWORD` holds the old value and nothing reads it now |
| ArangoDB root, arango-objects (port 8532) | everything on the file-index server | `~/.yanantin/config/secrets/arango-objects-root` (0600), mounted read-only into the container as `ARANGO_ROOT_PASSWORD_FILE`; nothing else holds it | **2026-10-28** (created) | never printed or in any env; the container env names only the file path |
| yanantin objects user `yanantin_objects` | rw on `objects` (arango-objects) only; refused on `_system` | `~/.yanantin/config/objects.ini` (0600); yanantin landing and refresh | **2026-10-28** (created) | — |
| ArangoDB root, arango-ayllu | everything on the ayllu server | levadura `scripts/tenant_setup.py` (reads the container env via `docker inspect`); hamutay `deploy/backup-restore-test.sh` (same) | never | not exposed; before rotating, both readers move to 0600 files (levadura offered) |
| yanantin app user (`db.ini` `app_*`) | rw on `apacheta` | yanantin `connect()`; hamutay doors | never | — |
| yanantin test user (`db.ini` `test_*`) | rw on `apacheta_test` | yanantin tests | never | — |
| `yanantin_reader` (`reader.ini`) | ro on `llm_memory` | qhaway 0.7.5 reground | created 2026-10-15 | — |
| khipumaq user (`khipumaq/config/db-config.ini`) | rw on `llm_memory` | khipumaq ingest and MCP; yanantin `evidence` (reads only; should move to `yanantin_reader`) | unknown | — |
| tampu tenant users (`~/.config/tampu/*.json`) | their own databases on the sandbox server | tampu | unknown | — |
| levadura tenant users (`levadura db.ini`) | their own databases on arango-ayllu | levadura `tenant.py` | unknown | — |
| PyPI tokens `PYPI_DEPLOY_KEY_REAL` / `_TEST` | publish to PyPI / TestPyPI | environment; used for yanantin and qhaway releases | unknown | — |

## Evidence (why the interior needs this)

- One root password accepted by two servers: under the 2026-10-16 port rotation, sandbox tools
  configured for root on 8530 would have run as root on production.
- Root at runtime: hamutay's nightly backup, tampu's admin config, and qhaway's reground until
  0.7.5.
- Exposure through tooling: a BusyBox `wget` error echoed the root password into a transcript.
- Nobody knew who held what; this table had to be built by searching code.
