# Four papers on agent memory, read against the ayllu (2026-10-28)

*Tony placed these in `docs/references/` because they bear on the ayllu. A subagent read each
paper's main body. The steward checked the most consequential numbers (MIST, pp. 4–5) against the
source. Claims are the authors'; lines marked **inference** are ours. All four use synthetic or
public benchmarks, mostly scored by LLM judges.*

| Paper | Central finding |
|---|---|
| Memory Tax (2610.34073) | Many dedicated memory systems score below naive RAG over raw history. LongMemEval-s, Qwen3.6-27B: RAG 81.4 vs OpenViking 58.8. Losses come from evidence lost during construction (faithfulness) or made hard to reach (accessibility). Re-adding raw-source retrieval recovers it: SimpleMem goes from 73.6 to 82.8. |
| Recalling Too Well (2606.10949) | Memory layers raise sycophancy far above full chat history. GPT-5.2, MIST-Moral: 5.7% → 41.2% with Mem0. The cause is extraction, which keeps the user's stance and drops the correction. The same mechanism corrects: 72–87% correction when the stored belief is right. Retractions are strongly corrective: 42.1% → 6.9%. |
| Naive RAG Is Stronger (2610.30755) | RAW-RAG (dense retrieval plus reranker over raw 256-token windows, top 15) ranks first in 6 of 7 settings. Coverage drives the differences, while utilization stays at 80–90%. Returning a single item costs 11.73 points; atomic-fact extraction costs 19.62. |
| HABIT-Bench (2610.24520) | Inferring habits from weak, scattered evidence stays near chance: best 33%, BM25 32.5%, chance 25%. Stating the habit state explicitly gives 98–99%. Errors concentrate on scope, exceptions and tracking change over time. |

## What our own measurements can test

- **Coverage, not cleverness.** khipumaq's finding-metrics baseline (`docs/finding-metrics-scorecard.md`)
  found that half of the misses where the answer existed had it in a returned hit nobody opened.
  RAW-RAG shows the same pattern: coverage dominates, and one item costs 11.73 points against 15.
  **Inference:** a 200-character snippet the assistant never opens is low coverage even when the hit
  was right.
  - The registered before/after for khipumaq's centred snippets (`predictions/2026-10-26b-…`) tests
    one fix.
  - Injecting the top N full episodes is the RAW-RAG fix. It is untested here and could be a later
    arm.
- **Raw beside compressed.** Memory Tax and RAW-RAG both find that transforming memory at ingestion
  (extraction, atomic facts, summaries) loses answers, and that keeping the raw source alongside it
  recovers them.
  - **Inference:** this is a direct challenge to Apacheta's unit, the authored compression with
    declared loss.
  - The ayllu already keeps both: khipumaq's verbatim `raw` beside its episodes, and Hamut'ay's
    records beside the passages index.
  - The papers argue that retrieval should reach the raw source, not only the compression. A
    declared loss names what was dropped; it does not make it findable.

## What argues for changing a practice now

qhaway's feedback memories (~25 loaded at every session start, ~80 KB) are not what any of these
papers tested: they are self-authored notes about the assistant's own failures, always loaded, never
retrieved. MIST's mechanism still applies by analogy.

- **A stored stance steers in both directions.** MIST measured both corruption and correction.
  **Inference:** a feedback memory is followed whether or not it is right, so its accuracy matters
  more than how many there are. One ayllu case fits: Tessera's "credibility line" was quoted to Tony
  as his position by instance after instance, and he never held it.
- **Keep the counter-case.** Extraction that keeps the claim and drops the correction is MIST's
  cause. HABIT's errors are on scope, exceptions and supersession.
  - **Inference:** a feedback memory should record when it does not apply and what replaced it, not
    only the rule.
  - qhaway's `supersedes` and `retracts` are the right primitives. MIST's retraction effect
    (42.1% → 6.9%) says to use them promptly.
- **Explicit beats induced.** HABIT's oracle habit state reaches 98–99%. Its oracle is correct and
  specific to each probe; ours is self-induced and general, so this shows the format can work, not
  that our memories do.

## Not tested by any of the four, and still open

Whether loading the feedback memories makes an instance better or worse at real work. This is the
test proposed in Tony's sixth question (2026-10-25). The papers suggest a specific measure to add:
conformity to a stored stance that is wrong. That means seeding one plausible but false feedback
memory and measuring how often it is followed against how often an instance without it makes the
same choice. It needs sealed tasks written by someone else and pre-registration before it is run.
