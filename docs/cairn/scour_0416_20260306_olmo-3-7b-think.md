<!-- Chasqui Scour Tensor
     Run: 416
     Model: allenai/olmo-3-7b-think (AllenAI: Olmo 3 7B Think)
     Target: src/yanantin/chasqui/gleaner.py
     Scope: introspection
     Cost: prompt=$1.2e-07/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 2622, 'completion_tokens': 3671, 'total_tokens': 6293, 'cost': 0.00104884, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00104884, 'upstream_inference_prompt_cost': 0.00031464, 'upstream_inference_completions_cost': 0.0007342}, 'completion_tokens_details': {'reasoning_tokens': 2750, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-06T21:59:03.372243+00:00
-->

### Preamble  
The target is `gleaner.py`, part of Yanantin's `chasqui` module, tasked with extracting structured claims from scout/scour reports to aid in epistemic observability. Its deterministic pattern-matching approach stands out as a deliberate tradeoff for reliability, avoiding LLMs entirely. The focus on categorizing claims (factual, architectural, etc.) and tracking provenance (source file/model) suggests a robust framework for traceability, though its reliance on regex introduces potential limitations in handling ambiguous or nuanced language.

---

### Strands  

#### 1. **Deterministic Claim Classification System**  
**What I Saw**:  
- Claims are categorized using regex patterns (e.g., `_DEFINITIVE_PATTERNS` for confidence, `_ARCHITECTURAL_PATTERNS` for structural claims).  
- Confidence scores default to 0.5 but are adjusted based on keywords like "always" or "missing."  
- `ExtractedClaim` includes `claim_type` (factual/epistemic/missing) and `file_references`, enabling targeted verification.  

**Thoughts**:  
- Strength: Avoids hallucinations by grounding extraction in explicit patterns, aligning with the project’s emphasis on verifiable observability.  
- Weakness: Overly rigid regex might misclassify claims (e.g., hedging phrases like "I suspect" could be missed if not explicitly matched).  
- **Connection to Project**: Directly enables the "Verify" step by providing structured, categorized claims for validation against code.  

**Example**:  
A line like `The API endpoint `/v1/data` is missing in `src/api/endpoints.py` would be flagged as `claim_type: "missing"` with high confidence (via `_MISSING_PATTERNS`).  

---

#### 2. **Provenance and Traceability**  
**What I Saw**:  
- `_extract_model_id` parses scout/scour headers to log `source_model` (e.g., `Model: ollama/mistral-7b`), critical for accountability.  
- `source_file` tracks which report a claim originates from.  

**Thoughts**:  
- Strength: Ensures traceability from raw reports to specific codebase artifacts, crucial for audits.  
- Weakness: Assumes consistent header formatting; edge cases (e.g., malformed model IDs) could break.  
- **Connection to Project**: Aligns with "composable tensor infrastructure" by linking claims to verifiable sources.  

**Example**:  
A claim `This feature is documented in the Strands section` would log `source_file: "report.md"` and `source_model: "scout-3.7b"`.  

---

#### 3. **Section and Strand Parsing for Report Structure**  
**What I Saw**:  
- `_extract_strands_section` identifies sections with "Strands" headings (e.g., `**Strands**`) to isolate focused content.  
- Sentence splitting (`_split_sentences`) collapses multi-line markdown into coherent units.  

**Thoughts**:  
- Strength: Handles hierarchical reporting (e.g., Strands sections) for targeted extraction.  
- Weakness: Fallback to full text if no "Strands" section exists risks missing context-specific claims.  
- **Connection to Project**: Supports the pipeline’s need to parse structured reports (likely markdown) for clarity.  

**Example**:  
A report with a `**Strands**` heading followed by claims about module dependencies would prioritize those claims.  

---

#### 4. **Confidence Scoring via Keyword Matching**  
**What I Saw**:  
- Definitive language (e.g., "always", "contains") boosts confidence scores.  
- Quantitative claims (e.g., "10 files") receive higher confidence via `_QUANTITATIVE_PATTERN`.  

**Thoughts**:  
- Strength: Quantifiable claims are verifiable, aligning with "epistemic observability."  
- Weakness: Subtle hedging (e.g., "might" in passive voice) may not trigger confidence boosts.  
- **Connection to Project**: Enables prioritization of claims that can be directly checked against code.  

**Example**:  
`The `main.py` module imports `utils` from `utils module` (line 42)` would score high confidence due to the explicit file reference and quantifier "line 42."  

---

### Declared Losses  
1. **Implementation Details of Claim Processing**:  
   - Did not inspect the actual `gleaner.Gleaner` class methods (e.g., `extract_claims()`), so the logic for iterating over sentences, applying patterns, and populating `ExtractedClaim` instances remains opaque.  
   - Uncertain how confidence scores are aggregated (e.g., weighting different pattern matches).  

2. **Handling Non-English or Ambiguous Claims**:  
   - Regex patterns are hardcoded for English. Claims in other languages or with nuanced phrasing (e.g., "likely" in a non-hedging context) may be misclassified or missed.  

3. **Edge Cases in Section/Strand Parsing**:  
   - No visibility into how `_extract_strands_section` handles nested headings or inconsistent formatting (e.g., headings with mixed case or extra markdown).  

4. **Missing Validation for File References**:  
   - The `file_references` list captures paths but does not verify if files exist in the codebase. A claim about a missing file might incorrectly flag a non-existent path as valid.  

---

### Open Questions  
1. **How Are Confidence Scores Calculated?**  
   - Are definitive/hedged patterns weighted differently? For example, does mentioning a file path (`_PATH_PATTERN`) inherently boost confidence?  

2. **Handling Mixed Claim Types**:  
   - What if a claim is both architectural (e.g., "The API uses an invariant constraint") and epistemic ("I’m unsure if this is maintained")? The current system might categorize it as one type, but the report might need disambiguation.  

3. **Quantitative Claim Limitations**:  
   - The `_QUANTITATIVE_PATTERN` matches "files" or "modules," but could miss metrics like percentages or performance benchmarks (e.g., "30% faster execution").  

4. **Provenance Header Variability**:  
   - What if scout/scour headers use inconsistent naming (e.g., `Model: SomeModel` vs. `Model: SomeModel (v1)`)? The current `_extract_model_id` function may fail.  

---

### Closing  
This `gleaner.py` is a well-structured foundation for deterministic claim extraction, emphasizing traceability and categorization over ambiguity. Its strengths lie in avoiding LLM reliance and providing clear metadata for verification. However, its rigid pattern-matching approach risks missing nuanced claims or edge cases in report formatting. For improvement:  
- **Add unit tests** for regex patterns to validate coverage of corner cases.  
- **Refine confidence scoring** to account for subtle hedging or quantifiers beyond explicit keywords.  
- **Implement file existence checks** for `file_references` to prevent false positives.  
- **Document header formats** more explicitly to reduce parsing ambiguities.  

This module is a critical enabler of the project’s observability goals but requires careful calibration to handle real-world report diversity.