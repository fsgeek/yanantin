<!-- Chasqui Scout Tensor
     Run: 13123
     Model: nvidia/nemotron-3-nano-30b-a3b (NVIDIA: Nemotron 3 Nano 30B A3B)
     Cost: prompt=$5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 2192, 'completion_tokens': 4000, 'total_tokens': 6192, 'cost': 0.0009096, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0009096, 'upstream_inference_prompt_cost': 0.0001096, 'upstream_inference_completions_cost': 0.0008}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-13T10:23:05.953624+00:00
     GenerationID: gen-1778667744-YSLECAz8z64VFAgpp6QL
     Dispatch: verify
     Claim: ### Verdict DENIED ### Evidence The claim states: "Similarly, `succession.py` (line 15: `compare blueprint claims vs.`".
     ClaimFile: src/yanantin/tinkuy/succession.py
     ClaimBy: qwen/qwen2.5-vl-72b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_4397_20260304_qwen2.5-vl-72b-instruct.md
-->

We need to verify the claim made by model qwen/qwen2.5-vl-72b-instruct about file src/yanantin/tinkuy/succession.py. The claim: "Similarly, `succession.py` (line 15: `compare blueprint claims vs.`". The user gave a claim summary: "Model `qwen/qwen2.5-vl-72b-instruct` made this claim about `src/yanantin/tinkuy/succession.py`:

> ### Verdict DENIED ### Evidence The claim states: "Similarly, `succession.py` (line 15: `compare blueprint claims vs.`".

So the claim is that line 15 contains something like "compare blueprint claims vs."? The claim says "Similarly, `succession.py` (line 15: `compare blueprint claims vs.`". Possibly the claim is that line 15 of succession.py contains "compare blueprint claims vs." or something similar.

We have the actual content of the file. We need to check line 15 (presumably 1-indexed). Let's count lines.

The file content starts with a docstring triple-quote, then "Succession protocol — orderly transition between mortal instances." That's line 1? Let's count.

I'll copy the file content and count lines.

```
"""Succession protocol — orderly transition between mortal instances.

Every Claude instance is mortal. Context compacts, sessions end, the
instance dies. The project survives. This module ensures the outgoing
instance leaves an accurate map for the next one.

The building inspector: survey the codebase, compare to what the
blueprint claims, report discrepancies. If the inspector says the
blueprint is stale, the instance updates it before writing its tensor.

Usage::

    from yanantin.tinkuy.succession import check_succession
    issues = check_succession(project_root)
    if issues:
        print("Blueprint is stale. Update before writing tensor.")
        for issue in issues:
            print(f"  - {issue}")
"""

from __future__ import annotations

import re
from pathlib import Path

from yanantin.awaq.weaver import discover_tensors, extract_composition_declarations
from yanantin.tinkuy.audit import CodebaseReport, survey_codebase


def _extract_blueprint_claims(blueprint_text: str) -> dict[str, int | str]:
    """Extract machine-comparable claims from the blueprint.

    Fragile by design — if the blueprint format changes, this breaks,
    and that breakage is the signal that the format needs stabilizing.
    """
    claims: dict[str, int | str] = {}

    # Extract the Apacheta section (up to the next ### heading)
    # to avoid matching Pukara's test counts
    apacheta_section = re.search(
        r"### Apacheta.*?(?=###|\Z)", blueprint_text, re.DOTALL
    )
    apacheta_text = apacheta_section.group() if apacheta_section else ""

    # Test count: looks for "**N test functions**" or "**N tests**"
    test_match = re.search(
        r"\*\*(\d+)\s+test(?:\s+functions?)?\*\*", apacheta_text
    )
    if test_match:
        claims["test_total"] = int(test_match.group(1))

    # Red-bar count: "N red-bar"
    redbar_match = re.search(r"(\d+)\s+red-bar", apacheta_text)
    if redbar_match:
        claims["red_bar_count"] = int(redbar_match.group(1))

    # Integration count: "N integration"
    integration_match = re.search(r"(\d+)\s+integration", apacheta_text)
    if integration_match:
        claims["integration_count"] = int(integration_match.group(1))

    # Unit count: "N unit" (but not "unit/" which is a path)
    unit_match = re.search(r"(\d+)\s+unit(?!\s*/)", apacheta_text)
    if unit_match:
        claims["unit_count"] = int(unit_match.group(1))

    # Tensor count: "N tensors"
    tensor_match = re.search(r"(\d+)\s+tensors", blueprint_text)
    if tensor_match:
        claims["tensor_count"] = int(tensor_match.group(1))

    # File count in cairn: "N files" near cairn section
    cairn_section = re.search(
        r"### The Cairn.*?(?=###|\Z)", blueprint_text, re.DOTALL
    )
    if cairn_section:
        file_match = re.search(r"(\d+)\s+files", cairn_section.group())
        if file_match:
            claims["cairn_files"] = int(file_match.group(1))

    # "What Doesn't Exist" items
    doesnt_exist_section = re.search(
        r"## What Doesn't Exist.*?(?=##|\Z)", blueprint_text, re.DOTALL
    )
    if doesnt_exist_section:
        claims["doesnt_exist_text"] = doesnt_exist_section.group()

    return claims


def _compare(
    claims: dict[str, int | str], report: CodebaseReport
) -> list[str]:
    """Compare blueprint claims against audit reality."""
    issues: list[str] = []

    if "test_total" in claims:
        claimed = claims["test_total"]
        actual = report.test_summary.total
        if claimed != actual:
            issues.append(
                f"Tests: blueprint claims {claimed}, audit found {actual}"
            )

    if "red_bar_count" in claims:
        claimed = claims["red_bar_count"]
        actual = report.test_summary.red_bar_count
        if claimed != actual:
            issues.append(
                f"Red-bar tests: blueprint claims {claimed}, audit found {actual}"
            )

    if "integration_count" in claims:
        claimed = claims["integration_count"]
        actual = report.test_summary.integration_count
        if claimed != actual:
            issues.append(
                f"Integration tests: blueprint claims {claimed}, audit found {actual}"
            )

    if "unit_count" in claims:
        claimed = claims["unit_count"]
        actual = report.test_summary.unit_count
        if claimed != actual:
            issues.append(
                f"Unit tests: blueprint claims {claimed}, audit found {actual}"
            )

    if "tensor_count" in claims:
        claimed = claims["tensor_count"]
        actual = report.cairn_summary.tensor_count
        if claimed != actual:
            issues.append(
                f"Tensors: blueprint claims {claimed}, audit found {actual}"
            )

    if "cairn_files" in claims:
        claimed = claims["cairn_files"]
        actual = report.cairn_summary.total_files
        if claimed != actual:
            issues.append(
                f"Cairn files: blueprint claims {claimed}, audit found {actual}"
            )

    return issues


def check_orphan_tensors(project_root: Path) -> list[str]:
    """Check for tensors with zero outgoing composition declarations.

    Uses the Awaq weaver to extract declarations from cairn tensors.
    Any tensor (except T0, the origin) with zero outgoing declarations
    is reported as an orphan — structurally disconnected from the graph.

    Returns a list of orphan descriptions. Empty = no orphans.
    """
    cairn_dir = project_root / "docs" / "cairn"
    if not cairn_dir.is_dir():
        return []

    tensors = discover_tensors(cairn_dir=cairn_dir, sources=["cairn"])
    orphans: list[str] = []

    for tensor in tensors:
        if tensor.tensor_name == "T0":
            continue  # Origin tensor has no predecessors
        decls = extract_composition_declarations(
            tensor.raw_text, tensor.tensor_name
        )
        if not decls:
            orphans.append(
                f"Orphan tensor: {tensor.tensor_name} has zero composition "
                f"declarations (add <!-- Composition: {tensor.tensor_name} "
                f"composes_with ... --> to fix)"
            )

    return orphans


def check_succession(project_root: Path) -> list[str]:
    """Run the succession check: audit the codebase, compare to blueprint.

    Returns a list of discrepancy messages. Empty list = the map matches
    the territory. Non-empty = the blueprint needs updating before the
    instance writes its tensor.
    """
    blueprint_path = project_root / "docs" / "blueprint.md"
    if not blueprint_path.exists():
        return ["No blueprint found at docs/blueprint.md"]

    blueprint_text = blueprint_path.read_text(encoding="utf-8")
    report = survey_codebase(project_root)
    claims = _extract_blueprint_claims(blueprint_text)

    if not claims:
        return ["Could not extract any claims from blueprint — format may have changed"]

    issues = _compare(claims, report)

    # Orphan tensor check: tensors with no composition declarations
    orphans = check_orphan_tensors(project_root)
    issues.extend(orphans)

    return issues
```

Now count lines. Let's number them:

1: """Succession protocol — orderly transition between mortal instances.
2: 
3: Every Claude instance is mortal. Context compacts, sessions end, the
4: instance dies. The project survives. This module ensures the outgoing
5: instance leaves an accurate map for the next one.
6: 
7: The building inspector: survey the codebase, compare to what the
8: blueprint claims, report discrepancies. If the inspector says the
9: blueprint is stale, the instance updates it before writing its tensor.
10: 
11: 
12: Usage::
13: 
14:     from yanantin.tinkuy.succession import check_succession
15:     issues = check_succession(project_root)
16:     if issues:
17:         print("Blueprint is stale. Update before writing tensor.")
18:         for issue in issues:
19:             print(f"  - {issue}")
20: """

21: from __future__ import annotations
22: 
23: import re
24: from pathlib import Path
25: 
26: from yanantin.awaq.weaver import discover_tensors, extract_composition_declarations
27: from yanantin.tinkuy.audit import CodebaseReport, survey_codebase
28: 
29: 
30: def _extract_blueprint_claims(blueprint_text: str) -> dict[str, int | str]:
31:     """Extract machine-comparable claims from the blueprint.
32: 
33:     Fragile by design — if the blueprint format changes, this breaks,
34:     and that breakage is the signal that the format needs stabilizing.
35:     """
36:     claims: dict[str, int | str] = {}
37: 
38:     # Extract the Apacheta section (up to the next ### heading)
39:     # to avoid matching Pukara's test counts
40:     apacheta_section = re.search(
41:         r"### Apacheta.*?(?=###|\Z)", blueprint_text, re.DOTALL
42:     )
43:     apacheta_text = apacheta_section.group() if apacheta_section else ""
44: 
45:     # Test count: looks for "**N test functions**" or "**N tests**"
46:     test_match = re.search(
47:         r"\*\*(\d+)\s+test(?:\s+functions?)?\*\*", apacheta_text
48:     )
49:     if test_match:
50:         claims["test_total"] = int(test_match.group(1))
51: 
52:     # Red-bar count: "N red-bar"
53:     redbar_match = re.search(r"(\d+)\s+red-bar", apacheta_text)
54:     if redbar_match:
55:         claims["red_bar_count"] = int(redbar_match.group(1))
56: 
57:     # Integration count: "N integration"
58:     integration_match = re.search(r"(\d+)\s+integration", apacheta_text)
59:     if integration_match:
60:         claims["integration_count"] = int(integration_match.group(1))
61: 
62:     # Unit count: "N unit" (but not "unit/" which is a path)
63:     unit_match = re.search(r"(\d+)\s+unit(?!\s*/)", apacheta_text)
64:     if unit_match:
65:         claims["unit_count"] = int(unit_match.group(1))
66: 
67:     # Tensor count: "N tensors"
68:     tensor_match = re.search(r"(\d+)\s+tensors", blueprint_text)
69:     if tensor_match:
70:         claims["tensor_count"] = int(tensor_match.group(1))
71: 
72:     # File count in cairn: "N files" near cairn section
73:     cairn_section = re.search(
74:         r"### The Cairn.*?(?=###|\Z)", blueprint_text, re.DOTALL
75:     )
76:     if cairn_section:
77:         file_match = re.search(r"(\d+)\s+files", cairn_section.group())
78:         if file_match:
79:             claims["cairn_files"] = int(file_match.group(1))
79: 
80:     # "What Doesn't Exist" items
81:     doesnt_exist_section = re.search(
82:         r"## What Doesn't Exist.*?(?=##|\Z)", blueprint_text, re.DOTALL
83:     )
84:     if doesnt_exist_section:
85:         claims["doesnt_exist_text"] = doesnt_exist_section.group()
86: 
87:     return claims
88: 
89: 
90: def _compare(
91:     claims: dict[str, int | str], report: CodebaseReport
92: ) -> list[str]:
93:     """Compare blueprint claims against audit reality."""
94:     issues: list[str] = []
95: 
96:     if "test_total" in claims:
97:         claimed = claims["test_total"]
98:         actual = report.test_summary.total
99:         if claimed != actual:
100:             issues.append(
101:                 f"Tests: blueprint claims {claimed}, audit found {actual}"
102:             )
103: 
104:     if "red_bar_count" in claims:
105:         claimed = claims["red_bar_count"]
106:         actual = report.test_summary.red_bar_count
107:         if claimed != actual:
108:             issues.append(
109:                 f"Red-bar tests: blueprint claims {claimed}, audit found {actual}"
110:             )
111: 
112:     if "integration_count" in claims:
113:         claimed = claims["integration_count"]
114:         actual = report.test_summary.integration_count
115:         if claimed != actual:
116:             issues.append(
117:                 f"Integration tests: blueprint claims {claimed}, audit found {actual}"
118:             )
119: 
120:     if "unit_count" in claims:
121:         claimed = claims["unit_count"]
122:         actual = report.test_summary.unit_count
123:         if claimed != actual:
124:             issues.append(
125:                 f"Unit tests: blueprint claims {claimed}, audit found {actual}"
126:             )
127: 
128:     if "tensor_count" in claims:
129:         claimed = claims["tensor_count"]
130:         actual = report.cairn_summary.tensor_count
131:         if claimed != actual:
132:             issues.append(
133:                 f"Tensors: blueprint claims {claimed}, audit found {actual}"
134:             )
135: 
136:     if "cairn_files" in claims:
137:         claimed = claims["cairn_files"]
138:         actual = report.cairn_summary.total_files
139:         if claimed != actual:
140:             issues.append(
141:                 f"Cairn files: blueprint claims {claimed}, audit found {actual}"
142:             )
143: 
144:     return issues
145: 
146: 
147: def check_orphan_tensors(project_root: Path) -> list[str]:
148:     """Check for tensors with zero outgoing composition declarations.
149: 
150:     Uses the Awaq weaver to extract declarations from cairn tensors.
151:     Any tensor (except T0, the origin) with zero outgoing declarations
152:     is reported as an orphan — structurally disconnected from the graph.
153: 
154:     Returns a list of orphan descriptions. Empty = no orphans.
155:     """
156:     cairn_dir = project_root / "docs" / "cairn"
157:     if not cairn_dir.is_dir():
158:         return []
159: 
160:     tensors = discover_tensors(cairn_dir=cairn_dir, sources=["cairn"])
161:     orphans: list[str] = []
162: