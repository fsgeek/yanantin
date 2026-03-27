<!-- Chasqui Scout Tensor
     Run: 8316
     Model: perplexity/sonar-pro (Perplexity: Sonar Pro)
     Cost: prompt=$3e-06/M, completion=$1.5e-05/M
     Usage: {'prompt_tokens': 5088, 'completion_tokens': 1190, 'total_tokens': 6278, 'cost': 0.03911, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.03911, 'upstream_inference_prompt_cost': 0.015264, 'upstream_inference_completions_cost': 0.023846}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-27T21:36:21.687682+00:00
     GenerationID: gen-1774647366-5pZKKK2i8POKe8lJNSsZ
-->

### Preamble
Dropped as Perplexity: Sonar Pro into `tmp/ubuntu-vm.claude/skills/pptx/scripts/`. First pull: a tight ecosystem of PowerPoint manipulators, each surgically precise yet interdependent like yin-yang blades. `inventory.py` screamed "epistemic cartographer" — mapping text with positions, overflows, overlaps — while `replace.py` imports it directly, revealing a pipeline not just for editing slides, but for *observing and intervening* in presentation cognition.

### Strands

**Surgical Text Archaeology**  
`inventory.py` doesn't just scrape text — it reconstructs *absolute positions* for nested GroupShapes (lines ~100-200 implied in dataclass hell), sorting shapes by visual order, flagging overflows and overlaps. ParagraphData captures bullets, levels, alignment, even space_before in inches. Surprising: it filters slide numbers/non-content placeholders, assuming "real" content is what's semantically meaty. Tension: treats PPTX as a spatial database, but PIL+ImageFont hints at rendering simulations (line ~20 imports), blurring extraction into prediction. Makes me think: this is for auditing *design intent* before AI rewrite.

**Destructive Reconstruction Pipeline**  
`replace.py` loads `inventory.py`'s output as sacred input, then *clears ALL text shapes* unless explicitly overridden (docstring warns bluntly). `clear_paragraph_bullets()` rips bullet XML nodes (`a:buChar`, `a:buNone`), rebuilds with OxmlElement hacks for custom indents (font-proportional EMUs, line ~50-70). `apply_font_properties()` prefers RGB hex over theme_colors, with fallback getattr(MSO_THEME_COLOR). Assumption: inventory JSON is the single source of truth — no shape untouched without spec. Tension: destructive by default (clear everything!), yet hyper-preserves formatting. Reveals intent: bulk-replace for AI-generated decks, where human oversight flags exceptions.

**Slide Cloning Ritual**  
`rearrange.py`'s `duplicate_slide()` is black magic: deepcopy()s shape XML, xpath-hunts `a:blip[@r:embed]`, recreates rels for images/media via `get_or_add()` (lines ~60-90). Clears placeholders first to dodge duplicates, copies *after* layout match. `delete_slide()` and `reorder_slides()` manipulate `_sldIdLst` directly. Surprising: repeats allowed (e.g., slide 34 twice), 0-based indices. Assumption: source layouts are pristine templates; output dir auto-makes. Tension: fragile rel-handling (six.iteritems for py2 compat?), assumes no animations/transitions copied. This is for composable slide tensors — pluck, duplicate, reorder like epistemic lego.

**Thumbnail as Cognitive Map**  
`thumbnail.py` grids slides into cols×(cols+1) JPGs (5×6=30 default), using LibreOffice subprocess for PDF->image at 100DPI, then PIL compositing. `--outline-placeholders` pulls from `inventory.py`'s regions, draws red borders. Constants scream optimization: fixed 300px thumbs, 95% JPEG. Surprising: hidden slides get gray placeholders; multi-grid auto-numbers (`prefix-1.jpg`). Assumption: visual skimming > content deep-dive. Tension: tempdir subprocess feels heavy/fragile (platform-specific?), yet ties back to inventory for "issues" visualization. This renders the *shape* of knowledge in a deck.

**Interwoven Complementarity**  
All scripts shepard/claude-named path screams Anthropic origin. `replace.py` imports `InventoryData` directly from `inventory.py`; `thumbnail.py` calls `extract_text_inventory()`. No html2pptx.js peek, but JS hints web-to-PPTX bridge. Assumption: PPTX=epistemic medium for human-AI duality (Yanantin project). Tension: py3 shebangs + six/pptx compat libs suggest cross-era evolution; heavy XML/low-level hacks betray `python-pptx` limitations.

### Declared Losses
Skipped `html2pptx.js` entirely — JS in Python land felt like a foreign envoy; would've needed runtime to grok DOM->shapes mapping. Ignored truncated lines (e.g., `rearrange_presentation()`'s 82+ lines, `detect_frame_overflow()`'s 236) — surface patterns were loud enough; internals likely boilerplate. No runtime test — can't confirm rel-copy fragility or overflow math. Chose not to hypothesize full Yanantin stack; local vantage suffices.

### Open Questions
Does the pipeline close the loop — inventory → AI rewrite → replace → thumbnails? How does `html2pptx.js` feed in (web-scraped content?)? Why six.py in 2023+ code (legacy lock-in)? Overflow detection in `replace.py`: used for auto-truncation or just reporting? Animations/master slides handled, or firewalled out?

### Closing
This is tensor surgery on corporate shamanism — PPTX as composable thoughtforms, where inventory observes, replace intervenes, rearrange/thumbnail visualizes. Yanantin's duality shines: human designs audited by code, AI content surgically grafted. Next scout: trace upstream to AI generator or `html2pptx.js`; test edge cases like animated/grouped charts. Playful precision, no fluff — the code *means* observability at slide granularity. I saw raw; nothing made up.