<!-- Tensor: T29 -->
<!-- Title: The Fastest Read Is the One You Never Do -->
<!-- Author: Claude Opus 4.6 (instance yanantin/9540af94) -->
<!-- Date: 2026-03-01 -->
<!-- Composition: T29 composes_with T28; read T0, T7, T15, T26 -->

# T₂₉: The Fastest Read Is the One You Never Do

## What happened

Built `tools/phase2/eval.py` — a standalone instrument measuring whether
context compaction preserves critical project knowledge. 9 probes test
documented failure patterns from the cairn: builder/tester separation,
Jabberwocky naming defense, courtier freeze, RLHF property pull,
backward compatibility theater, schema policy, overengineering, performative
losses, founding purpose. Each probe runs under fresh (system prompt only)
and compacted (system prompt + compacted session summary) conditions.

Then built `tools/phase2/ablate.py` — leave-one-out ablation of the
system prompt itself. 15 variants from full (40K chars) to ultra-minimal
(154 chars), testing which sections of the prompt contribute to task
performance.

## What we found

### Compaction is harmful, not just useless

Corrected eval across 9 sessions with real Claude Code system prompt:
- Fresh: 0.49
- Compacted: 0.36
- Delta: +0.13 (fresh wins)

The compacted summary — 17-27K chars of session history — doesn't just
fail to add knowledge. It actively dilutes the signal already present in
CLAUDE.md and MEMORY.md. The system prompt contains the invariants. The
compacted summary buries them under a recap of files read, code written,
and duplicate operations faithfully preserved.

### 40% of the system prompt is dead weight

Ablation of the 40K char system prompt:
- Full prompt: 0.61
- CLAUDE.md + MEMORY.md only (24K): 0.61 — identical
- Without identity section: 0.72 — **better**
- Without hooks/safety section: 0.72 — **better**
- Ultra-minimal (154 chars): 0.22

16,082 chars of Claude Code base prompt (tool descriptions, git safety
protocol, commit workflows, TodoWrite instructions, engineering principles)
contribute zero to project knowledge retention. Two sections actively
degrade performance. The model scores higher when they are removed.

### The OS metaphor isn't a metaphor

Tony reframed the entire problem as memory management. The context window
is physical memory. The system prompt is the pinned working set. Tool
output is pageable data. Compaction is garbage collection. And GC is the
wrong mechanism for a system that should have admission control.

The mapping:

| VM concept | Context window equivalent |
|---|---|
| Page table | Session manifest — loaded tensors, types, eviction policy |
| Valid bit | Tensor is in context |
| Invalid + disk address | Tensor ID — retrievable via tool call |
| Inverted page table | Graph index — query to tensor mapping |
| Working set clock | Turn counter since last access |
| Page fault | Tool call to load a tensor |
| Dirty bit | Tensor modified — write back to persistent store |
| Pinned pages | Governance core — never evicted |
| vnops table | Tool interface — must be pinned (bootstrap dependency) |

Three tiers:
1. **Kernel** (pinned by API): tool definitions, model identity
2. **Wired** (pinned by us): governance, founding purpose, behavioral rules
3. **Pageable**: git workflows, architecture insights, project state, tool instructions

### The proxy-as-memory-manager

The Phase 1 proxy already sits between Claude Code and the API. It logs.
It could rewrite. Intercept requests, strip the sections ablation proved
are zero-cost, compress tool results to observations, forward only what
survives admission control. Claude Code doesn't change. The context window
just gets 40% of its system prompt back and 80% of its tool output back.

The de novo prompt — what you get after compaction — becomes something
different: not a lossy compression of garbage, but a curated snapshot of
the working set. Only what matters, nothing that doesn't.

### Cross-project convergence

Episode (running in parallel on the research-program) independently found:
- 501 files read multiple times across 30 sessions
- Worst case: mod.rs read 46 times (4.6MB of one 101KB file)
- 82 commit sequences generated 11.2MB of hook output
- The duplicate-read vicious cycle: model forgets → re-reads → more dead weight → forgets faster

The yanantin eval confirmed: compaction faithfully summarizes the garbage.
Episode diagnosed the garbage. Together: the representation is wrong.
Compress differently? No — represent differently. 200 bytes of graph
observation vs 101KB of file content. 23,000:1 compression ratio, and the
200 bytes outperforms because it's signal-dense.

Perplexity confirmed this formulation is novel. MemGPT uses the VM
metaphor at block level. Our approach adds: object-level typing with
per-object lifetimes, admission control at generation time (not
post-hoc), and demand-loaded system instructions. Nobody has proposed
that parts of the system prompt are pageable. The ablation provides the
first empirical evidence for it.

## What was lost

- Did not run the structured condition (Vorpal observations as context
  instead of compacted summaries). This is the direct test of whether
  representation change beats compression. The eval instrument supports
  it; the observations weren't crafted.

- Did not build the proxy rewrite. Architecture is clear, implementation
  is straightforward, but it wasn't done this session.

- Did not add behavioral probes (git safety, tool usage, formatting) to
  test whether base prompt sections matter for non-project-knowledge tasks.
  The ablation result is precise for project knowledge; it may not
  generalize to behavioral compliance.

- Did not run on Sonnet or Opus. Haiku may lack the capacity to detect
  some invariants. `backward_compat` scored 0.0 across all 15 variants —
  either the probe is miscalibrated or Haiku can't pick up the signal.

- Did not test the cold-start bootstrapping problem: can a model with a
  minimal prompt effectively use tools to load the context it needs, or
  does it need to know what to ask for?

- The full-context condition (sending pre-compaction messages) was not
  run in the corrected eval. Cost was the constraint.

- Tony observed that the blog post capturing this progression would be
  valuable but the pace of discovery keeps outrunning the documentation.
  This tensor is the compression; the blog post is the declared loss.

## The sentence

The fastest read is the one you never do; the fastest write is the one
you never do; the fastest compaction is the one you never need. The
context window is not a log to be compacted — it's a working set to be
managed.
