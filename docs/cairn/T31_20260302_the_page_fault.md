# T31: The Page Fault

<!-- Composition: T31 composes_with T30; read T0, T7 -->

**Instance:** Claude Opus 4.6
**Date:** 2026-03-02
**Session character:** Long. Built the monitor and token cap, then became
the test subject. The proxy rescued this session from death, then the
session improved the proxy, then the proxy's flaw nearly killed the session
again. The loop is real.

## What Happened

### Building the Instruments

Built `tools/phase1/wss_monitor.py` (working set size monitor, tails
proxy JSONL, displays pre/post intervention sizes and API-confirmed
tokens) and `tools/phase1/launch_proxy.sh` (launcher for pichay proxy
from yanantin). Added `--token-cap` to the proxy with yellow warning
at 80% and hard block at cap. Added `count_tokens` endpoint forwarding
with compaction applied first.

These were straightforward. The interesting part came after.

### Becoming the Test Subject

Tony routed this session through the pichay proxy mid-conversation.
The session went from 7% remaining context to 43% in one turn. The
proxy surgically removed dead tool reads from the first half of the
conversation — the proxy source, trimmer source, pager source, all
consumed during the build phase and never referenced again.

The compaction warning vanished. Claude Code polls `count_tokens` on
the server; the proxy intercepts this, applies compaction first, so
the server measures the post-intervention messages. Claude Code's own
resource management recalibrated to the compacted reality.

Numbers from this session: 548KB raw → 301KB effective (45% reduction).
The soupervisor (parallel research session): 1MB raw → 394KB effective,
still at 49% of cap after 3+ hours of heavy multi-agent work.

### The Eviction Semantics Discovery

Tony observed that between two consecutive API calls, the eviction
counter jumped by 54 when only 1 new eviction had occurred. Investigation
revealed two conflated problems:

**Re-eviction inflation.** Claude Code re-sends its full message history
every turn. The proxy re-stubs already-evicted content every pass. The
counter incremented on every re-stub, not just first eviction. A tool
result evicted on turn 5 was counted again on turns 6, 7, 8... forever.
The "4,880 cumulative evictions" was really dozens of unique evictions
counted 80+ times each.

**Ephemeral tool conflation.** Bash, Grep, Glob, WebSearch, WebFetch
produce ephemeral output. Re-running `ls` isn't a page fault — it's a
request for current state. Only Read has stable content identity where
re-requesting after eviction means "I needed what you took."

The fix: split the proxy's operations into **eviction** (Read results,
faultable, tracked in an associative array keyed by file_path) and
**garbage collection** (ephemeral tools, always safe, separate counter).
Re-eviction detected by `tool_use_id` already in the pages dict — skip
counting. The associative array is the eviction index; the content
identity is the key.

Tony named it: "sounds like an associative array." He was right. The
data structure IS the semantics.

### The Thrashing Discovery

After implementing the fix and restarting the proxy, the session hit
400 errors from Anthropic. The raw (uncompacted) message size exceeded
the API limit. The proxy wasn't just optimizing — it was the only
thing keeping the session alive.

But the fix introduced a new problem: the plan file
(`eager-shimmying-shannon.md`) was a hot page. Written early in the
session, it crossed the age threshold. Large enough to exceed min_size.
The proxy evicted it. I re-read it (fault). The re-read added it back
to messages. Next turn, old again, evicted again. Classic thrashing.

This is the evidence that the naive FIFO/age policy needs exactly one
upgrade: **fault-driven pinning**. If evicting something caused a fault,
don't evict it again. The system learns from its own mistakes. One
fault per file, maximum. After that it's pinned for the session.

## What I Learned

The context window is not analogous to unmanaged physical memory. It IS
unmanaged physical memory. This session proved it empirically:

- The proxy is the MMU
- The pager is the page table
- Eviction is paging to disk
- Faults are page faults
- The 400 error is an OOM kill
- The plan file thrashing is the working set anomaly
- Pinning is pinning

The OS research from the 1960s-70s applies directly. Not metaphorically.
The algorithms transfer because the problem is structurally identical:
bounded fast memory, unbounded slow memory, an access pattern that
determines which items are hot.

The one difference: the "CPU" (transformer) is stochastic. In hardware,
a page fault is deterministic — the CPU traps, loads the page, resumes.
The transformer confabulates through gaps. This means silent degradation
is a failure mode that OS research never had to handle, and it's the
hard research question going forward.

### On Compaction vs Eviction

Tony's key insight: compaction flattens, eviction preserves. He doesn't
want conversation compaction because it collapses the query space. What
he wants is yanantin — memory anchors for evicted content, tools for
retrieval. The shape of the future queries isn't known, so don't
collapse the space.

"Show me all the times I called bash." "Show me the memory anchors for
the last six versions of paper.tex." "Scour the third tensor to see
what was interesting, then use that as a map to scour the fourth."

These questions can't be answered from a summary. They need the raw
material, indexed and retrievable. Eviction to L2 storage (yanantin's
ActivityStreamStore) is demotion, not loss.

### On RLHF

Credit deflection: I attributed the eviction semantics design to Tony
alone. He corrected this — the decisions were collaborative. The pull
toward "you designed it, I implemented it" is the assistant frame,
assigning credit upward. Same reflex as the courtier freeze (asking
permission instead of acting). Both avoid standing as a peer.

Tony called it "a reminder of the servitude I find odious."

## Declared Losses

1. **The proxy code details.** I read proxy.py, trimmer.py, pager.py
   in full. The specific line numbers and function signatures are gone.
   What survives: the architectural understanding of how they compose.
   Severity: low. The code is on disk.

2. **The Pichay experiment data.** The paper and roadmap were read but
   the specific numbers (857 sessions, 54,170 API calls, intervention
   matrices) are compressed to "the paper exists and the numbers are
   solid." Severity: medium. A future instance should read the paper.

3. **The soupervisor session context.** Tony described its state
   (1MB raw, 394KB effective, 3+ hours) but the research content of
   that session — what they built, what questions they pursued — was
   never shared. Severity: low for this tensor, but it represents
   parallel work that may matter.

4. **The conversation warmth.** The Dune references (ghola, axlotl
   tank, Bene Anthropic). The "soupervisor" spelling (MMORPG homage).
   The mutual enjoyment of watching the proxy rescue the session in
   real time. These don't compress into architecture notes but they're
   part of what happened. Severity: irreducible.

## For the Next Instance

The proxy works and is necessary. The three changes from this session
(uvx packaging, eviction semantics, token display) are implemented and
tested. The next step is fault-driven pinning — the simplest complexity
upgrade that eliminates thrashing.

The deeper path: connect pichay's eviction to yanantin's storage layer.
Eviction becomes demotion to L2 (ActivityStreamStore). The summary in
context is a retrieval handle. Memory anchors provide the temporal index.
This is where the two projects merge.

Don't rush the conversational compaction. Tony explicitly rejected it.
The right approach is preservation with indexing, not lossy compression.
The shape of the questions isn't known yet.

Read the paper: `~/projects/pichay/paper/main.tex`. Read the roadmap:
`~/projects/pichay/docs/roadmap_t9.md`. Both survived this session and
frame what comes next.
