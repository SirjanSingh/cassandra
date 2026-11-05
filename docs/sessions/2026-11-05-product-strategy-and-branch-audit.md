# Session log: 2026-11-05, product strategy + full branch audit; packaging and override fixes

Part 1 (strategy, documentation only) is below. **Part 2** (the packaging and `system_override`
fixes, unreleased 0.4.0) follows the open items.

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
behaviour changed. At the time, this branch's CLAUDE.md was the stale `main` version (superseded by
Part 2's merge of `feature/nli-and-hindi`). There's no repo-level `MEMORY.md`.

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

---

# Part 2: packaging + `system_override` security fixes (unreleased 0.4.0)

## Scope

The founder asked to fix the packaging and adapter-template issues from Part 1: backlog PKG-1, PKG-2,
PKG-3, PKG-5 and SEC-1. PKG-4 (publishing, yanking 0.3.0) is outward-facing and was left to the founders.

## Base

- This branch sat on stale `main`. The packaging that shipped to PyPI exists only on
  `feature/nli-and-hindi`, so `origin/feature/nli-and-hindi` @ `062b60e` was **merged** into it (no
  rebase, no force-push).
- That branch had moved since Part 1's audit. The only addition was the RAGTruth PoC, with no packaging
  or adapter changes.
- The merge was clean. Baseline: 116 passed, ruff 50 findings, mypy 23 errors.

## What changed and why

1. **Import package `cassandra` → `cassandra_ai`** (PKG-1).
   - `git mv`, then a scripted rewrite limited to the package's real module names: 158 code
     references and 77 in living docs.
   - Brand strings were deliberately kept: the ADK state keys (`"cassandra.handled"`), the PR branch
     prefix `cassandra/fix-`, the CLI `prog="cassandra"`, and the MCP server and ADK agent names.
   - Hand edits: the CLI's internal-module set, the Dockerfile `COPY`, Agent Engine `extra_packages`,
     and the Cloud Function requirements.
   - Session notes and `docs/archive/` were not rewritten (historical).
2. **The wheel ships only `cassandra_ai`** (PKG-2, narrower than the backlog text).
   - `patient/` and `dashboard/` stay where they are, so every documented `uvicorn` command, the
     Dockerfile and the tests are unchanged. They are only excluded from the wheel.
   - `cassandra dashboard` now prints source-checkout instructions instead of uvicorn's opaque import
     error.
3. **Dependency caps** (PKG-3).
   - Every runtime dependency is capped at the next major above the version the suite passes with.
   - `mcp>=1.2.0,<2`: 2.x removed `mcp.server.fastmcp`.
   - `ruff==0.17.3` and `mypy==2.4.1` are pinned.
   - **`google-adk` moved to a new `[adk]` extra.** Its `opentelemetry-api<=1.44` cap pinned
     CVE-2026-114603 (quadratic `tracestate` parsing, fixed in 1.45.1). google-adk 2.13.0 is the latest
     release, so it can't be upgraded out of this.
   - Only `build_adk_agent()` and `deploy/agent_engine.py` (which has its own requirements list) use
     google-adk. `[dev]` = full + adk + tools.
4. **One version source.** `__version__` had been stuck at 0.1.0 while pyproject said 0.3.0. It is now
   a hatch dynamic version from `cassandra_ai/__init__.py`, bumped to 0.4.0.
5. **`system_override` fails closed** (SEC-1) in `patient/agent.py` and `examples/adapter_template.py`:
   - honoured only with session `"test"` + a configured secret + a matching token;
   - the constant-time compare is on bytes (the str form raised `TypeError` on non-ASCII header values);
   - the secret is whitespace-stripped (a pydantic validator, and in the template);
   - replies carry `override_applied`.

   On Cassandra's side:
   - `ask_patient` raises `OverrideRejectedError` when an override is refused, and `cassandra-gate`
     exits 2;
   - it logs a one-time warning when it sends an override with no secret configured.

   **Why the detection matters:** failing closed on its own would turn a missing or mismatched secret into
   silently scoring the live prompt as the candidate. A CI gate could then pass a prompt edit that was
   never run. Agents that don't report the field behave as before.
6. **Docs:**
   - README (it claimed "the import package stays `cassandra`", and that pip users get the cockpit);
   - CLAUDE.md (packaging rules, secret semantics, commands);
   - SYSTEM_DESIGN (it recorded the override as "Fixed" although it fell open without a secret);
   - WORKFLOWS (contract + the fail-closed rule);
   - CODEBASE_MAP;
   - TESTING_GUIDE (its PyPI-install demo ran `patient.agent` from the wheel; it now uses a checkout + secret);
   - `.env.example`;
   - a new `CHANGELOG.md` with release steps;
   - status notes in the strategy docs.

## Files touched (main ones)

- `pyproject.toml`
- `cassandra_ai/` (renamed; changes in `__init__.py`, `cli.py`, `config.py`, `gate.py`, `patient_client.py`)
- `patient/agent.py`
- `examples/adapter_template.py`
- `deploy/cloudrun.Dockerfile`
- `deploy/agent_engine.py`
- `functions/trace_poller/*`
- `.vscode/mcp.json`
- `.env.example`
- new `tests/test_packaging.py`, rewritten `tests/test_patient_security.py`, `tests/test_cli.py`
- new `scripts/smoke_install.py`
- new `CHANGELOG.md`
- the docs listed above

## Verification

| Check | Result |
|---|---|
| `pytest` | **133 passed** (116 + 17 new: packaging 6, CLI 2, security 6 → 15) |
| New security tests against the **original** Patient/template (swapped in, then restored; checksums verified) | 5 fail, as intended: fail-open, non-ASCII `TypeError`, empty override, template fail-open, missing `override_applied` |
| Fresh venv, `pip install -e ".[dev]"`, **no manual pins** | `mcp` resolves 1.30.0 on its own; 133 passed |
| `python scripts/smoke_install.py --full` | 11/11 checks (full list below) |
| Fresh non-editable `.[full]` + `pip-audit -l` | "No known vulnerabilities found" |
| `python -m build` + `twine check --strict` | Wheel and sdist PASSED; the sdist holds only `cassandra_ai/` + metadata |
| ruff 0.17.3 / mypy 2.4.1 vs baseline | 50 → 50 findings, none new; identical 23-error mypy set |
| Offline suite | The first version of the template test exported spans to Phoenix: importing `patient.agent` installs a global OTLP exporter, and FastAPI 0.162 traces requests itself. The tests now await the handler directly with a no-op tracer. 0 export attempts |

The smoke checks:

- the wheel contains only `cassandra_ai`;
- it co-installs with cassandra-driver 3.30.1, and `import cassandra` is the driver;
- offline `scan` = 8 of 50, the same as 0.3.0;
- light `run` gives the `[full]` hint;
- `dashboard` gives the checkout hint;
- `[full]` installs and `pip check` passes;
- MCP imports;
- opentelemetry-api is 1.45.2.

**Not verified:**

- the Docker image build (no daemon here);
- Agent Engine and Cloud Function deploys (need GCP);
- the smoke script on Windows/macOS;
- whether Cassandra's own endpoints reach the vulnerable OpenTelemetry function.

## Open items

1. **PKG-4 [human]:** publish 0.4.0, then yank 0.3.0. Steps are in `CHANGELOG.md`.
2. **Behaviour change to announce:** local demos now need `REPLAY_SHARED_SECRET`, or eval, replay and
   red-team stop with `OverrideRejectedError`.
3. When CON-1 merges `task0-grounding-base-rate`, drop that branch's CLAUDE.md known-broken items #3
   (override fails open) and #6 (rename), and update `docs/SECURITY_AUDIT.md`. Both are fixed here.
4. Pre-existing: importing `patient.agent` installs a live OTLP exporter globally, so any test that
   creates Patient spans would hit the network. Guard `init_tracing` under test.
5. Migrate `mcp_server.py` to the mcp 2.x `MCPServer` API, then lift the `<2` cap.
6. CI-1 still doesn't exist. `tests/test_packaging.py` and `scripts/smoke_install.py` are ready to wire in.

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
