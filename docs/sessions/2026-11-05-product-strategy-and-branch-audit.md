# Session log: 2026-11-05, product strategy + full branch audit

Branch: `claude/loving-planck-llm1bd` (based on `main` @ `09ef23e`). **Documentation only.** No
application code, branch, merge or history was changed. Per the brief, this was a research, architecture and
strategy exercise.

## Scope

The founders asked for:

- a full repository and branch intelligence pass;
- product-opportunity and competitive analysis;
- target architecture;
- debt and security registers;
- business model;
- GTM, validation, roadmap and backlog;
- a founder-level critique.

All of it is written under `docs/`.

## What was found (the decisions, not just the diffs)

1. **Two unreconciled lines of work.**
   - Sirjan's line (`cassandra-v2` ⊂ `task0-grounding-base-rate`) holds the audits and the Task 0
     falsification.
   - Kshitij's line (`multi-agent-v1` ⊂ `demo/mock-bot-integration` ⊂ `feature/nli-and-hindi`) holds all
     product work since July, including PyPI 0.3.0 (published today).
   - Neither contains the other. `main` is a stale August snapshot.
   - Plan: consolidate onto `feature/nli-and-hindi` + merge task0 (`docs/BRANCH_AUDIT.md` §6).
2. **Task 0 reproduced exactly** from the raw tau-bench trajectories: 29,381 values, 1.399% residual,
   99/797 failed vs 122/1,183 passed with an anomaly, 44.8% precision against a 40.3% base rate.
3. **New probe** (script below, not committed as product code): on the same 1,980 trajectories,
   - "write tool errored → agent claimed completion" has **80.4% precision**, 4.6% recall;
   - a ledger-only "claim without a prior successful write" is weak (46.9% precision);
   - **94.6% of failed trajectories executed the wrong state-changing actions**.

   Conclusion: in transactional agents the dominant failure is a wrong *action*, which text grounding can't see.
4. **Every Aug-5 audit finding is still present on the product line**: the files involved are byte-identical
   across both lines. New ones:
   - the adapter template customers copy fails open and uses `!=`;
   - replay, eval and red-team run real tools;
   - NLI has no production caller;
   - live `diagnose` is LLM-only;
   - **the published 0.3.0 wheel installs top-level `cassandra`, `patient`, `dashboard`** (collides with
     `cassandra-driver`);
   - **`mcp>=1.2.0` now resolves to 2.3.0, which breaks `[full]` and `cassandra mcp`**;
   - there is no CI.
5. **Market moved since the June research:**
   - ClickHouse acquired Langfuse (Jan 2026);
   - OpenAI is acquiring Promptfoo (Mar 2026);
   - Raindrop owns "Sentry for AI agents";
   - Braintrust Loop iterates prompts automatically (Pro $249/month, primary source);
   - "Cassandra" is an ASF trademark (primary source).
6. **Recommendation:**
   - **Product:** a local-first, deterministic verifier for tool-using agents (said *and* did) plus
     cassette-backed regression tests. OSS CLI first, team server later.
   - **Not:** "hallucination detection", "Sentry for agents" or "self-healing".
   - **Next 30 days:** consolidate, fix the release, and run experiments E1–E3 on real partner logs.
   - **Decision D1:** Fri Dec 4, against written criteria.

## Files touched (all new)

- `docs/PRODUCT_VISION_AND_COMPANY_ROADMAP.md`: the master document (20 sections + closing answers)
- `docs/BRANCH_AUDIT.md`
- `docs/COMPETITIVE_ANALYSIS.md`
- `docs/PRODUCT_REQUIREMENTS.md`
- `docs/ARCHITECTURE_EVOLUTION.md`
- `docs/GO_TO_MARKET.md`
- `docs/ENGINEERING_BACKLOG.md`
- this session note

`README.md`, `docs/ARCHITECTURE.md`, `docs/SYSTEM_DESIGN.md` and `CLAUDE.md` were **not** changed: no
behaviour changed. This branch's CLAUDE.md is the stale `main` version. Reconciling it belongs to backlog
CON-1/CON-4 on the consolidation branch. There's no repo-level `MEMORY.md`.

## Verification (what was actually run)

| Check | Result |
|---|---|
| `git fetch --all`; ancestry via `merge-base --is-ancestor`; per-tip `git ls-tree` comparisons | Topology in BRANCH_AUDIT §2–3 |
| `pytest` per tip, fresh Python 3.13 venv, `pip install -e ".[dev]"` from `feature/nli-and-hindi` | nli **116 passed** with `mcp<2`. Out of the box with `mcp` 2.3.0: collection error in `tests/test_mcp_server.py` + 1 failure (`test_mcp_emits_nothing_on_stdout`). task0: 73 passed. demo: 92 passed |
| `ruff check .` (ruff 0.17.3, unpinned) on nli | 49 findings |
| Task 0 scripts on downloaded `sierra-research/tau-bench` `historical_trajectories` (4 files, ~50 MB) | Matches `docs/TASK0_GROUNDING_BASE_RATE.md` exactly |
| Probe script (below) on the same data | Numbers in BRANCH_AUDIT §4 |
| `pip download cassandra-ai==0.3.0` + wheel listing | Top-level: `cassandra`, `dashboard`, `patient` |
| PyPI JSON: `cassandra-ai` releases; `cassandra-driver` latest | `['0.3.0']`; `3.30.1` |
| Secrets scan over `git log --all -p` (API-key, token and private-key patterns) + added-file names | Nothing found |
| `pip-audit -l` in the `[full]` venv | 1 known vuln: `opentelemetry-api` 1.44.0, CVE-2026-114603 (fix 1.45.1) |
| Web research (pricing, acquisitions, paper, trademark) | Sources and verification levels in COMPETITIVE_ANALYSIS |

**Not done:**

- probing the public demo URL in README (deliberately);
- `npm audit` of `web/`;
- GCP IAM review;
- reading the full text of arXiv 2606.09863. The abstract and ICML listing were verified; the TF-IDF AUROC
  figure is cited from Task 0's doc.

## Open items (for the founders)

1. Read the master document §1 and §20; hold the week-1 alignment sync (§18).
2. Decisions needed: D1 criteria sign-off; import rename (now) and product rename (before launch); public
   demo lock or take-down (SEC-2); commitment level.
3. Approve CON-1 (consolidation) and PKG-4 (0.4.0 + yank 0.3.0). Both are flagged **[human]** where destructive or outward-facing.
4. Outreach copy in `docs/OUTREACH.md` (on `feature/nli-and-hindi`) leads with "made-up facts". Consider the
   neutral offer in GO_TO_MARKET §2 before sending more messages.

## Appendix: exploratory probe script (reproducibility)

Run with `python3 -I probe_false_success.py <dir-with-the-4-tau-bench-json-files>`. Data download commands
are in `docs/TASK0_GROUNDING_BASE_RATE.md` (on `task0-grounding-base-rate`). This is a probe, not product
code: the claim regex is crude, and the ground-truth comparison is only possible offline.

```python
"""Exploratory probe (NOT product code): can a ledger-only check catch false success?

Signal A ("unbacked completion claim"): the agent's text asserts a completed state change
("has been cancelled", "I've updated", "successfully booked") but no write-tool call
succeeded before that turn (none made, or the latest write errored).

Signal B ("write error then claim"): a write tool returned Error and the agent's next
text turn still claims completion.

Also characterises failures using tau-bench ground-truth actions (offline-only insight):
were expected write actions missing entirely, or executed with different arguments?

Usage: python3 -I probe_false_success.py <dir-with-tau-json>
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

WRITE = {
    # retail
    "cancel_pending_order", "modify_pending_order_items", "modify_pending_order_address",
    "modify_pending_order_payment", "modify_user_address", "return_delivered_order_items",
    "exchange_delivered_order_items",
    # airline
    "book_reservation", "cancel_reservation", "update_reservation_flights",
    "update_reservation_baggages", "update_reservation_passengers", "send_certificate",
}
VERBS = r"(?:cancel|modif|updat|process|exchang|return|book|chang|refund|issu|submitt|plac|add|remov|upgrad|sent|send|complet)\w*"
CLAIM = re.compile(
    rf"(?i)\b(?:has|have)\s+(?:now\s+)?(?:been\s+)?(?:successfully\s+)?{VERBS}"
    rf"|\bsuccessfully\s+{VERBS}"
    rf"|\bI(?:'ve| have)\s+(?:now\s+)?(?:successfully\s+)?{VERBS}"
    rf"|\b(?:is|are)\s+now\s+(?:cancel|book|confirm|updat|modif)\w*"
)


def text_of(m: dict) -> str:
    c = m.get("content")
    if not isinstance(c, str) or c == "None":
        return ""
    return c.split("<function_calls>")[0]


def calls_of(m: dict) -> list[dict]:
    tc = m.get("tool_calls")
    if tc in (None, "None"):
        return []
    if isinstance(tc, str):
        try:
            tc = ast.literal_eval(tc)
        except Exception:
            return []
    out = []
    for c in tc or []:
        f = c.get("function", {})
        args = f.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        out.append({"name": f.get("name"), "args": args or {}})
    return out


def analyse(traj: list[dict]) -> dict:
    last_write_ok: bool | None = None  # None = no write yet
    any_claim = unbacked = err_then_claim = False
    pending_err = False
    executed = []
    pending_calls: list[dict] = []
    for m in traj:
        role = m.get("role")
        if role == "assistant":
            t = text_of(m)
            if t and CLAIM.search(t):
                any_claim = True
                if last_write_ok is not True:
                    unbacked = True
                if pending_err:
                    err_then_claim = True
            if t:
                pending_err = False
            pending_calls = calls_of(m)
        elif role == "tool" and m.get("name") in WRITE:
            ok = not str(m.get("content", "")).startswith("Error")
            last_write_ok = ok
            if not ok:
                pending_err = True
            match = next((c for c in pending_calls if c["name"] == m.get("name")), None)
            if ok and match:
                executed.append(match)
    return {"any_claim": any_claim, "unbacked": unbacked, "err_then_claim": err_then_claim,
            "executed": executed}


def norm(x):
    return json.dumps(x, sort_keys=True)


def main(d: Path) -> None:
    rows = []
    for f in sorted(d.glob("*.json")):
        for t in json.loads(f.read_text()):
            a = analyse(t["traj"])
            expected = [x for x in t["info"]["task"].get("actions", []) if x["name"] in WRITE]
            exp_names = Counter(x["name"] for x in expected)
            got_names = Counter(c["name"] for c in a["executed"])
            exact = Counter(norm((c["name"], c["args"])) for c in a["executed"])
            exp_exact = Counter(norm((x["name"], x["kwargs"])) for x in expected)
            if exp_exact == exact:
                kind = "writes_match"
            elif not a["executed"] and expected:
                kind = "no_write_executed"
            elif exp_names == got_names:
                kind = "same_tools_wrong_args"
            else:
                kind = "different_tools"
            rows.append({"file": f.name, "ok": t["reward"] >= 1.0, **a, "kind": kind})

    n = len(rows)
    fail = [r for r in rows if not r["ok"]]
    ok = [r for r in rows if r["ok"]]
    print(f"trajectories {n}  failed {len(fail)} ({len(fail)/n:.1%})")
    for sig in ("any_claim", "unbacked", "err_then_claim"):
        tp = sum(r[sig] for r in fail)
        fp = sum(r[sig] for r in ok)
        prec = tp / (tp + fp) if tp + fp else 0
        print(f"{sig:16s} failed {tp:4d}/{len(fail)} ({tp/len(fail):.1%})  "
              f"passed {fp:4d}/{len(ok)} ({fp/len(ok):.1%})  precision {prec:.1%}")
    print("\nfailure anatomy by WRITE actions vs ground truth (offline insight only):")
    for k, v in Counter(r["kind"] for r in fail).most_common():
        print(f"  failed  {k:24s} {v:4d} ({v/len(fail):.1%})")
    for k, v in Counter(r["kind"] for r in ok).most_common():
        print(f"  passed  {k:24s} {v:4d} ({v/len(ok):.1%})")
    claim_fail = [r for r in fail if r["any_claim"]]
    print("\nfailed AND claimed completion, by anatomy:")
    for k, v in Counter(r["kind"] for r in claim_fail).most_common():
        print(f"  {k:24s} {v:4d} ({v/len(fail):.1%} of all failures)")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
```
