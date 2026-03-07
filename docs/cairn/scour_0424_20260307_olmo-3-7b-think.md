<!-- Chasqui Scour Tensor
     Run: 424
     Model: allenai/olmo-3-7b-think (AllenAI: Olmo 3 7B Think)
     Target: src/yanantin/chasqui/gleaner.py
     Scope: introspection
     Cost: prompt=$1.2e-07/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 2622, 'completion_tokens': 3468, 'total_tokens': 6090, 'cost': 0.00100824, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00100824, 'upstream_inference_prompt_cost': 0.00031464, 'upstream_inference_completions_cost': 0.0006936}, 'completion_tokens_details': {'reasoning_tokens': 3006, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-07T02:24:20.767526+00:00
-->

### Preamble  
The Gleaner module in `gleaner.py` is a deterministic, regex-based system for extracting structured claims from scout/scour reports in the Yanantin project. What drew my attention first was its reliance on pattern matching (no LLMs) to classify claims by type and score confidence—a critical design choice for reproducibility in observability. The structured ExtractedClaim dataclass and organized regex patterns suggest a focus on reliability, but gaps in confidence scoring and edge-case handling hint at areas needing refinement.

---

### Strands  

#### 1. **Deterministic Extraction Core**  
**What I saw**: The module uses regex to parse claims from reports, with patterns categorized into paths, provenance, sentence boundaries, and claim types. Key functions like `_PATH_PATTERN` and `_strip_headers` extract file references and model IDs from headers.  
**Thoughts**:  
- **Strength**: Avoids LLM hallucinations by relying on explicit rules, aligning with Yanantin’s goal of verifiable observability.  
- **Assumptions**: Reports must adhere to consistent formatting (e.g., backtick-wrapped file paths, section headings with **bold** tags). Deviations could lead to missed claims or misclassifications.  
- **Breakage Risk**: If a report references a file without backticks (e.g., raw text paths), `_PATH_PATTERN` would fail to capture it, leaving claims incomplete.  

#### 2. **Provenance and Metadata Handling**  
**What I saw**: Functions like `_extract_model_id` parse scout/scour headers to identify the generating model (e.g., `Model: olmo-3-7b`), which is stored in `ExtractedClaim.source_model`.  
**Thoughts**:  
- **Connection to Project**: This metadata is critical for tracking the provenance of claims, ensuring Verify can cross-check claims against the correct model’s output.  
- **Limitation**: The regex for header formats assumes consistent syntax. Future work might need to handle variations in header styles.  

#### 3. **Claim Classification Framework**  
**What I saw**: Pattern lists (`_ARCHITECTURAL_PATTERNS`, `_EPISTEMIC_PATTERNS`, etc.) define claim types based on keywords (e.g., "depends on" → architectural). Confidence is default to 0.5 but could be adjusted via pattern matches.  
**Thoughts**:  
- **Strength**: Explicit categorization helps downstream systems (e.g., Verify) prioritize or flag claims.  
- **Gaps**:  
  - No logic to dynamically adjust confidence scores based on detected patterns (e.g., a sentence with both hedging and definitive language).  
  - Claims with no matching patterns default to "factual," but some might belong to "epistemic" (e.g., "I wonder if X is secure").  

#### 4. **Section Extraction and Structure Parsing**  
**What I saw**: Functions like `_extract_strands_section` target "Strands" headings to extract specific content (e.g., test results or component summaries).  
**Thoughts**:  
- **Purpose**: Likely used to isolate structured sections (e.g., Strands for individual project components) in reports.  
- **Potential Issue**: If reports lack consistent section headings (e.g., missing "**Strands**"), this logic fails, losing granular claim extraction.  

---

### Declared Losses  
1. **Confidence Scoring Mechanism**: The default 0.5 confidence and lack of dynamic scoring logic prevent precise trust in claims. For example, a definitive statement like "The API uses HTTP" (detected via `_DEFINITIVE_PATTERNS`) isn’t currently weighted higher than a hedged one.  
2. **Edge Cases in Sentence Splitting**: The truncated `_split_sentences` function’s implementation isn’t visible, raising concerns about how multi-line markdown renders or edge cases (e.g., abbreviations followed by periods).  
3. **No Handling for Ambiguous Claims**: Sentences without clear keywords (e.g., "The code is modular") default to "factual," but might better fit "architectural" or "epistemic."  

---

### Open Questions  
1. **Pattern Coverage Gaps**:  
   - How does the system classify claims like "There’s no logging for Step X" (missing feature) vs. "Step X lacks logging" (architectural)? The `_MISSING_PATTERNS` includes "no exists," but contextual nuance (e.g., intent vs. observation) isn’t addressed.  
2. **Dependency Tracking**: Claims referencing other claims or prior context (e.g., "Step Y depends on Step X’s result") are treated as standalone. How does the Gleaner handle such dependencies?  
3. **Model ID Compatibility**: If future LLM-guided reports (a planned enhancement) include non-standard headers, will `_extract_model_id` break?  

---

### Closing  
The Gleaner is a robust foundation for structured claim extraction in Yanantin’s observability pipeline, emphasizing deterministic reliability over speculative LLM outputs. Its strengths lie in clear metadata capture (model sources, file references) and modular pattern organization. However, critical gaps in confidence scoring and edge-case handling could undermine its effectiveness. To improve:  
- **Implement confidence scoring** based on detected pattern matches (e.g., +0.2 for quantifiers, -0.3 for hedging).  
- **Add tests** for regex patterns against diverse report formats (e.g., inconsistent backtick usage, nested section headings).  
- **Refine claim type classification** to better distinguish "epistemic" vs. "architectural" in ambiguous cases.  

This module is vital for downstream validation but requires further polish to fully align with Yanantin’s mission of transparent, verifiable observability.