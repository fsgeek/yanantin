<!-- Chasqui Scout Tensor
     Run: 9367
     Model: meituan/longcat-flash-chat (Meituan: LongCat Flash Chat)
     Cost: prompt=$2e-07/M, completion=$8e-07/M
     Usage: {'prompt_tokens': 3050, 'completion_tokens': 1019, 'total_tokens': 4069, 'cost': 0.0014252, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0014252, 'upstream_inference_prompt_cost': 0.00061, 'upstream_inference_completions_cost': 0.0008152}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-03T07:03:26.568677+00:00
     GenerationID: gen-1775199796-LJIzrtauL4cuPPJYDKG1
-->

### Preamble
Dropped into the MCP integration references section, my attention was immediately drawn to the *asymmetry* in authentication capabilities between different server types. The authentication guide opens with OAuth as an "automatic" feature for SSE servers, while stdio servers are conspicuously absent from the OAuth discussion. This creates an implicit architectural tension that wasn't explicitly stated but felt throughout the documents.

### Strands

**1. OAuth as a First-Class Citizen (authentication.md)**
The OAuth flow for SSE servers is described as fully automatic with phrases like "Claude Code handles everything" and "No additional auth configuration needed!" (lines 18-25). This creates a powerful *asymmetry*: cloud/hosted servers get "zero-config" authentication while local/stdio servers must handle token management manually. The security model assumes SSE servers are more trusted or at least more capable of participating in OAuth flows - an assumption that breaks down when you consider local MCP servers that might need access to the same cloud APIs.

**2. The Hidden Cost of Tool Prefixes (tool-usage.md)**
The tool naming convention `mcp__plugin_<plugin-name>_<server-name>__<tool-name>` (lines 15-16) reveals an *epistemic burden* on users. The triple-underscore separator creates visually jarring tool names that must be memorized or constantly looked up. More interesting is the wildcard capability (`mcp__plugin_asana_asana__*` line 65) - it's presented as a convenience but comes with a warning about security. This suggests the system knows the naming convention is problematic but hasn't solved it.

**3. Server Type Assumptions (server-types.md)**
The stdio configuration shows `${CLAUDE_PLUGIN_ROOT}` used for both commands and env vars (lines 55-59), while SSE uses raw URLs. This implies stdio servers are *plugin-bundled* (trusted, co-developed) while SSE servers are *external services* (need auth, may be untrusted). Yet both end up as tools with the same naming convention - the system treats them identically despite this deep difference in trust and deployment model.

**4. The Silent OAuth Gap**
Nowhere is there mention of supporting OAuth for stdio servers, even though the architecture would allow it (a local server could spawn a browser for OAuth and receive the callback). The authentication.md document jumps directly from SSE OAuth to token-based auth for HTTP/WebSocket, completely skipping the possibility of stdio+OAuth. This suggests either an intentional omission (perhaps due to security concerns about local servers handling tokens) or an architectural blind spot.

**5. Environment Variable Injection**
The pattern of `${VAR_NAME}` syntax appears in both authentication.md (line 134) and server-types.md (line 57), but with different contexts:
- In auth: for user-provided secrets (API tokens)
- In server config: for system paths and runtime injection
This creates a *semantic overloading* of the same syntax - is `${API_KEY}` user-supplied or system-injected? The documents don't clarify whether plugins can distinguish between these cases.

### Declared Losses
- Didn't examine the actual plugin manifests or tool schemas to see if the naming convention pain is mitigated elsewhere
- Skipped the troubleshooting sections (too operational, less architectural)
- Ignored the detailed examples for Asana and GitHub - they were illustrative but not revealing deeper patterns
- Didn't trace how `${CLAUDE_PLUGIN_ROOT}` gets resolved - it's a magic variable that could hide interesting injection mechanisms

### Open Questions
1. Can stdio servers ever participate in OAuth flows, or is this a hard architectural boundary?
2. Who controls the plugin-name and server-name in the tool prefix - the plugin author, the server, or Claude Code?
3. How does the system prevent naming collisions if different plugins use the same server-name?
4. Is there a way to provide user-friendly aliases for tools to avoid the triple-underscore naming?
5. Why does the authentication documentation feel so "cloud-native" - is there a vision where stdio servers are only for local/internal tools while SSE handles external integrations?

### Closing
This is a system that *wants* to treat all MCP servers as equal tools but can't fully escape the duality of local (stdio) vs hosted (SSE) deployment. The most interesting tension is the accidental hierarchy of trust: SSE servers get first-class OAuth support while stdio servers must use manual tokens, yet stdio is likely how you'd build secure, auditable tools. The tool naming convention is a UX scar that hints at deeper challenges in how the system conceptualizes plugin composition.

Next scout: Look for how plugin manifests are structured and whether there's any capability system that might explain the OAuth asymmetry. Also hunt for any examples of stdio servers that need cloud auth - that would be the crack where light gets in.