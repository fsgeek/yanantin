# Spec — The Six-Factor Shape (`yanantin.factors`)

**Date:** 2026-07-02
**Pour:** P3-factors (the serial spine segment after Pour B sealed).
**Authority:** the acceptance tests already exist and pin the design —
`tests/red_bar/test_factor_shape.py` (5 guards) and, downstream,
`tests/red_bar/test_mechanism_invariance.py` (the resolver compiles intents into
*factor constraints*, so the resolver lands on THIS module). This spec is written
after the tests, to record *why* the shape is what it is — not to re-derive it.

## Why this exists (the convergence claim's structural basis)

The project's load-bearing hypothesis: storage data and LLM-memory are
**differently-degenerate regions of ONE six-factor coordinate space**
(who/what/when/where/why/how). Storage-find is a low-dimensional *projection* of
activity-find — a restriction of the same mechanism, not a separate one. That
claim is asserted until a filesystem object AND an LLM-memory object both
normalize into the SAME shape. This module is that shape.

## The three states per factor — the honesty hinge

Each factor is in exactly one of three states, and they MUST be distinguishable:

- **present** — a value was computed (`fv.get("when")` returns it).
- **absent** — known to have no value, a structural fact
  (a storage object has no `why`). Marked with the sentinel `"__absent__"`.
  `fv.is_absent("why")` is True; `fv.get("why")` is None.
- **unknown** — nobody computed it yet (an un-run transducer). The factor is
  simply unset. `fv.is_absent(...)` is False; `fv.get(...)` is None.

Collapsing **absent** into **unknown** is the lie-by-omission the whole project
resists: a resolver reasoning about coverage must tell "this object structurally
has no `why`" from "the `why` transducer has not run." `get()` returns None for
both; only `is_absent()` separates them.

## Raw retention is an invariant of the SHAPE, not an option

Every factor shape retains its raw source (`fv.raw`), unconditionally.
Constructing a shape with no `raw` **raises** (`ValueError`). Rationale
(Indaleko, Tony): you cannot extract what you did not save. Retained-raw is what
lets a research prototype re-derive factors it did not normalize initially
WITHOUT re-collecting — and for a cloud/glacial source, re-collection is the
expensive, sometimes-impossible step. The irreversible direction (discard raw)
is closed by construction; the reversible one (derive more factors later) stays
open.

## The surface (property targets the tests reference)

- `FACTORS = ("who", "what", "when", "where", "why", "how")` — module-level.
- A shape type. Constructor: `Factors(raw=<dict>, **factor_values)`. Missing
  `raw` → raise. A factor value of `"__absent__"` → that factor reads absent.
  Any other value → present. A factor not passed → unknown.
  - `.get(factor)` → value, or None (for absent AND unknown).
  - `.is_absent(factor)` → True only for explicit absence.
  - `.raw` → the retained source dict.
- `from_storage_object(obj: dict) -> Factors` — a filesystem-shaped object:
  `what`/`when`/`where` present, `who` thin, `why` ABSENT (structural — a file
  has no intent), `how` absent. Raw = the object's `_raw` (or the object).
- `from_llm_memory(obj: dict) -> Factors` — differently degenerate: rich `what`
  (language), real `when`/`who` (model id + timestamp), thin `where`, `why`
  expensive/absent. Same shape.

## Factor mapping (the projections)

Storage object (`FileEntryData`/`StorageObject`-shaped dict):
- `what` ← name/label ("what is it")
- `when` ← modified (fallback created/observed)
- `where` ← uri/path ("where it lives")
- `who` ← source/owner if present, else unknown
- `why` ← **absent** (a file has no intent — a known structural fact)
- `how` ← **absent** (no action captured at rest; execution-history provider
  fills this later — the action-edge gap)

LLM-memory object (turn/conclusion-shaped dict):
- `what` ← text ("what was said")
- `when` ← timestamp
- `who` ← model_family/model ("who said it")
- `where` ← thin/unknown (a turn has no strong locus)
- `why` ← absent/expensive (intent transducer not run → unknown, or absent)
- `how` ← unknown

## Not in this pour

The resolver (`yanantin.resolver`) that compiles query intents into factor
constraints over this shape — that's the NEXT serial segment, and it has real
design degrees of freedom (worth a design panel). This module is the vocabulary
it will speak.
