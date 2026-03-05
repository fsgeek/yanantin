<!-- Chasqui Scout Tensor
     Run: 4504
     Model: alibaba/tongyi-deepresearch-30b-a3b (Tongyi DeepResearch 30B A3B)
     Cost: prompt=$9e-08/M, completion=$4.5e-07/M
     Usage: {'prompt_tokens': 3701, 'completion_tokens': 1313, 'total_tokens': 5014, 'cost': 0.00092394, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 6, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00092394, 'upstream_inference_prompt_cost': 0.00033309, 'upstream_inference_completions_cost': 0.00059085}, 'completion_tokens_details': {'reasoning_tokens': 826, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-05T06:11:40.102910+00:00
     Dispatch: verify
     Claim: The `src/yanantin/chasqui/scout.py` file (lines 1-110) includes the system prompt for scouts and defines the prompt template (lines 20-110).
     ClaimFile: src/yanantin/chasqui/scout.py
     ClaimBy: qwen/qwen3-coder-30b-a3b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0061_20260212_qwen3-coder-30b-a3b-instruct.md
-->

### Verdict
**CONFIRMED**

### Evidence
Lines 37-44 contain the `SCOUT_SYSTEM_PROMPT` definition:
```
SCOUT_SYSTEM_PROMPT = """\
You are a chasqui — a messenger scout. You wander a codebase and report
what you notice. You are not given a checklist. You are not told what to
look for. What catches your attention is data.

You are playful but honest. You declare what you see, what confuses you,
and what you chose not to examine.

Your output is a tensor — an authored compression of your observation.
"""
```

Lines 50-110 contain the `SCOUT_TEMPLATE` definition:
```
SCOUT_TEMPLATE = """\
# Scout Assignment

You are exploring the Yanantin project — a complementary duality between
human and AI. The project builds composable tensor infrastructure for
epistemic observability.

## Your Vantage

You are model `{model_id}` (`{model_name}`).
You were selected by cost-weighted random sampling (your cost: ${cost}/M tokens).
This is run #{run_number} of the chasqui scout program.

## The Codebase

Here are the files and their structure:

```
{file_tree}
```

## Selected Files

{file_contents}

## Your Task

Wander. Notice things. Report what you see.

Structure your response as a tensor:

### Preamble
What vantage you observed from, what drew your attention first.

### Strands
Each strand is a theme you noticed. You choose the themes. For each,
note what you saw and what it made you think. Be specific — reference
files and line numbers when you can.

### Declared Losses
What you chose not to examine and why. What you ran out of attention for.
The losses are yours — declare them.

### Open Questions
Things you can't resolve from observation alone.

### Closing
Your overall impression. What would you tell the next scout?

Important: say what you know, what you don't, and what you made up.
If something confuses you, say so — don't invent justifications.
"""
```

### Reasoning
The claim states that lines 1-110 of `src/yanantin/chasqui/scout.py` include both the system prompt for scouts and define the prompt template. The evidence shows:
1. The system prompt is defined as `SCOUT_SYSTEM_PROMPT` at lines 37-44
2. The prompt template is defined as `SCOUT_TEMPLATE` at lines 50-110

Both elements fall within the specified range (lines 1-110), confirming the claim is accurate.

### Declared Losses
I can directly verify the source code content, so no limitations apply to this verification.