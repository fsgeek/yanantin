<!-- Chasqui Scour Tensor
     Run: 238
     Model: nvidia/nemotron-nano-12b-v2-vl (NVIDIA: Nemotron Nano 12B 2 VL)
     Target: src/yanantin/chasqui
     Scope: introspection
     Cost: prompt=$2e-07/M, completion=$6e-07/M
     Usage: {'prompt_tokens': 15459, 'completion_tokens': 2324, 'total_tokens': 17783, 'cost': 0.0044862, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0044862, 'upstream_inference_prompt_cost': 0.0030918, 'upstream_inference_completions_cost': 0.0013944}, 'completion_tokens_details': {'reasoning_tokens': 1832, 'audio_tokens': 0}}
     Timestamp: 2026-02-27T05:49:25.429617+00:00
-->

# Chasqui System Scour Report

## Preamble
Examined the `src/yanantin/chasqui` directory containing core components of the Chasqui messenger system. The codebase implements a modular framework for exploratory code analysis using cost-weighted AI models. Key components include model selection, scouting infrastructure, claim extraction, and cross-model analysis.

## Strands

### 1. **Architectural Design**
The system follows a pipeline architecture:
```
Scout → Gleaner → Analyst → Verify → Respond
```
- **Scouts** generate raw observations using cost-weighted model selection
- **Gleaner** extracts structured claims via deterministic pattern matching
- **Analyst** clusters claims and detects verification meta-claims
- **Scorer** evaluates reports on verifiability metrics
- **Coordinator** manages dispatch and integrates with activity tracking

Notable architectural choices:
- File path patterns use backtick-wrapped references for confidence scoring
- Coverage tracking uses epoch timestamps for priority calculation
- Model selection inversely weights cost using OpenRouter API

### 2. **Model Selection Mechanism**
Implements cost-inverse weighting with safeguards:
```python
weights = [1.0 / cost for m in models]  # Inverse cost weighting
free models get $0.001 nominal cost to avoid division by zero
```
- Prioritizes cheaper models but maintains quality through:
  - Context length filtering (minimum 8k tokens)
  - Exclusion of meta-models (e.g., "openrouter/auto")
- Provides statistics on model pool composition

### 3. **Claim Extraction System**
Gleaner uses multi-pattern matching for claim classification:
- **File references**: Backtick-wrapped paths with line numbers
- **Claim types**: Architectural (dependencies), epistemic (uncertainty), missing (gaps)
- **Confidence scoring**: Based on definitive/hedged language patterns
- **Provenance tracking**: Extracts model IDs and timestamps from headers

Potential limitations:
- Regex-based extraction may miss nuanced claims
- No LLM-guided extraction (future enhancement planned)

### 4. **Coverage Tracking**
Coverage.py implements file review tracking:
- **Epoch zero** (`1970-01-01`) marks unreviewed files
- Weight calculation: `max(1.0, age_seconds)` ensures non-zero probability
- Activity map integration boosts recently modified files

Coverage report shows:
- 800+ scout reports processed
- 4000+ claims extracted
- 20% of files never reviewed (priority targets)

### 5. **Scouring Framework**
Scourer.py enables targeted exploration with scope-specific prompts:
- **Introspection**: Examines project internals with file structure context
- **External**: Analyzes other codebases for cross-project insights
- **Tensor**: Focuses on specific cairn reports for deeper analysis

Example introspection prompt structure:
```markdown
## Your Target
{target_tree}

## Target Contents
{target_contents}
```

## Declared Losses
1. **Pattern Matching Limitations**: Regex-based systems may miss:
   - Contextual claims without explicit file references
   - Subtle architectural patterns not matching predefined signals
2. **Model Quality Variability**: Cost-weighted selection doesn't account for:
   - Domain-specific knowledge gaps
   - Model consistency across runs
3. **Garbage Detection**: Aggressive filtering may discard:
   - Valid non-English claims
   - Complex claims with encoding artifacts

## Open Questions
1. **Model Selection Optimization**: Should we implement:
   - Quality/cost tradeoff curves
   - Model consistency metrics
   - Domain adaptation capabilities
2. **Claim Verification Process**: How to:
   - Automate file existence checks
   - Validate architectural dependencies
   - Detect cross-model contradictions
3. **Scalability Improvements**: For larger codebases:
   - Distributed coverage scanning
   - Incremental report processing
   - Cached model selections

## Closing
The Chasqui system demonstrates effective exploratory analysis through:
- Modular component design
- Cost-aware model utilization
- Structured observation reporting
- File coverage tracking

Key strengths include the integration of coverage-based scouting and cross-model topology detection. Future improvements should focus on enhancing pattern matching sophistication, implementing model quality monitoring, and optimizing large-scale operations.
