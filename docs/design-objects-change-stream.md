# Objects: a current projection plus a change stream (proposal, 2026-10-26)

*From yanantin's steward. It resolves the tension between #31 (append-only versioning with
`supersedes` edges, chosen with Tony in June) and the July batch landing (one object per
machine and path, replaced in place). Nothing below is built yet.*

## The problem, as it showed up

- Re-walking a machine replaces each object by `uuid5(source:uri)` and refreshes its
  `observed_at`. It never notices a file that's gone: a deleted file stays findable forever.
- Replacing in place also overwrites the previous size, mtime and inode. The history #31
  chose to keep is lost on every walk.
- The substrate position (`docs/yanantin-substrate-position.md`) says what both must
  satisfy. History stays legible as "an append-only chain of transitions", and the reader of
  `find` chooses between "post-supersession only, or superseded records with status exposed".

## The proposal: keep both, as event sourcing

1. **`Objects` is the current projection**: one document per (machine, path), as now. It is
   what makes "what's there" a 3 ms lookup, and it should stay that.
2. **Each complete walk is diffed against the projection, and the diff is a stream of
   immutable change facts** in the activity stream (provider = that machine's collector):
   - **created:** a path the projection doesn't have;
   - **changed:** size, mtime or (device, inode) differ. The fact carries the old and new
     values. A new (device, inode) at the same path is #31's atomic-rename case: a new
     physical object under the same logical file;
   - **gone:** in the projection, not seen in this walk;
   - **unchanged:** nothing is written. This is #31's write-suppression, and it also makes a
     re-walk land only what changed instead of rewriting millions of documents.
3. **"Gone" objects are marked, not deleted.** The projection records `gone_at` (the walk that
   failed to see the path). `find` defaults to present objects; a scope option includes gone
   ones ("what was there"), which the substrate position asks for.
4. **History is the change stream.** Any earlier state of a path is its creation fact plus its
   changes. `supersedes` is then a relation between successive change facts for the same
   (machine, path), rather than between object documents.

## Why this shape

- This **is** the storage activity data stream Tony described: "scan everything, look for
  changes". A walk is the sensor, and the diff is the activity. eBPF, the NTFS USN journal or
  FSEvents can later feed the same change facts faster, without changing what is stored.
- It fixes #31's "identical-copy hoarding" (unchanged means no write) without giving up the
  fast current view.
- Deletions are facts with a time. "When did that file disappear?" becomes a query.

## Costs and limits, declared

- **The diff must read the projection for one machine.** That is up to 5M (uri → size, mtime,
  inode) entries, streamed by source, or looked up per chunk by key. It needs measuring before
  choosing between the two.
- **"Gone" means not seen by a complete walk under the same policy.** A partial walk, a
  permission change or a policy change (name excludes) must not mark things gone. Each walk
  records its root and policy, and only a complete walk with the same policy may emit "gone".
  The 2026-10-26 policy mix (July `--all-names` against today's default) is exactly the case
  this rule exists for.
- **Size and mtime miss a content change that preserves both.** That was declared in June
  (handoff-collector-recorder-architecture.md); content hashing is a separate transducer.

## Migration

The July objects of this WSL carry the old policy's `observed_at` values. After every machine
has had one all-names walk, the first diffed walk per machine sets the baseline. "Gone" is
emitted only from the second diffed walk onward.
