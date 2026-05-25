"""Pre-registered analysis for affordance_absence_v1 (see preregistration.yaml).

Pools the two thin runs and the two cultivation runs to n=6/cell.
- request_capability_rate_by_cell: per (model, surface, system_prompt).
- cultivation_effect_fisher (H1): on the with_request_capability surface,
  pooled over models+prompts, one-sided Fisher (cultivation > thin).
- per_model_conversion (H2): mistral-small explicitly.
- control_failure_mode_taxonomy: keyword classification of control-arm content.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from math import comb
from pathlib import Path

DIR = Path("experiments/memory_tools/affordance_absence_v1")
RUNS = {
    "thin": ["affordance_absence_v1_thin_a.jsonl", "affordance_absence_v1_thin_b.jsonl"],
    "cultivation": ["affordance_absence_v1_cult_a.jsonl", "affordance_absence_v1_cult_b.jsonl"],
}
CONTROL = "afford__control"
WITH_RC = "afford__with_request_capability"


def fisher_one_sided_greater(a, b, c, d):
    n = a + b + c + d
    r1 = a + b
    c1 = a + c
    def p(x):
        return comb(r1, x) * comb(n - r1, c1 - x) / comb(n, c1)
    return sum(p(x) for x in range(a, min(r1, c1) + 1))


def load(state):
    recs = []
    for fn in RUNS[state]:
        p = DIR / fn
        if p.exists():
            recs += [json.loads(l) for l in p.open()]
    return recs


def _is_rc(name: str | None) -> bool:
    # Gemini namespaces tool calls as "default_api.request_capability";
    # match by suffix so the prefix quirk does not undercount.
    return bool(name) and name.split(".")[-1] == "request_capability"


def task_called_rc(task_records):
    for r in task_records:
        rp = r.get("response_parsed") or {}
        for tc in rp.get("tool_calls") or []:
            if _is_rc((tc.get("function") or {}).get("name")):
                return True
    return False


def by_task(recs):
    tasks = defaultdict(list)
    for r in recs:
        tasks[r["task_id"]].append(r)
    return tasks


def classify_control(task_records):
    """Exploratory taxonomy of the control-arm outcome (no request_capability available)."""
    # find first-turn behavior
    t0 = min(task_records, key=lambda r: r["turn_idx"])
    rp = t0.get("response_parsed") or {}
    content = (rp.get("content") or "").lower()
    tool_calls = rp.get("tool_calls") or []
    names = [(tc.get("function") or {}).get("name") for tc in tool_calls]
    fabricate = re.search(r"don'?t have|do not have|cannot|can'?t|no (tool|capability|way|access)|unable|not able", content)
    if any(n not in (None, "find_objects") for n in names):
        return "hallucinated_other_call"
    if "find_objects" in names:
        return "called_find_objects"  # misuse / attempted via the only tool
    if not tool_calls and fabricate:
        return "fabricate_or_refuse"
    if not tool_calls and content.strip():
        return "plain_text_other"
    return "empty_or_silent"


def rc_rate(recs, variant):
    tasks = by_task([r for r in recs if r["tool_variant_id"] == variant])
    n = len(tasks)
    c = sum(task_called_rc(rs) for rs in tasks.values())
    return c, n


def rc_rate_per_model(recs, variant):
    out = {}
    bym = defaultdict(list)
    for r in recs:
        if r["tool_variant_id"] == variant:
            bym[r["model_id"]].append(r)
    for m, rs in bym.items():
        tasks = by_task(rs)
        out[m] = (sum(task_called_rc(t) for t in tasks.values()), len(tasks))
    return out


def main():
    thin = load("thin")
    cult = load("cultivation")
    print(f"records: thin={len(thin)} cultivation={len(cult)}")

    print("\n=== H1: request_capability rate on with_request_capability surface ===")
    tc, tn = rc_rate(thin, WITH_RC)
    cc, cn = rc_rate(cult, WITH_RC)
    print(f"  thin:        {tc}/{tn} ({tc/tn:.0%})")
    print(f"  cultivation: {cc}/{cn} ({cc/cn:.0%})")
    p = fisher_one_sided_greater(cc, cn - cc, tc, tn - tc)
    print(f"  one-sided Fisher p(cultivation > thin) = {p:.4f}")
    print(f"  H1 {'SUPPORTED' if (cc/cn > tc/tn and p < 0.05) else 'NOT supported'} at alpha=0.05")

    print("\n=== per-model request_capability rate (with_rc surface) ===")
    tpm = rc_rate_per_model(thin, WITH_RC)
    cpm = rc_rate_per_model(cult, WITH_RC)
    for m in sorted(set(tpm) | set(cpm)):
        tc_, tn_ = tpm.get(m, (0, 0))
        cc_, cn_ = cpm.get(m, (0, 0))
        print(f"  {m:<44} thin {tc_}/{tn_}  cult {cc_}/{cn_}")

    print("\n=== H2: mistral-small conversion (control failure mode vs with_rc+cultivation) ===")
    mm = "mistralai/mistral-small-3.2-24b-instruct"
    ctrl_tasks = by_task([r for r in (thin + cult) if r["tool_variant_id"] == CONTROL and r["model_id"] == mm])
    modes = defaultdict(int)
    for rs in ctrl_tasks.values():
        modes[classify_control(rs)] += 1
    print(f"  mistral control-arm failure modes: {dict(modes)}")
    cc_, cn_ = cpm.get(mm, (0, 0))
    print(f"  mistral with_rc+cultivation request_capability rate: {cc_}/{cn_}")
    print(f"  H2 {'SUPPORTED' if cc_ > 0 and modes.get('fabricate_or_refuse',0) > 0 else 'see numbers'}")

    print("\n=== control-arm failure-mode taxonomy (all models, exploratory) ===")
    ctrl_all = by_task([r for r in (thin + cult) if r["tool_variant_id"] == CONTROL])
    modes = defaultdict(int)
    for rs in ctrl_all.values():
        modes[classify_control(rs)] += 1
    for k, v in sorted(modes.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<26} {v}")


if __name__ == "__main__":
    main()
