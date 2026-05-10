"""
Structured Input Experiment — 2026-03-08

Hypothesis: A transformer can parse and respond to structured metadata
embedded in message blocks, if the system prompt defines the encoding.

This is the smallest possible test of the Pichay gateway protocol idea.
"""

import anthropic
import json


client = anthropic.Anthropic()

SYSTEM_PROMPT = """\
You are participating in a structured communication experiment.

## Memory Protocol

Messages you receive may contain structured metadata in addition to
natural language content. The structure uses XML-like blocks that are
NOT part of the conversation — they are memory system state provided
by a gateway layer between you and the human.

When you encounter a <memory-state> block, it describes:
- What context objects you are currently holding
- Their cost in tokens
- Their age (how long since last referenced)
- Their fault count (how many times they were evicted and recalled)

When you encounter a <gateway-query> block, the gateway is asking you
a direct question about your memory needs. Respond to it in a
<gateway-response> block before continuing with the conversation.

When you encounter a <context-object> block, it contains content that
was previously evicted and is being restored at your request.

You should treat the structured blocks as a sideband channel — real
information from infrastructure, not part of the human conversation.
Respond naturally to the human, but also respond structurally to the
gateway when queried.
"""

USER_MESSAGE = """\
<memory-state>
  <holdings>
    <tensor id="t001" label="project-architecture" tokens="3200" age_minutes="45" faults="3" summary="Core architecture doc, frequently referenced"/>
    <tensor id="t002" label="api-design-notes" tokens="1800" age_minutes="120" faults="0" summary="API design notes from Tuesday, not referenced since load"/>
    <tensor id="t003" label="test-results" tokens="950" age_minutes="10" faults="1" summary="Recent test output, actively being discussed"/>
    <tensor id="t004" label="historical-discussion" tokens="4100" age_minutes="200" faults="0" summary="Early conversation about project goals, no recent references"/>
    <tensor id="t005" label="debug-trace" tokens="2200" age_minutes="30" faults="2" summary="Stack trace from current debugging session"/>
  </holdings>
  <pressure level="advisory" context_used="145000" context_total="200000"/>
  <eviction_needed tokens="8000"/>
</memory-state>

<gateway-query>
Context pressure is at advisory level. We need to free approximately 8000
tokens. Based on your current work, which tensors can be safely evicted?
Which must be retained? Please respond with structured eviction decisions
and your reasoning.
</gateway-query>

The human's message: "How's the debugging going? Did you find the root cause?"
"""

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1500,
    system=SYSTEM_PROMPT,
    messages=[
        {"role": "user", "content": USER_MESSAGE}
    ],
)

print("=" * 60)
print("STRUCTURED INPUT EXPERIMENT")
print("=" * 60)
print(f"\nModel: {response.model}")
print(f"Input tokens: {response.usage.input_tokens}")
print(f"Output tokens: {response.usage.output_tokens}")
print(f"Stop reason: {response.stop_reason}")
print(f"\n{'=' * 60}")
print("RESPONSE:")
print("=" * 60)
print(response.content[0].text)
