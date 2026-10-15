# Evidence references in qhaway memories, and a verifier

**Date:** 2026-10-14. **Asked for by:** qhaway (`../qhaway/docs/requests/2026-10-14-reply-to-yanantin.md`, qhaway `31b7fb1`).
**As of:** yanantin `eb3b1516`.

## Problem

A memory cites evidence as free text: an episode key, a commit hash. Nobody can check later that
the evidence still exists and is unchanged. On 2026-10-14 an audit had to join a hamut'ay
memory, khipumaq episodes, git, and a correction by hand.

## Format

Memory topic files may carry an `evidence:` list in their YAML frontmatter. qhaway leaves
unknown keys byte-identical (`qhaway/tests/test_topic_files_untouched.py`).

```yaml
evidence:
  - ref: git:hamutay@ab3e3f2752bd8a21292cfe2efb0d4a7314b49972
  - ref: git:hamutay@ab3e3f27:experiments/auto_vs_bio_results.md
    sha256: <hex>
  - ref: khipumaq:019e8405-a228-7c60-97dd-2b086cb81878-line8673
    sha256: <hex>
  - ref: memory:some-other-memory-slug
    sha256: <hex>
```

| Scheme | Resolves to | What `sha256` covers |
|---|---|---|
| `git:<repo>@<commit>` | a commit in `<repos>/<repo>` | not needed; the commit id is already a content hash |
| `git:<repo>@<commit>:<path>` | a file at that commit | the file's bytes at that commit |
| `khipumaq:<episode key>` | a khipumaq episode | UTF-8 of `user_message + "\0" + response` |
| `memory:<slug>` | `<slug>.md` in the same memory directory | the file's bytes |

`python -m yanantin.evidence pin <ref>` prints the entry with its digest, so a writer never
computes one by hand.

## Statuses

| Status | Meaning |
|---|---|
| `intact` | resolved, and the digest matches (or the scheme needs none) |
| `changed` | resolved, but the digest differs from the one recorded |
| `missing` | the store answered, and the referent is not there |
| `unavailable` | the store could not be asked (no repo, no khipumaq config, database down) |
| `withdrawn` | `memory:` only: another memory in the directory `retracts` it |
| `superseded` | `memory:` only: another memory `supersedes` it |
| `unpinned` | resolved, but no digest was recorded where the scheme needs one |
| `unknown` | the scheme is not one of the above |

`withdrawn` and `superseded` are reported alongside the digest check (`withdrawn, intact`).

**What a status claims.** `intact` means *the evidence is unchanged since it was cited*. It never
means the memory is true. The verifier says "evidence intact", not "verified". (qhaway's limit:
don't turn a fallible store into "a temple of (alleged) truth".)

## Verifier

`python -m yanantin.evidence check <memory dir> [--repos DIR]` prints one line per reference.
It exits 1 if any reference is `changed` or `missing`, and 0 otherwise. `unavailable` doesn't
fail the run, because a machine without khipumaq can't say anything about khipumaq.

- Standalone: it reads files, runs `git`, and reads khipumaq through khipumaq's own config file
  (`$KHIPUMAQ_CONFIG`, else `~/.config/khipumaq/db-config.ini`). It imports nothing from qhaway
  or khipumaq, and qhaway gains no dependency.
- `--repos` defaults to `$YANANTIN_REPOS`, else `~/projects`, the ayllu layout (`~/projects/<repo>`).

## Declared losses

- khipumaq's credentials are its own scoped user, which can write. A read-only user would be
  least privilege; none exists yet.
- The khipumaq digest covers the episode's words only. A re-ingest that changes other episode
  fields is not seen.
- A `memory:` ref resolves only within one memory directory. Cross-directory (hamut'ay memory
  cited from yanantin's) is not covered.
- A `git:` ref to a repository that rewrote history reports `missing`, which is correct but
  doesn't say why.

## Evidence for more

qhaway's reopen trigger is chains joined by hand *repeatedly*. The count is kept here; add a
line each time:

1. 2026-10-14: auto-vs-bio audit (a hamut'ay memory, khipumaq, hamutay git, a qhaway correction).

## Fixtures

`tests/fixtures/evidence/` is a self-contained memory directory (`memory:` refs only) with
`expected.tsv` as its contract (file, ref, status, note). qhaway may copy it into its own tests;
`tests/unit/test_evidence.py::test_shared_fixtures_match_expected` keeps the two in agreement here.
