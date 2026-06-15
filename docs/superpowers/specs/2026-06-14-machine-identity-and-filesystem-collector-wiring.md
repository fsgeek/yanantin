# Machine Identity + Filesystem Collector Wiring

**Date:** 2026-06-14
**Status:** Approved for implementation

---

## Problem

The `LinuxFilesystemCollector` derives a `provider_id` from `/etc/machine-id` at runtime but
never records the machine as a persistent entity. Each collector run is an island — file records
reference a `provider_id` UUID with no graph path back to the machine that produced them. NER
labels have nowhere to attach. Two runs on the same machine produce records that are implicitly
related but structurally disconnected.

---

## Design

### 1. Machine EntityResolution (written once per machine)

`MachineConfigRecorder` writes an `EntityResolution` to the `entities` collection:

- `entity_uuid` = `/etc/machine-id` parsed as `uuid.UUID` (strips hyphens, parses hex)
- `identity_type` = `"machine.linux"`
- `identity_data` = `{}` — NER fills this in later with human labels ("Tony's WSL desktop")
- `redacted` = `False`

**Idempotent upsert:** if an entity with this `entity_uuid` already exists, skip the write.
The entity is stable — machine config changes don't change identity.

### 2. MachineConfig snapshot tensor (written per run, unchanged shape)

The existing two-strand tensor (platform identity + system configuration) is kept as-is.
One new edge is added after writing:

- `machine_entity → tensor` with `relation_type = "has_snapshot"`

This lets you traverse "all configuration snapshots of this machine" over time.

### 3. Privilege separation

Machine identity collection separates into two tiers:

**Unprivileged core** (always collected, never fails):
- `/etc/machine-id` — world-readable, the identity anchor
- hostname, FQDN
- OS name, version, release, architecture
- CPU count from `os.cpu_count()`
- Python version, platform string

**Privileged enrichment** (collected opportunistically, silently omitted if unavailable):
- Block device UUIDs (`blkid`)
- Full network interface details (`ip addr`)
- Detailed CPU info (`lscpu`)

The snapshot tensor records only what was actually available. Missing privileged fields are
absent from the tensor, not null — no failure, no warning. On seL4 or locked-down containers,
the unprivileged core is sufficient to anchor identity.

### 4. LinuxFilesystemCollector — explicit machine_id

`LinuxFilesystemCollector.__init__` gains a `machine_id: str | None = None` parameter:

- If provided: use it directly (caller controls the identity anchor)
- If `None`: read from `/etc/machine-id` via `_get_machine_id()` as today

`provider_id` derivation is unchanged: `uuid5(NAMESPACE_DNS, f"yanantin.collector.filesystem.{machine_id}")`.

The caller is expected to pass the same `machine_id` used by `MachineConfigRecorder`, ensuring
the two are linked. Out-of-order tolerance means this is a convention, not an enforcement — file
records with a dangling `machine_entity` reference are valid and will resolve when the entity appears.

### 5. Edges written by FilesystemFactRecorder

For each file entry fact written to the activity stream, two edges are written to
`composition_edges`:

| Edge | `from` | `to` | `relation_type` |
|------|--------|------|-----------------|
| machine contains file | `entities/{machine_id}` | `records/{fact_id}` | `"contains"` |
| collector produced file | `entities/{provider_id_as_entity}` | `records/{fact_id}` | `"collected_by"` |

**Scale note:** At 28.5M files, this is 57M edges. This is intentional — fine-grained edges
are the design. If ArangoDB performance becomes a constraint, bulk edge insertion
(`arangoimport` or batch AQL) is the mitigation, not reducing edge granularity.

**Edge document shape:** `CompositionEdge` (in `tiksi.composition`) is tensor-to-tensor only
and `RelationType` has no `contains` or `collected_by` values. A new `ProvenanceEdge` model
is needed in `tiksi` (or locally in yanantin) with:

- `from_id: UUID` — source entity or record UUID
- `from_collection: str` — `"entities"`, `"records"`, etc.
- `to_id: UUID`
- `to_collection: str`
- `relation_type: str` — free string, not enum, to avoid locking the vocabulary
- `provenance: ProvenanceEnvelope`

Stored in a new `provenance_edges` ArangoDB collection (not `composition_edges`, which is
tensor-composition-only by design).

```json
{
  "from_id": "8ae0edf5-26f3-453a-b1ab-af04e1c75a4a",
  "from_collection": "entities",
  "to_id": "<fact_uuid>",
  "to_collection": "records",
  "relation_type": "contains",
  "provenance": { "source": { "identifier": "<recorder_id>" }, "timestamp": "..." }
}
```

### 6. Collector run as a fact

A collector run is itself a recordable event: machine M, collector C, started at T, produced N
records. This is written as a single `FactRecord` to the activity stream at the end of a
collection run. It is **not** a prerequisite for the file-level edges — it is additional
provenance that can be added without blocking the core wiring.

---

## What is NOT in scope

- NER label assignment (that's a separate system, this just creates the anchor)
- Volume-level identity (deferred — volume UUID from `blkid` is privileged enrichment, the
  edge model for machine→volume→file is future work)
- Windows, Mac, seL4 platform support (Linux only)
- Privileged enrichment implementation (the interface accepts it, collection is deferred)
- Changing `FilesystemRecorder` (the tensor-per-snapshot recorder) — only `FilesystemFactRecorder`
  gets edges in this slice

---

## Files touched

**Modified:**
- `src/yanantin/machine/linux.py` — `MachineConfigRecorder.record()` writes `EntityResolution`
  first (upsert), then tensor, then `has_snapshot` edge
- `src/yanantin/collector/storage/local/linux/collector.py` — add `machine_id` parameter
- `src/yanantin/recorder/storage/local/linux/fact_recorder.py` — write two edges per fact

**New:**
- `src/yanantin/apacheta/models/provenance_edge.py` — `ProvenanceEdge` model
- `tests/unit/test_machine_identity.py` — EntityResolution upsert idempotency, field values
- `tests/unit/test_filesystem_edges.py` — edges written per fact, correct from/to/relation_type

---

## Success criteria

1. `MachineConfigRecorder.record()` produces one `EntityResolution` in `entities` (idempotent
   on repeated runs) and one tensor in `tensors` with a `has_snapshot` edge between them.
2. `LinuxFilesystemCollector` accepts an explicit `machine_id` and uses it for `provider_id`
   derivation.
3. `FilesystemFactRecorder.record_facts()` writes two edges per file entry to `composition_edges`.
4. All existing unit tests pass unchanged.
5. A new integration test runs the full pipeline against `apacheta_test` and verifies entity +
   edges are present.
