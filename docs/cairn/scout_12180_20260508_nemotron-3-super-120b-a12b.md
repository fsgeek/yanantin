<!-- Chasqui Scout Tensor
     Run: 12180
     Model: nvidia/nemotron-3-super-120b-a12b (NVIDIA: Nemotron 3 Super)
     Cost: prompt=$9e-08/M, completion=$4.5e-07/M
     Usage: {'prompt_tokens': 1315, 'completion_tokens': 4000, 'total_tokens': 5315, 'cost': 0.0021315, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0021315, 'upstream_inference_prompt_cost': 0.0001315, 'upstream_inference_completions_cost': 0.002}, 'completion_tokens_details': {'reasoning_tokens': 4216, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-08T05:41:46.526819+00:00
     GenerationID: gen-1778218703-Vx0JSiPiv0ckitmWLYWZ
-->

### Preamble
I was dropped into the `references/` directory of the MCP integration skill, specifically examining `authentication.md`. This file serves as a guide for plugin developers on authenticating MCP (Model Context Protocol) servers within Claude Code plugins. What first drew my attention was the stark contrast between the "automatic" OAuth flow—where Claude Code handles everything—and the manual, environment-variable-driven token-based approaches. This dichotomy immediately raised questions about trade-offs in convenience, security, and developer burden.

### Strands

**Strand 1: The Illusion of Full Automation in OAuth**  
- *What I saw*: The OAuth section describes a seamless 6-step flow handled entirely by Claude Code, with a configuration example requiring only `{"service": {"type": "sse", "url": "https://mcp.example.com/sse"}}`—no auth details needed. It claims Claude Code manages token storage, refresh, and even browser-based consent.  
- *What it made me think*: This assumes Claude Code possesses intrinsic knowledge of OAuth endpoints (authorization/token URLs) and client credentials for services like Asana or GitHub. Yet, the file never explains *how* Claude Code obtains these details. Is it hardcoded? Dynamically discovered? For "custom OAuth servers," the file offers zero configuration guidance, creating a critical gap: if a plugin targets a non-listed service, how does the developer specify OAuth parameters? The automation feels conditional—it works only for pre-approved services, leaving custom implementations undocumented and forcing developers into token-based methods despite preferring OAuth’s security benefits. This reveals a tension between user convenience (no setup) and extensibility (no clear path for novel services).

**Strand 2: Token-Based Auth Shifts Burden to the User**  
- *What I saw*: Token-based methods (Bearer, API keys, custom headers) require plugins to define headers like `"Authorization": "Bearer ${API_TOKEN}"`, with explicit instructions to document required environment variables in the README.  
- *What it made me think*: Unlike OAuth—where Claude Code shields plugins from tokens entirely—this approach forces plugin developers to expose secrets via environment variables, pushing secret management onto end-users. The file mentions tokens are "stored securely by Claude Code" only for OAuth; for token-based auth, it implies tokens live in the plugin’s config (or process environment), accessible to the plugin and potentially leaking via logs or debugging. This creates a security stratification: OAuth offers plugin-side token isolation (safer for plugin developers), while token-based auth demands user vigilance. The file never addresses mitigations (e.g., integrating with secret vaults) or warns about risks like accidental token exposure in serverless environments, suggesting an assumption that users will handle secrets correctly—a risky premise in practice.

**Strand 3: The Truncation Anomaly**  
- *What I saw*: In the "Documenting Token Requirements" section, the README example ends abruptly with:  
  ```markdown
  ## Setup
  ### Required Environment Variables
  Set these environment variables before using the plugin:
  ... (400 more lines