# Query-driven enrichment: let the queries decide what knowledge to extract

*Provenance: conversation with Tony (PI) and the yanantin owner instance, 2026-10-16.
Status: a hypothesis with an evaluation plan, not a result. The idea is Tony's, from
Indaleko (the sound-engineer example) and a conversation with Royal (studio asset
management). This page records it so it has a date and a home.*

## The problem

Digital asset management professionals spend up to 25% of their time searching
for, or recreating, assets they can't locate (Horodyski, *Metadata Matters*, CRC
Press, 2022). Knowledge workers spend about 8.8 hours a week searching for files
(Dropbox, 2023). Both are cited in `thesis/draftchapters/intro.tex`; check the
primary sources before quoting them in a paper.

> "Show me the sound files that included thunder for the game *AI Escape from
> Anthropic* that we released three years ago."

| Factor | In the query | Resolved by |
|---|---|---|
| what | sound files | file type, already indexed |
| what (semantic) | included thunder | **an attribute nobody has**: an audio transducer |
| why / project | the game | an entity, resolved through activity (repositories, build manifests, commits), not filenames |
| when | released three years ago | **an event anchor** (the release), not file mtimes |
| who | we | the team as principal |

## Claim

In the regime of **a few clients querying a shared collection** (a person, a studio,
an ayllu), queries are few, repeated and domain-specific. There, the query workload
can decide not only *which indexes to build* (classic workload-driven tuning) but
**which derived attributes to compute at all**. A query for an attribute that
doesn't exist triggers the transducer that creates it.

**What makes it affordable.** The query's cheap factors (time anchor, project,
type) prune the candidate set *before* the expensive transducer runs. Enrichment
then costs on the order of the pruned set (hundreds of files), not the corpus
(hundreds of thousands). Once computed, the attribute stays on those objects for
every later query by anyone in the group. Temporal pruning (`docs/north-star.md`)
is what makes demand-driven enrichment cheap.

## Mechanism (what yanantin has and lacks)

- Has: a transducer slot (in-process Unstructured path, 2026-07), the six-factor
  shape (`yanantin.factors`), a single gateway through which every ArangoDB query
  passes (the obfuscating façade, enforced by a red bar), and an append-only store.
- Lacks: query capture at that gateway (plan, scanned and returned counts, timing,
  result histogram); the transducer cost-signal interface (gh #20); event anchors
  (a release as a hyperedge over its assets); entity resolution from a project name
  to its activity.

## Evaluation (Tony's metrics, fixed before building)

1. **Abandonment:** are search chains abandoned less often with query-driven
   enrichment than without (or than the earlier version)? Split abandonment into
   *existed but not found* and *absent*; telling those apart is part of what good
   tools buy you.
2. **Time and cost to find:** does the wall-clock time (and, for AI consumers,
   tokens) from first query to a "found" signal decrease?
3. **Cost side:** transducer compute spent compared with classifying the whole
   corpus up front, at equal (1) and (2).

The chain definitions (query → reformulation → found or abandoned) are to be
pre-registered and timestamp-anchored before any analysis. For AI consumers,
khipumaq's verbatim `raw` tool calls already contain chains (`search` followed by
`recall` = found).

## Related work to check (not yet read for this page)

Workload-driven index tuning (AutoAdmin and successor tuning advisors); adaptive
indexing and database cracking; query stores that keep plans and runtime stats
(SQL Server Query Store, `pg_stat_statements`); missing-index records kept by the
optimizer. The claimed difference: those reorganise *existing* attributes; this
decides which *new* attributes to extract, with cost bounded by query-time pruning.
