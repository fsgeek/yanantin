<!-- Chasqui Scour Tensor
     Run: 1523
     Model: mistralai/mistral-small-3.2-24b-instruct (Mistral: Mistral Small 3.2 24B)
     Target: src/yanantin/chasqui
     Scope: introspection
     Cost: prompt=$7.5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 17092, 'completion_tokens': 1334, 'total_tokens': 18426, 'cost': 0.00233868, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00233868, 'upstream_inference_prompt_cost': 0.00153828, 'upstream_inference_completions_cost': 0.0008004}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-02T05:41:56.395929+00:00
     GenerationID: gen-1775108412-adgyjLZxC1wIjvPMV9eB
-->

## Chasqui Module Analysis

### Overview
The `chasqui` module is a core component of the Yanantin project, designed to dispatch "messengers" (scouts and scourers) to explore and report on various aspects of the codebase. These messengers generate structured observations, known as tensors, which are stored in a cairn. The module includes components for selecting models, generating prompts, analyzing reports, and verifying claims.

### Key Components

1. **Model Selection (`model_selector.py`)**:
   - **Purpose**: Selects AI models for scouting tasks based on cost-weighted random sampling.
   - **Key Features**:
     - Models are weighted inversely by cost, favoring cheaper models.
     - Supports filtering models by context length and exclusion patterns.
     - Provides statistics on the model pool, including cost distribution and free models.

2. **Scout Dispatch (`scout.py`)**:
   - **Purpose**: Sends scouts into the codebase to generate tensors.
   - **Key Features**:
     - Constructs prompts for scouts, including file trees and prior findings.
     - Picks vantage directories weighted by coverage to ensure diverse exploration.
     - Generates structured tensors with preamble, strands, declared losses, open questions, and closing remarks.

3. **Scourer Dispatch (`scourer.py`)**:
   - **Purpose**: Targeted exploration with a specific scope (introspection, external, tensor, synthesis).
   - **Key Features**:
     - Constructs prompts for scourers with detailed instructions on what to examine.
     - Supports different scopes, each with its own template for generating tensors.

4. **Gleaner (`gleaner.py`)**:
   - **Purpose**: Extracts structured claims from scout and scour reports.
   - **Key Features**:
     - Uses deterministic pattern matching to extract claims.
     - Classifies claims by type (factual, architectural, epistemic, missing).
     - Scores confidence and deduplicates claims across reports.

5. **Scorer (`scorer.py`)**:
   - **Purpose**: Scores scout tensors on various axes (specificity, fabrication, efficiency, generativity, structure).
   - **Key Features**:
     - Extracts file references and open questions from scout reports.
     - Computes metrics like word count, strand count, and insight-per-token ratio.
     - Verifies the existence of referenced files.

6. **Analyst (`analyst.py`)**:
   - **Purpose**: Surfaces cross-model patterns from gleaner claims.
   - **Key Features**:
     - Filters garbage from models producing corrupted output.
     - Scores model quality based on claim density, reference density, and confidence.
     - Clusters claims by primary file reference and detects cross-model agreement.

7. **Attestation (`attestation.py`)**:
   - **Purpose**: Converts Chasqui verification results into Willay epistemic receipts.
   - **Key Features**:
     - Maps verification verdicts to Willay Evaluations with honest T/I/F values.
     - Records epistemic receipts with declared losses and file evidence.
     - Integrates with the Willay ledger for recording attestations.

8. **Coverage Tracker (`coverage.py`)**:
   - **Purpose**: Tracks which source files have been reviewed by scouts.
   - **Key Features**:
     - Scans the cairn to build a coverage map.
     - Computes selection weights based on coverage freshness.
     - Ensures new and stale code gets priority for review.

9. **Coordinator (`coordinator.py`)**:
   - **Purpose**: The heartbeat of Yanantin, dispatching messengers and managing the cairn.
   - **Key Features**:
     - Dispatches scouts and scourers with specific prompts.
     - Manages the cairn, where scout and scour tensors are stored.
     - Handles verification of claims and generation of reports.

### Connections and Broader Project Integration

- **OpenRouter Client**: The module uses the OpenRouter client to interact with various AI models.
- **Willay Integration**: Verification results are converted into epistemic receipts for Willay, a ledger for recording epistemic data.
- **Activity Stream**: Utilizes the activity stream to track recently observed file states, providing additional context for scouts.
- **DuckDB Store**: Queries the DuckDB store for activity data to build an activity map.

### Observations and Confusions

1. **Observations**:
   - The module is well-structured with clear separation of concerns.
   - It leverages deterministic pattern matching for extracting claims, ensuring reproducibility.
   - The use of cost-weighted random sampling for model selection ensures efficient use of resources.
   - The integration with Willay and the activity stream provides a comprehensive view of the codebase and its observations.

2. **Confusions**:
   - The exact details of how the Willay integration works, especially the mapping of verification verdicts to epistemic receipts, could be clearer.
   - The process of how scout and scour tensors are stored and retrieved from the cairn is not fully detailed in the provided code.
   - The interaction between the activity stream and the coverage tracker could be more explicitly described.

### Declarations

- **What I Chose Not to Examine**:
  - Detailed implementation of the OpenRouter client and its interactions with the `chasqui` module.
  - The internal workings of the Willay ledger and how it handles epistemic receipts.
  - The specific algorithms used for pattern matching and claim extraction in the Gleaner.

- **Open Questions**:
  - How does the module handle conflicts or discrepancies between different scouts' observations?
  - What mechanisms are in place to ensure the quality and reliability of the tensors generated by scouts and scourers?
  - How does the module evolve over time as new models and verification techniques are introduced?

### Closing

The `chasqui` module is a sophisticated and well-organized component of the Yanantin project, designed to facilitate deep and structured exploration of the codebase. Its use of cost-weighted model selection, deterministic pattern matching, and integration with external systems like Willay and the activity stream makes it a robust tool for epistemic observability. The module's focus on thorough but honest reporting ensures that the generated tensors are both useful and reliable for further analysis and verification.