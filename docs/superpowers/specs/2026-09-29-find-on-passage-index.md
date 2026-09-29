# find() on the passage BM25 index

*2026-09-29. Evidence: [find-quality scorecard](../../find-quality-scorecard.md). Design chosen
from a panel of three (minimal, boundary-first, consumer-first) and two judges. It is the
minimal design, with the boundary fixes grafted on.*

## What changes

`ArangoDBBackend.find(terms, limit)` stops scanning every record. It queries a BM25 view
over **passages** and returns the same `FindResult`, with hits in relevance order.

## Passages

- **What a passage is.** A passage is one unique `(session, dotted path, string value)` leaf of
  a stored record.
- **Source.** Derive passages from the dict that is actually stored: the output of
  `_to_generic_doc`, before obfuscation, with `id` already removed. Do not use
  `model_dump`.
- **Exclusions.** Skip `_`-prefixed keys at any depth, top-level `provenance` and
  `lineage_tags`, and every non-string value. These rules are identical to
  `eval/find_quality.py` (`record_leaves`), and a parity test enforces that.
- **Session** is `provenance.author_instance_id`. If a record has no provenance, use the
  record's own key as its session, so records without a session never share passages.
- **Document fields.**
  - `_key`: the first 16 hex characters of sha256(session NUL path NUL value), as in the
    instrument.
  - `session`, `path`, `value`.
  - `record_key`: the record that owns the passage.
  - `text`: the humanized path plus `": "` plus the value, with underscores turned into
    spaces. Humanizing replaces `_` and `.` with spaces.
- **Code.** The derivation lives in `src/yanantin/apacheta/passages.py`. The frozen instrument
  `eval/find_quality.py` is not edited.

## Storage

- **Collection.** `passages`, created through `Khipu.watay`.
- **View.** An arangosearch view named `self._map.collection_name("passages_bm25")`. The view
  name goes through the obfuscator; Khipu passes names through raw, so the caller must supply
  the obfuscated name. The view links `passages.text` with `text_en`, and Khipu obfuscates
  the links.
- **When they are created.** Both are created in `_ensure_collections`, and only under a
  transparent map.

## Write path (`store_record`)

- **Transparent map.** One stream transaction inserts the record, then `insert_many` inserts
  its passages with `overwrite_mode="ignore"`. `ignore` means the first writer owns a
  passage. If either insert fails, neither is kept.
- **Opaque map.** Only the record is written, as today; no passages are written. Stored
  passage values contain semantic path words, which would break C0.

## Keeping passages current (`sync_passages`)

- **What it does.** An idempotent function that walks every record in instrument order
  (cycle, then timestamp, then key) and inserts the missing passages with `ignore`.
- **When it's needed.** Hamut'ay writes records through older installed yanantin code that
  knows nothing about passages, so this is the backfill. It is safe to run at any time, and
  there is no truncate.
- **CLI.** `python -m yanantin.apacheta.passages sync`.
- **Known gap.** A record written by an older client is not searchable until the next sync.

## Query

- BM25 over the view with `text_en`. The query has underscores turned into spaces and uses
  `waitForSync`.
- **One hit per record.** Group with `COLLECT` on `record_key`, using `MAX(BM25)`, sorted
  by best score descending, then key.
- **Hit fields.** `matched_fields` holds the record's matched paths, ordered by score.
  `snippet` holds the best passage's value, capped at 120 characters.
- **Counts.** `total_matched` is `fullCount` of distinct records, which is exact.
  `truncated` is `total_matched > limit`.
- **Field and view names** are resolved through the obfuscator. This is enforced by
  `red_bar/test_no_literal_aql_field_refs`.
- **Fail-stop.** If the view is missing, or the map is opaque, `find()` raises. The substring
  scan is deleted, and there is no fallback.

## Tests

- **Unit:**
  - leaf rules
  - the underscore and humanize rules
  - parity with `find_quality.build_passages` on a synthetic corpus, including a record
    without provenance
- **Integration** (`apacheta_test`):
  - stemming
  - the underscore rule (`reward_function` found by "reward function")
  - first owner within a session, both owners across two sessions
  - exact `total_matched` and `truncated` above `limit`
  - a record is findable immediately after `store_record`
  - a duplicate record raises `ImmutabilityError` and leaves the passage count unchanged
  - running `sync_passages` twice gives the same set
  - the existing `test_llika_service` find contract
- **Red bar:**
  - an opaque map means no passages are written and `find()` raises
  - a missing view means `find()` raises
  - a failed passage insert means no record exists (the write is atomic)
  - neither the view name nor its links contain a semantic name under a **hashing**
    obfuscator; this needs a hashing stand-in, since `PrefixObfuscator` keeps the word
- **Replay gate:** after the production sync, run the frozen query set through `find()`.
  Record-level success@10 should be close to the passage-level 0.76. It is labelled a
  replay, not a prediction.

## Declared losses

- No `rank` or `score` envelope yet. Hit order is the only ranking signal.
- The snippet is the best passage's value, not a window around the matched terms.
- Plaintext values are gh #9's exposure. On opaque storage the feature is off, which is
  gh #8.
- `content_view.py` becomes dead code. It is noted here, not deleted.
- Hamut'ay's `search_memory` is not moved; that migration is a hamutay change, offered
  separately.
