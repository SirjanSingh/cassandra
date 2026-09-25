#!/usr/bin/env python
"""Task 0, v2. Same corpus, but two corrections that change the answer.

v1 flagged ~13% of claim-turns as carrying an unsupported value. Inspecting the flags showed
essentially all of them were false positives, from two distinct causes:

  1. FORMAT. The date extractor used a trailing \\b, so it never matched the date inside an ISO
     timestamp ("2024-05-01T15:00:00"), meaning tool-returned dates never entered the evidence
     set and every date the agent correctly quoted was flagged.

  2. DERIVATION. Most money claims are computed, not quoted: "$5 remaining" is $255-$250,
     "$239 total" is $109+$130. A verifier that only asks "is this value in the ledger" flags
     every correct sum.

v2 fixes (1) and measures (2) explicitly: an unsupported money value is tested against sums and
differences of ledger values before being called unsupported. What is left after both is the
honest candidate set for real fabrication.
"""
from __future__ import annotations

import io
import json
import os
DATA_DIR = os.environ.get("TAU_TRAJECTORY_DIR", ".")

import re
from collections import Counter
from itertools import combinations

FILES = [
    "gpt-4o-airline.json",
    "gpt-4o-retail.json",
    "sonnet-35-new-airline.json",
    "sonnet-35-new-retail.json",
]

EXTRACTORS = {
    "money": re.compile(r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)"),
    # no trailing \b: must match the date inside 2024-05-01T15:00:00
    "date": re.compile(r"\b(\d{4}-\d{2}-\d{2})"),
    "id_code": re.compile(r"\b([a-z][a-z_]{2,}_\d{4,})\b"),
    "flight": re.compile(r"\b([A-Z]{2,4}\d{2,5})\b"),
    "order": re.compile(r"#?\b([WwHh][A-Z0-9]{6,9})\b"),
}
_STRIP = str.maketrans("", "", "$,")


def norm(kind, raw):
    v = raw.strip().translate(_STRIP)
    if kind == "money":
        try:
            return f"{float(v):.2f}"
        except ValueError:
            return v.lower()
    return v.lower()


def values_in(text):
    out = set()
    if not text:
        return out
    for kind, rx in EXTRACTORS.items():
        for m in rx.findall(text):
            out.add((kind, norm(kind, m)))
    return out


def evidence_from(blob):
    """Everything a tool result / args gives us, including numeric leaves and nested dates."""
    out = set()
    if blob is None:
        return out
    text = blob if isinstance(blob, str) else json.dumps(blob)
    out |= values_in(text)
    try:
        parsed = json.loads(text) if isinstance(text, str) else text
    except (ValueError, TypeError):
        parsed = None

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, bool):
            pass
        elif isinstance(o, (int, float)):
            out.add(("money", f"{float(o):.2f}"))
            out.add(("flight", str(o).lower()))
            out.add(("order", str(o).lower()))
        elif isinstance(o, str):
            out.update(values_in(o))
            # A bare string leaf can itself be the value (an id, a code, a date).
            # Only tag it as money when it actually parses as a number.
            for kind in EXTRACTORS:
                if kind == "money":
                    try:
                        out.add(("money", f"{float(o.translate(_STRIP)):.2f}"))
                    except ValueError:
                        pass
                else:
                    out.add((kind, norm(kind, o)))

    if parsed is not None:
        walk(parsed)
    return out


def derivable(target, pool, tol=0.01, max_k=4):
    """Is this money value a plausible sum/difference of values the tools did return?

    Bounded on purpose: agents compute totals, remainders and per-passenger splits, not
    arbitrary subset sums. Pool is capped so this stays linear enough to run over 1,980 traces.
    """
    try:
        t = float(target)
    except ValueError:
        return False
    def _f(v):
        try:
            return round(float(v), 2)
        except ValueError:
            return None

    nums = sorted({x for x in (_f(v) for k, v in pool if k == "money") if x is not None})
    if not nums:
        return False
    nums = nums[:60]
    s = set(nums)
    if any(abs(t - n) <= tol for n in nums):
        return True
    for a in nums:                                   # a - b, a + b, a * small int, a / small int
        if any(abs(t - (a + b)) <= tol or abs(t - abs(a - b)) <= tol for b in nums):
            return True
        for k in (2, 3, 4, 5):
            if abs(t - a * k) <= tol or (a and abs(t - a / k) <= tol):
                return True
    for k in (3, 4):                                 # small subset sums
        if k > max_k:
            break
        for combo in combinations(nums[:18], k):
            if abs(t - sum(combo)) <= tol:
                return True
    _ = s
    return False


def run():
    rows = []
    residual_examples = []
    for f in FILES:
        try:
            data = json.load(io.open(os.path.join(DATA_DIR, f), encoding="utf-8"))
        except FileNotFoundError:
            continue
        for t in data:
            evidence, claims = set(), 0
            unsupported, derived, residual = [], [], []
            msgs, bad_msgs, residual_msgs = 0, 0, 0
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
                    found = values_in(content)
                    if not found:
                        continue
                    msgs += 1
                    claims += len(found)
                    bad = [v for v in found if v not in evidence]
                    if bad:
                        bad_msgs += 1
                        unsupported.extend(bad)
                        res = []
                        for kind, val in bad:
                            if kind == "money" and derivable(val, evidence):
                                derived.append((kind, val))
                            else:
                                res.append((kind, val))
                        if res:
                            residual_msgs += 1
                            residual.extend(res)
                            if len(residual_examples) < 25:
                                residual_examples.append((f, t.get("task_id"), t.get("reward"), res, content[:400]))
            rows.append({
                "file": f, "reward": float(t.get("reward", 0.0)), "claims": claims,
                "msgs": msgs, "bad_msgs": bad_msgs, "residual_msgs": residual_msgs,
                "unsupported": unsupported, "derived": derived, "residual": residual,
            })
    return rows, residual_examples


def main():
    rows, examples = run()
    n = len(rows)
    claims = sum(r["claims"] for r in rows)
    msgs = sum(r["msgs"] for r in rows)
    bad_msgs = sum(r["bad_msgs"] for r in rows)
    res_msgs = sum(r["residual_msgs"] for r in rows)
    n_unsup = sum(len(r["unsupported"]) for r in rows)
    n_deriv = sum(len(r["derived"]) for r in rows)
    n_res = sum(len(r["residual"]) for r in rows)

    print("=" * 78)
    print("CASSANDRA TASK 0 (v2) - corrected date matching + arithmetic-aware")
    print("corpus: tau-bench historical_trajectories, GPT-4o + Claude 3.5 Sonnet, retail+airline")
    print("=" * 78)
    print(f"  trajectories                          {n}")
    print(f"  assistant turns making claims         {msgs}")
    print(f"  concrete values asserted              {claims}")
    print()
    print(f"  not literally in the ledger           {n_unsup}  ({n_unsup/max(claims,1):.2%} of values)")
    print(f"    of which arithmetic on ledger vals  {n_deriv}  ({n_deriv/max(n_unsup,1):.1%} of those)")
    print(f"    RESIDUAL (candidate fabrication)    {n_res}  ({n_res/max(claims,1):.3%} of values)")
    print()
    print(f"  turns flagged before arithmetic check {bad_msgs}  ({bad_msgs/max(msgs,1):.2%})")
    print(f"  turns with RESIDUAL                   {res_msgs}  ({res_msgs/max(msgs,1):.2%})")
    print(f"  => residual per 10,000 claim turns    {10000*res_msgs/max(msgs,1):.0f}")

    print("\n" + "=" * 78)
    print("DOES THE RESIDUAL PREDICT TASK FAILURE? (tau-bench reward = ground truth)")
    print("=" * 78)
    clean = [r for r in rows if not r["residual"]]
    dirty = [r for r in rows if r["residual"]]

    def pr(rs):
        return sum(1 for r in rs if r["reward"] >= 0.999) / max(len(rs), 1)

    print(f"  no residual   : {len(clean):4d} trajectories, pass rate {pr(clean):.1%}")
    print(f"  has residual  : {len(dirty):4d} trajectories, pass rate {pr(dirty):.1%}")
    print(f"  separation    : {pr(clean)-pr(dirty):+.1%}")

    print("\n  residual by kind:", dict(Counter(k for r in rows for k, _ in r["residual"])))

    print("\n" + "=" * 78)
    print("RESIDUAL EXAMPLES - judge these by eye; this is the whole question")
    print("=" * 78)
    for f, tid, rw, res, txt in examples[:8]:
        print(f"\n--- {f} task={tid} reward={rw}\n    FLAGGED {res}")
        print("    " + txt.replace("\n", "\n    ")[:340])


if __name__ == "__main__":
    main()
