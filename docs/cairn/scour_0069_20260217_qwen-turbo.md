<!-- Chasqui Scour Tensor
     Run: 69
     Model: qwen/qwen-turbo (Qwen: Qwen-Turbo)
     Target: src/yanantin/chasqui/gleaner.py
     Scope: introspection
     Cost: prompt=$5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 2609, 'completion_tokens': 1024, 'total_tokens': 3633, 'cost': 0.00033525, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00033525, 'upstream_inference_prompt_cost': 0.00013045, 'upstream_inference_completions_cost': 0.0002048}, 'completion_tokens_details': {'reasoning_tokens': 0}}
     Timestamp: 2026-02-17T08:12:29.996610+00:00
-->

# Tensor: Gleaner.py Inspection

## Preamble
I was directed to examine `src/yanantin/chasqui/gleaner.py`, a module responsible for extracting structured claims from scout and scour reports in the Yanantin project. My attention was immediately drawn to the comprehensive set of regular expressions and the structured data class `ExtractedClaim`, which suggests this module is foundational to the project's epistemic observability pipeline.

## Strands

### 1. **Claim Extraction Architecture (Lines 10-60)**
I observed a well-defined data structure `ExtractedClaim` that captures claims with rich metadata like `claim_type`, `confidence`, and `file_references`. This suggests the module is designed for systematic, structured extraction rather than raw text processing.

This connects to the broader project's goal of "composable tensor infrastructure for epistemic observability" by providing a standardized way to represent claims. The use of deterministic pattern matching instead of LLM calls reflects an assumption that explicit, rule-based extraction is sufficient for the current scope.

**Thoughts**: The design is clean but could benefit from more explicit type hints for the `file_references` field, which is currently a list of strings.

### 2. **Pattern Matching System (Lines 65-210)**
The module contains extensive regular expression patterns for identifying file paths, provenance headers, sentence boundaries, and various types of claims. These patterns are categorized by their purpose: confidence signals, claim types, and section extraction.

This is critical for the module's functionality and reflects an assumption that pattern matching is sufficient for extracting meaningful claims. However, the complexity of the patterns (e.g., `_PATH_PATTERN` and `_BARE_PATH_PATTERN`) suggests this approach may be brittle.

**Thoughts**: The use of regex for file path detection is reasonable, but the module might benefit from a more robust file system validation step to confirm that the extracted paths actually exist.

### 3. **Provenance Extraction (Lines 215-235)**
The `_extract_model_id` and `_strip_headers` functions are designed to extract metadata from scout and scour reports. This is essential for tracking the source of each claim, which is important for verification.

This connects directly to the project's goal of maintaining a verifiable audit trail of claims. The use of HTML comment headers for provenance suggests a specific format expectation that could be a point of fragility if the format changes.

**Thoughts**: The module assumes that all reports will have the expected provenance header format. If this changes, the extraction logic would break.

### 4. **Section Extraction (Lines 240-275)**
Functions like `_extract_section` and `_extract_strands_section` are designed to extract specific sections from the report, which is important for organizing and categorizing claims.

This reflects an assumption that reports are structured with clear headings, which may not always be the case. The fallback to the full body if no Strands section is found is a good design choice.

**Thoughts**: The module could benefit from more detailed error handling if the expected section structure is not found.

### 5. **Sentence Splitting (Lines 280-290)**
The `_split_sentences` function is designed to break text into sentences, which is essential for processing claims. However, the implementation is truncated, and the full logic is not visible.

**Thoughts**: The incomplete implementation of `_split_sentences` is a potential issue. The function's purpose and behavior are unclear, which could lead to problems in claim extraction.

## Declared Losses
- I did not examine the full implementation of `_split_sentences` because the code is truncated.
- I did not analyze the integration of this module with the rest of the Yanantin project, such as how extracted claims are used in the "Verify" stage.
- I did not investigate the potential for LLM-guided extraction, which is mentioned in the docstring but not implemented.

## Open Questions
- How are the extracted claims used in the "Verify" stage of the pipeline?
- What is the expected format of the reports that this module processes?
- How is the confidence score calculated, and what factors influence it?
- How are the different claim types (factual, architectural, epistemic, missing) used in the project?

## Closing
This module is a well-structured, pattern-based system for extracting claims from reports. It is designed with clear data models and extensive regular expressions to identify key elements like file paths, provenance, and claim types. However, its reliance on deterministic pattern matching and the assumption of a specific report format could be points of fragility.

If modifying this module, I would focus on improving the sentence splitting logic, adding more robust error handling, and considering how to integrate LLM-guided extraction in the future. The module is a critical component of the Yanantin project's infrastructure, and its reliability is essential for the overall system.