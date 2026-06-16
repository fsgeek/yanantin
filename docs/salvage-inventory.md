# Salvage Inventory — before the C0 spine-rewrite

*2026-06-16. "Is this still Yanantin or a replacement?" resolved into a SALVAGE INVENTORY: the
name follows the salvage, not the code-percentage. A rewrite that carries the load-bearing /
non-regenerable / identity-bearing pieces forward IS Yanantin continuing; one that drops them
silently is a replacement even if it keeps more lines. Criterion for salvage: load-bearing AND
(path-dependent OR identity-bearing). The felt "I'd hate to lose this" is the detector.*

*Method: Tony gave the whole directory list AT ONCE (deliberately — "the affirmation for whichever
one I choose is the tell"; refusing to let the builder validate a single pick forces independent
judgment on the whole). Tony's read + Claude's INDEPENDENT read, disagreements MARKED not smoothed.*

## The four-way cut + orthogonal tooling

| Dir | Tony's read | Claude's independent call | Verdict |
|-----|-------------|---------------------------|---------|
| **transport** | "wranglers, definitely core" | Agree — the build-path simplifier | **CORE** |
| **apacheta** | "immutable store interface" | The CONTRACT (immutability + interface) is core; tensor models are AI-section; its missing REGISTRATION is C0 | **CORE (contract) / AI (models)** |
| **llika** | "AI section, built last week" | Agree — AI read-side | **AI** |
| **jabberwock** | "NER, want to keep" | Agree + scout confirms risky-rebuild (adversarial-review design, mome lifecycle, namespace registry) | **SALVAGE — risky-rebuild** |
| **collector** | "not the right level if bifurcating" | Agree — distribute into the tenants they FEED, not a top-level section (the blob-recorder wreck came from treating them as generic) | **FEEDER → tenants** |
| **recorder** | (same) | Same — tenant-specific feeders | **FEEDER → tenants** |
| **chasqui** | "orchestrator we'll need" | Agree — salvage; scout flags cost-weighting + prompt structure risky-rebuild. Uses the substrate, not in the 4-cut | **SALVAGE (tooling)** |
| **experiments** | "useful but probably not core" | Agree harness=easy-rebuild; its FINDINGS are irreplaceable (data-is-product) | **ORTHOGONAL (outputs sacred)** |
| **infra** | "largely orthogonal" | Agree — infra management | **ORTHOGONAL** |
| **provenance** | "more speculative than real, but important to me" | IDENTITY-BEARING: code thin/speculative, but encodes the attestation commitment (Willay, integrity threat-model). Keep the INTENT even if code is rewritten | **ASPIRATIONAL-CORE (keep intent)** |

## DISAGREEMENTS / OPEN — do NOT smooth these over

- **machine** — Tony: "useful but I don't know where it slots — maybe core?" **Claude pushes back:
  machine is a COLLECTOR (the machine-identity provider; produces records like filesystem does),
  NOT core. It feels core because identity feels foundational, but it's a SOURCE, not substrate.**
  Genuine architecture disagreement, not preference. RESOLVE before slotting.
- **tinkuy** — Tony: "not sure where or if it fits now." Claude: suspect VESTIGIAL governance
  tooling (audit/succession/ground-truth-from-fs). **VERIFY-BEFORE-CARRYING** — don't auto-salvage,
  don't auto-drop.
- **awaq** — Tony: **"I can't tell you what awaq does right now."** THE MOST IMPORTANT ITEM:
  a piece Tony can't describe but hasn't dropped = the silent-loss risk made live (the
  declared/done gap happening TO the PI, on the salvage list). Scout says: composition WEAVER —
  extracts composition declarations from tensors, tensor-ref regex (Unicode subscripts, LaTeX),
  relation vocabulary; 855 loc / 627 test loc; **risky-rebuild.** "Keep a thing I can't describe"
  and "drop a thing I can't describe" are BOTH wrong. **ACTION: re-read awaq and recover its
  function BEFORE deciding — the one genuine "go find out" before any rewrite starts.**

## Irreplaceable RESEARCH ARTIFACTS (data-is-product; not code — RECORDS of what happened)

These cannot be re-run; the original session logs / spend are gone. ROOT principle = sacred.
- `docs/findings-2026-05-14-tool-name-cue-conflict.md` — pre-registered study, 13 models, $1.17
  OpenRouter spend, FALSIFIED predictions (as valuable as confirmed). OTS-anchored thinking-order.
- `docs/compaction_quality_finding.md` (+ `tools/compaction_experiment.py`) — needs original
  Claude Code session logs to reproduce; can't.
- `docs/findings-2026-05-10-hamutay-tool-analysis.md` — a one-time analyst-instance behavior record.

## Also flagged by scout (verify, lower priority)

- `apacheta/ingest/markdown_parser.py` — **scout says IRREPLACEABLE**: the T0–T7 tensor calibration,
  tuned to literal strings real tensors contained ("I collapsed:", "The losses are mine"). If the
  rewrite drops it, the original tensors may become unreadable. Carry if the old tensors are truth.
- `apacheta/content_address.py`, `rummage.py`, `query/engine.py` — easy-rebuild, reference tests.

## Bottom line

Carrying THIS inventory forward = Yanantin continues. Dropping it silently = replacement wearing
the name. The three OPEN items (machine slot, tinkuy fit, awaq function) need decisions Tony hasn't
made; awaq needs a re-read FIRST. None of this blocks C0's bottom-up build (own Arango → DuckDB
mapping → 3 calls → fail-stop singleton) — salvage is carried INTO the new spine as each section is
built, not a gate before it.
