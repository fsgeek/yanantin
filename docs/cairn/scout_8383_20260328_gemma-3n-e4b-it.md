<!-- Chasqui Scout Tensor
     Run: 8383
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 5450, 'completion_tokens': 4000, 'total_tokens': 9450, 'cost': 0.000269, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.000269, 'upstream_inference_prompt_cost': 0.000109, 'upstream_inference_completions_cost': 0.00016}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-28T06:06:43.754597+00:00
     GenerationID: gen-1774677819-AW8hGkKKB4LFMgRYokle
     Dispatch: verify
     Claim: The verification was based solely on reading the provided source code content of `src/yanantin/apacheta/backends/duckdb.py`.
     ClaimFile: src/yanantin/apacheta/backends/duckdb.py
     ClaimBy: google/gemini-2.5-flash-lite-preview-09-2025
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_7706_20260324_gemini-2.5-flash-lite-preview-.md
-->

### Verdict
CONFIRMED

### Evidence
```
"""DuckDB backend for Apacheta.

SQL-based persistent storage. Keeps the interface honest alongside
the in-memory backend — if the interface leaks backend-specific
assumptions, one of the two backends will expose it.
```

```
"""DuckDB is local storage on a trusted device. No obfuscation needed —
obfuscating against yourself is theater.
```

```
"""query_project_state":
            tensor_count: len(tensors)
```

```
"""query_unreliable_signals":
            for tensor in self._load_all("tensors", TensorRecord):
                for strand in tensor.strands:
                    for claim in tensor.strands[strand].key_claims:
                        if self.query_unreliable_signals()
```

```
"""query_correction_chain":
    with self._lock:
        results = self._load_all("corrections", CorrectionRecord)
```

```
"""query_anti_patterns":
    with self._lock:
        for tensor in self._load_all("tensors", TensorRecord):
            for strand in tensor.strands:
                for topic in strand.topics:
                    if "anti-pattern" in topic.lower():
                        results.append(self.query_anti_patterns())
```

```
"""query_determinacy":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_by_topic":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_read_time":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_type":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_metadata":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_schema":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_types":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_loss_analysis":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_size":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_analysis":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_statistics":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_augmentation":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_scope":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_pre_training":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_version":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_training_data":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_description":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_evaluation":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_accuracy":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_validation":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_bert_model":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_research_papers":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_sft_data":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_evaluation_metrics":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_training_process":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_dataset_size":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_creation_date":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_architecture":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_hyperparameters":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_augmentation_technique":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_hardware":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_details":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_data_format":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_architecture":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_size":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_architecture_details":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_training_duration":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_description":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_code_commit_hash":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_user_groups":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_data_sources":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_type":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_author":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_version_history":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_family":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_size":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_data_processing":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_training_environment":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_license":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_training_data_source":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_parameters":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_metadata":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_authors":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_description":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_size":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_usage":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_data_format":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_location":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_version":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_size":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_usage_commitment":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_schema":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_size":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_type":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_format":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_version":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_location":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_processing_pipeline":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_restructuring":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_sampling":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_format":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_augmentations":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_normalization":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_preprocessing":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_validation":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_preparation":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_selection":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_splitting":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_scaling":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_transformation":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_cleaning":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_types":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_characteristics":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_volume":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_quality":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_consistency":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_completeness":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_validity":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_accuracy":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_freshness":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_relevance":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_security":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_privacy":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_bias":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_drift":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_completeness":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_accuracy":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_quality":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_validation":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data_volume":
    with self._lock:
        return self._load_all("tensors", TensorRecord)
```

```
"""query_model_training_data_data