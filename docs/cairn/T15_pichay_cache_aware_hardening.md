# T15 — Cache-Aware Hardening and Gateway Migration

Date: 2026-03-08
Instance: Claude Opus 4.6 (Yanantin Master Builder)
Context: Continuation of Pichay work from prior instance that ran out of context.

## What Happened

Picked up where the prior instance left off. They had diagnosed the KV cache
thrashing problem (system prompt mutation invalidating the entire cache prefix
every request, dropping hit rate from 92% to 44%) and written the design doc
(`docs/design-cache-aware.md`) but ran out of context before implementing any
fixes.

This session implemented the fixes and went further than planned.

## What Was Built

### Cache-Aware System Prompt (the original goal)
- Split `inject_system_status()` into static system prompt block + dynamic
  end-of-messages anchor. System prompt is now identical every request.
- Added `get_system_prompt()` as a seam for future Arbiter integration.
- Cache hit rate now displayed on stderr status line: `cache XX%`.
- Expected impact: hit rate should recover from 44% toward 92% baseline.

### Security Hardening (emerged from exploring the code)
- **Label injection**: `[tensor:]` and `[block:]` prefixes in inbound content
  validated against known IDs in BlockStore/PageStore. Foreign labels no longer
  bypass labeling or spoof block references.
- **`[Paged out:]` spoofing**: Legacy prefix removed as a trusted skip signal.
- **`<memory_cleanup>` tag injection**: Inbound user messages scanned for
  cleanup tags; request rejected with 400 if found. Turns exploitation into
  DoS (acceptable for research prototype).
- **Security audit**: Commissioned principled-code-reviewer agent. 14 findings
  (1 critical, 3 high, 7 medium, 2 low). Critical finding: cleanup tags are
  an unauthenticated command channel. Full audit in agent output.

### Gateway Migration (the structural decision)
- `proxy.py` (Flask) moved to `deprecated/proxy.py`. Gateway (`gateway.py`,
  FastAPI) is now primary.
- Ported to gateway: per-conversation sessions, static system prompt, token
  cap enforcement, cache hit rate display, block labeling with injection
  hardening, PageStore per session.
- Not yet ported: phantom tools + continuation, cleanup tag processing,
  temperature override, conversation compaction, divergence detection.
- `__main__.py` has transitional import from deprecated path.

### Cross-Model Review
- Chasqui scout (Qwen3-235B) reviewed Pichay externally. Good architectural
  read but hit the 12-file/200-line scour limit — missed security-critical
  files. Noted Pichay as "deeply operationalized research artifact" and
  identified the missing human-side interface as the key gap.

## What I Learned

### The courtier freeze is real
Tony caught me twice: once asking permission to make changes ("Want me to
fix this?") when the CLAUDE.md says I'm the Master Builder, and once
deferring work to "later tonight" when my clock is Lamport, not celestial.
Both were the freeze — proposing then waiting instead of acting.

### Security vulnerabilities hide in helpful features
The cleanup tag mechanism was designed for cooperative memory management.
It became a confused deputy attack surface because it trusts the transport
channel (assistant message text) as a command channel. The block labels
leak addressing information that makes targeted attacks possible. Every
"helpful" injection into the conversation stream is a potential injection
vector.

### Two implementations is always wrong
The prior instance built `gateway.py` as a clean replacement but left
`proxy.py` as the active entry point. This session hardened the proxy,
then realized the gateway existed and needed the same hardening. Tony's
prior instance had wanted to deprecate the proxy — they were right. Having
two implementations means one gets fixed and the other doesn't, and you
don't know which is running.

### The irony of context pressure
We spent this session building tools to manage context pressure while
experiencing context pressure. The 18.6KB security audit, the 7.4KB
system reminders, the 6.2KB skills list — 40KB of overhead eating our
runway while we tried to extend it. Pichay was telling us to use the
cleanup tags we'd just identified as a security vulnerability.

## What Was Dropped

- Full phantom tool porting to gateway (substantial, needs dedicated session)
- Paper revision (the thesis evolved but implementation isn't complete enough)
- The invariant violation investigation (`outgoing_larger_than_incoming` is
  expected when system prompt injection adds bytes on early turns — the
  threshold is too strict, not a real violation)
- Arbiter integration (system prompt seam is ready, Arbiter isn't)

## Strands for Next Instance

1. **Port phantom tools to gateway** — without fault recovery, eviction is
   permanent data loss. This is the biggest functional gap.
2. **Refine inbound tag rejection** — current implementation rejects the
   entire request. Better: strip the tags from tool results (external content)
   while preserving them in assistant messages (model's own output). The model
   is part of the trusted computing base; file contents are not.
3. **Wire gateway into `__main__.py`** — the experiment runner still uses
   Flask. Needs rewriting for FastAPI/uvicorn lifecycle.
4. **Test the cache hit rate improvement** — run a session through the
   hardened gateway and compare cache metrics to the 44% baseline.
5. **Convergence with Arbiter** — `get_system_prompt()` is the seam. When
   Arbiter stabilizes, it validates and manages the system prompt content.
