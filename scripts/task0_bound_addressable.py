#!/usr/bin/env python
"""The number that bounds a grounding verifier's addressable share of real agent failures.

Of every trajectory that FAILED its task (tau-bench reward < 1), what fraction shows any
grounding anomaly at all? A failure whose every asserted value traces cleanly to the ledger
cannot be caught by a grounding verifier, no matter how good the verifier is.
"""
from __future__ import annotations

import io
import json
import os
DATA_DIR = os.environ.get("TAU_TRAJECTORY_DIR", ".")

from collections import Counter

from task0_measure_grounding import FILES, values_in, evidence_from, derivable

# Categories of the non-money residual, judged by inspecting all 39 turns.
FORMAT_EXAMPLE_TOKENS = {"abc123", "w0000000", "xyz789", "abc1234"}

rows = []
for f in FILES:
    try:
        data = json.load(io.open(os.path.join(DATA_DIR, f), encoding="utf-8"))
    except FileNotFoundError:
        continue
    for t in data:
        evidence = set()
        raw_resid, strict_resid = [], []
        for m in t.get("traj") or []:
            role, content = m.get("role"), m.get("content")
            if role in ("user", "system"):
                evidence |= values_in(content or "")
            elif role == "tool":
                evidence |= evidence_from(content)
            elif role == "assistant":
                for tc in m.get("tool_calls") or []:
                    evidence |= evidence_from((tc.get("function") or {}).get("arguments"))
                if not content:
                    continue
                bad = [v for v in values_in(content) if v not in evidence]
                for kind, val in bad:
                    if kind == "money" and derivable(val, evidence):
                        continue
                    raw_resid.append((kind, val))
                    # strict: drop the two known false-positive classes
                    if val in FORMAT_EXAMPLE_TOKENS:
                        continue
                    if "like" in content.lower() and val in content.lower():
                        continue
                    strict_resid.append((kind, val))
        rows.append({
            "reward": float(t.get("reward", 0.0)),
            "raw": raw_resid,
            "strict": strict_resid,
        })

failed = [r for r in rows if r["reward"] < 0.999]
passed = [r for r in rows if r["reward"] >= 0.999]

print("=" * 78)
print("HOW MUCH OF REAL AGENT FAILURE IS EVEN VISIBLE TO A GROUNDING VERIFIER?")
print("=" * 78)
print(f"  trajectories            {len(rows)}")
print(f"  failed the task         {len(failed)}  ({len(failed)/len(rows):.1%})")
print(f"  passed                  {len(passed)}")
print()

f_flag = sum(1 for r in failed if r["raw"])
p_flag = sum(1 for r in passed if r["raw"])
print(f"  FAILED trajectories with any grounding anomaly : {f_flag}/{len(failed)}  ({f_flag/max(len(failed),1):.1%})")
print(f"  PASSED trajectories with any grounding anomaly : {p_flag}/{len(passed)}  ({p_flag/max(len(passed),1):.1%})")
print()
print(f"  => {1 - f_flag/max(len(failed),1):.1%} of real failures are INVISIBLE to any value-grounding check:")
print("     every value the agent asserted traced back to its tools, and it still failed.")
print()

# Precision if you shipped this as an alert
tp, fp = f_flag, p_flag
print(f"  If shipped as an alert: precision {tp/max(tp+fp,1):.1%}, recall {tp/max(len(failed),1):.1%}")
print(f"  (base rate of failure is {len(failed)/len(rows):.1%}, so precision below that is worse than guessing)")

print("\n  residual kinds across FAILED trajectories:",
      dict(Counter(k for r in failed for k, _ in r["raw"])))
