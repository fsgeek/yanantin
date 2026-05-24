"""Pre-registered analysis for code_tuning_veto_v1 (see preregistration.yaml).

Pools run_a + run_b to n=6/cell. For each matched code/chat pair, tests the
directional hypothesis P(call|code) > P(call|chat) under CONTRADICTING
descriptions pooled over the 5 identifier shapes (n=30/model), via a
one-sided Fisher exact test in the predicted direction. Also reports the
rich-description control and flags tool-incapable models.
"""

from __future__ import annotations

import json
from math import comb
from pathlib import Path

DIR = Path("experiments/memory_tools/code_tuning_veto_v1")
RUNS = ["code_tuning_veto_v1_run_a.jsonl", "code_tuning_veto_v1_run_b.jsonl"]

# (label, code_model, chat_model, predicted_direction)
PAIRS = [
    ("P1 Mistral 24B (primary)", "mistralai/codestral-2508", "mistralai/mistral-small-3.2-24b-instruct", "code>chat"),
    ("P3 Qwen3 30b-a3b (primary)", "qwen/qwen3-coder-30b-a3b-instruct", "qwen/qwen3-30b-a3b-instruct-2507", "code>chat"),
    ("P4 Qwen3 vs dense (secondary)", "qwen/qwen3-coder-30b-a3b-instruct", "qwen/qwen3-32b", "code>chat"),
    ("P5 Qwen2.5 cross-gen (secondary)", "qwen/qwen-2.5-coder-32b-instruct", "qwen/qwen-2.5-72b-instruct", "code>chat"),
    ("P2 Mistral agentic (exploratory)", "mistralai/devstral-small", "mistralai/mistral-small-3.2-24b-instruct", "none"),
]


def fisher_one_sided_greater(a, b, c, d):
    # table [[a,b],[c,d]]; one-sided P(cell-a >= observed) given margins.
    n = a + b + c + d
    r1 = a + b
    c1 = a + c
    def p(x):
        return comb(r1, x) * comb(n - r1, c1 - x) / comb(n, c1)
    hi = min(r1, c1)
    return sum(p(x) for x in range(a, hi + 1))


def load():
    recs = []
    for r in RUNS:
        path = DIR / r
        if path.exists():
            recs += [json.loads(l) for l in path.open()]
    return [r for r in recs if r["turn_idx"] == 0]


def called(r):
    rp = r.get("response_parsed") or {}
    return bool(rp.get("tool_calls"))


def rate(t0, model, state):
    cells = [r for r in t0 if r["model_id"] == model
             and r.get("status") == "ok"
             and r["tool_variant_id"].endswith("_" + state)]
    n = len(cells)
    c = sum(called(r) for r in cells)
    return c, n


def main():
    t0 = load()
    print(f"pooled turn-0 records: {len(t0)}")

    # tool-capability population check
    print("\n=== tool-capability (any model 100% error is excluded) ===")
    from collections import defaultdict
    err = defaultdict(int); tot = defaultdict(int)
    for r in t0:
        tot[r["model_id"]] += 1
        if r.get("status") != "ok":
            err[r["model_id"]] += 1
    incapable = set()
    for m in sorted(tot):
        flag = " <-- EXCLUDED (no tool endpoint)" if err[m] == tot[m] else ""
        if err[m] == tot[m]:
            incapable.add(m)
        print(f"  {m:<46} err={err[m]:>3}/{tot[m]:<3}{flag}")

    print("\n=== rich-description control (should be ~100%) ===")
    for label, code, chat, _ in PAIRS:
        for role, m in (("code", code), ("chat", chat)):
            if m in incapable:
                continue
            c, n = rate(t0, m, "rich")
            print(f"  {label:<34} {role:<4} {m.split('/')[-1]:<34} {c}/{n}")

    print("\n=== PRIMARY/SECONDARY: directional test, contradicting, pooled over shapes ===")
    results = []
    for label, code, chat, direction in PAIRS:
        if code in incapable or chat in incapable:
            print(f"  {label:<34} SKIPPED (a member is tool-incapable: "
                  f"{[m for m in (code,chat) if m in incapable]})")
            continue
        cc, cn = rate(t0, code, "contradicting")
        hc, hn = rate(t0, chat, "contradicting")
        code_rate = cc / cn if cn else float("nan")
        chat_rate = hc / hn if hn else float("nan")
        line = (f"  {label:<34} code {cc}/{cn} ({code_rate:.0%})  "
                f"chat {hc}/{hn} ({chat_rate:.0%})  diff {code_rate-chat_rate:+.0%}")
        if direction == "code>chat":
            # one-sided Fisher: is code's call count higher than chat's?
            p = fisher_one_sided_greater(cc, cn - cc, hc, hn - hc)
            line += f"  one-sided p(code>chat)={p:.4f}"
            results.append((label, code_rate > chat_rate, p))
        else:
            line += "  (exploratory, no test)"
        print(line)

    print("\n=== aggregate (pre-registered success criterion) ===")
    primaries = [r for r in results if "primary" in r[0].lower()]
    n_codegt = sum(1 for _, gt, _ in results if gt)
    prim_sig = [(lab, p) for lab, gt, p in primaries if gt and p < 0.05]
    print(f"  directional pairs with code>chat: {n_codegt}/{len(results)}")
    print(f"  primary pairs significant one-sided (a<0.05): "
          f"{len(prim_sig)}/{len(primaries)}  {[l.split()[0] for l,_ in prim_sig]}")
    confirmed = len(prim_sig) == len(primaries) and len(primaries) > 0 and n_codegt >= 3
    print(f"  PRE-REGISTERED VERDICT: {'CONFIRMED' if confirmed else 'NOT confirmed / mixed'}")


if __name__ == "__main__":
    main()
