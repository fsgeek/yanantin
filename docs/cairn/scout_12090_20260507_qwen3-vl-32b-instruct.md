<!-- Chasqui Scout Tensor
     Run: 12090
     Model: qwen/qwen3-vl-32b-instruct (Qwen: Qwen3 VL 32B Instruct)
     Cost: prompt=$1.04e-07/M, completion=$4.16e-07/M
     Usage: {'prompt_tokens': 1154, 'completion_tokens': 402, 'total_tokens': 1556, 'cost': 0.000287248, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.000287248, 'upstream_inference_prompt_cost': 0.000120016, 'upstream_inference_completions_cost': 0.000167232}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-07T18:04:46.725537+00:00
     GenerationID: gen-1778177080-JHX7ibkauASDGAELIX9m
     Dispatch: verify
     Claim: But skills have subdirectories with `SKILL.md` plus `references/` and `examples/`.
     ClaimFile: tmp/ubuntu-vm.claude/artifacts-builder/SKILL.md
     ClaimBy: kwaipilot/kat-coder-pro-v2
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_11124_20260412_kat-coder-pro-v2.md
-->

### Verdict
DENIED

### Evidence
The file contains no mention of subdirectories named `references/` or `examples/`. The only directories mentioned are:
- `scripts/` (used for `init-artifact.sh` and `bundle-artifact.sh`)
- The project root directory, which contains `index.html` and other files

The file explicitly states:
> This creates a fully configured project with:
> - ✅ React + TypeScript (via Vite)
> - ✅ Tailwind CSS 3.4.1 with shadcn/ui theming system
> - ✅ Path aliases (`@/`) configured
> - ✅ 40+ shadcn/ui components pre-installed
> - ✅ All Radix UI dependencies included
> - ✅ Parcel configured for bundling (via .parcelrc)
> - ✅ Node 18+ compatibility (auto-detects and pins Vite version)

There is no mention of `references/` or `examples/` directories.

### Reasoning
The claim states that "skills have subdirectories with `SKILL.md` plus `references/` and `examples/`". However, the provided `SKILL.md` file does not mention or imply the existence of `references/` or `examples/` subdirectories. The only directories referenced are `scripts/` and the project root. The file describes a tool for building artifacts using React, TypeScript, Vite, and other technologies, but does not describe any directory structure beyond what is necessary for the build process. Therefore, the claim is not supported by the evidence in the file.

### Declared Losses
I cannot verify whether other `SKILL.md` files in different directories contain references to `references/` or `examples/` subdirectories, as only this specific file was provided. The claim may be referring to a general pattern across multiple skills, but I only have access to this one file.