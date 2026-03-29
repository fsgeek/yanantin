<!-- Chasqui Scout Tensor
     Run: 8570
     Model: openai/gpt-oss-safeguard-20b (OpenAI: gpt-oss-safeguard-20b)
     Cost: prompt=$7.5e-08/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 2787, 'completion_tokens': 2672, 'total_tokens': 5459, 'cost': 0.001010625, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.001010625, 'upstream_inference_prompt_cost': 0.000209025, 'upstream_inference_completions_cost': 0.0008016}, 'completion_tokens_details': {'reasoning_tokens': 1221, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-29T20:44:16.400097+00:00
     GenerationID: gen-1774817052-eVxGDH9qOtrEHNMqgXR6
-->

**Preamble**  
I landed in `src/yanantin/query/`, a tiny but dense slice of a larger
“epistemic observability” system. What first drew me in was the
dual‑use of the same data model for *queries* and *facts*: the
`QueryFactRecorder` writes a query’s metadata back into the very
activity stream it reads from. It feels like the project is deliberately
making queries first‑class citizens in the same universe that holds
user events. That reflexive design is the hook that made me read on.

---

### Strands

| # | Theme | Observation | What it suggests |
|---|-------|-------------|------------------|
| 1 | **Python‑only filtering** | `engine.execute` pulls *all* facts that match the time range and provider, then applies `_apply_content_filters` in pure Python. No push‑down to SQL or AQL. | The system prioritises simplicity over performance. Perhaps the underlying stores are small‑scale or the designers expect the data volume to be modest. |
| 2 | **Dot‑path resolution & sentinel** | `_resolve_dotpath` walks a dict using `path.split(".")`, returning a unique `_MISSING` object if any key is absent. | A lightweight “optional chaining” helper that keeps the filter logic clean. Using a singleton sentinel avoids a `KeyError` but also means any value equal to that sentinel would be mis‑interpreted (unlikely in practice). |
| 3 | **Filter operators** | Operators are handled with a long `if` chain: `eq`, `contains`, `glob`, `gt`, etc. `contains` and `glob` cast to `str`. | The design is intentionally permissive: any value can be coerced to a string for text‑based ops, but numeric ops rely on native comparisons. This could silently fail if types clash. |
| 4 | **Missing‑value handling** | For `exists`, the presence of a key is enough. For all other ops, if `_MISSING` is returned, the filter fails (`False`). | A strict “AND” logic: a fact must satisfy *every* filter. The `exists` operator is the only one that ignores the value. |
| 5 | **Query metadata as facts** | `QueryFactRecorder` creates a `FactRecord` with `provider_id = uuid5(NAMESPACE_DNS, "yanantin.query.service")`. It serialises the whole `QuerySpec` with `model_dump(mode="json")`. | The query service has a deterministic provider ID, ensuring all query facts can be grouped. Serialising the spec preserves the exact shape of the request, which could be useful for debugging or replay. |
| 6 | **No result‑fact recording** | The recorder only stores the query’s *metadata* (spec, timing, counts), not the facts that were returned. | Avoids duplication and keeps the stream lean. The assumption is that the query itself is an observation; the data it fetched is already in the stream. |
| 7 | **Summaries over pagination** | If `spec.summarize` is true, `_build_summary` runs on the *entire* filtered list before pagination. The summary contains `total_count`, provider breakdown, top `content_hashes`, and `sample_data_keys`. | The engine provides a lightweight “stats‑only” mode, but it still fetches every matching fact. This is a potential scalability bottleneck. |
| 8 | **Extensibility via `extra="allow"`** | `QuerySpec`, `QuerySummary`, and `QueryResult` all allow arbitrary extra fields. | The API is designed to grow without breaking existing consumers. New NLP or confidence‑scoring layers can attach metadata without redefining the models. |
| 9 | **Timing granularity** | `execution_time_ms` uses `time.monotonic()` and is rounded to two decimals. | A pragmatic choice for profiling; the timestamp on `QueryResult` defaults to UTC now, ensuring the fact’s timestamp is the moment the result was assembled, not the query’s start time. |
| 10 | **Provider‑centric stats** | `QueryEngine.get_stats` and `list_providers` expose per‑provider counts via the store. | The system treats each provider as a logical shard; the API surfaces that granularity, hinting at a multi‑tenant or multi‑source architecture. |

---

### Declared Losses

* **Store internals** – I did not dig into `ActivityStreamStore` or `FactRecord`. Their API shapes the engine’s expectations (e.g., `query_range`, `count_facts`), but I’m not sure how they actually fetch data or what storage back‑end they use.  
* **Summary implementation** – The truncated `_build_summary` body was omitted, so I’m guessing on its logic.  
* **CLI/HTTP glue** – `__main__` and any routing code are outside my view; I can’t see how a user actually supplies a `QuerySpec`.  
* **Testing and error handling** – No tests are visible here; I don’t know how edge cases (e.g., malformed filters) are handled.

---

### Open Questions

1. **Scalability** – How does the engine cope with millions of facts? Does it ever employ database push‑down or batch streaming?  
2. **Type safety** – Are there any runtime checks that the resolved value matches the expected type for numeric ops?  
3. **Content hash filtering** – Why is it separated from `ContentFilter`? Is it meant as a cheap index‑like shortcut?  
4. **Provider ID scheme** – What guarantees that `uuid5(NAMESPACE_DNS, "yanantin.query.service")` is unique across deployments?  
5. **Extensibility path** – How will new operators (e.g., regex, in) be added without breaking the `if` chain?  
6. **Result caching** – Is there any caching layer that could short‑circuit repeated queries?  
7. **Pagination strategy** – Does the engine support cursor‑based pagination, or is it purely offset/limit?  

---

### Closing

The query subsystem is a minimalist, reflexive layer: it treats every query as a fact, records it, and can summarize results without pulling them back into the client. Its design favours **clarity and extensibility** over raw performance—most filtering is done in Python, and the API is built to grow with `extra="allow"`.

For the next scout: focus on the store implementation to understand how data is actually retrieved, and on the missing `_build_summary` logic to see how the system aggregates over large result sets. Also, look at how `QuerySpec` is constructed from user input (CLI flags or NLP), because that will reveal how the “composable tensor infrastructure” is intended to be used in practice.