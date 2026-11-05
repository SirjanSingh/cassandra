# Product requirements: feature architecture (2026-11-05)

> Part of the strategy set. Master document: [PRODUCT_VISION_AND_COMPANY_ROADMAP.md](PRODUCT_VISION_AND_COMPANY_ROADMAP.md).
> Engineering tasks that implement these features: [ENGINEERING_BACKLOG.md](ENGINEERING_BACKLOG.md).
> The hackathon-era `docs/PRD.md` / `docs/REQUIREMENTS.md` (FR-*/NFR-*) describe the demo pipeline and are
> superseded for product purposes.

## 0. Product in one paragraph

Cassandra is a **local-first verifier for tool-using AI agents**. You point it at your agent's logs or traces.
It checks what the agent **said** and **did** against what its tools **returned** and what your **rules
allow**. Every verdict is deterministic and cites the exact tool call as evidence. Confirmed failures become
regression tests whose tool responses are **recorded and replayed**, so CI can gate prompt, model and tool
changes without flakiness or side effects. The OSS CLI does all of this on a laptop. The commercial server
does it continuously for a team, with review, history and audit export.

**Status legend:**

- ✅ exists and works
- ⚠️ exists but is broken or has known defects
- 🧪 prototype or demo only
- ❌ not built

## 1. Primary workflow (the thing developers should love)

```
pip install <pkg>            # 10 s, 7 deps, offline
<cli> init  logs.jsonl       # mines a draft contract from your own logs → contract.yaml (review it in 15 min)
<cli> scan  logs.jsonl       # one-page report: which turns failed which check, each with the receipt
<cli> keep  t-0042           # turn a confirmed failure into a regression case (+ recorded tool responses)
<cli> test                   # replay all cases against the current prompt/model, offline; non-zero exit on regression
# CI: the same `test` runs on every PR that touches the prompt, model or tool definitions
```

**North-star metric:** confirmed failures caught per agent per week that the team *acted on* (kept as a test
or fixed). It measures trust and usefulness together. Stars and installs don't.

## 2. Feature map

Each row gives: what it is · user problem · why it matters · how it works · dependencies · complexity
(S/M/L/XL) · priority (P0–P3) · success measure. **"Value"** marks features that create genuine value;
**"Optics"** marks features that mostly make the product look impressive.

### 2.1 Essential features

| ID | Feature | Status | Problem → why | How | Deps | Cx | Pri | Success measure | Value/Optics |
|---|---|---|---|---|---|---|---|---|---|
| F-01 | **Log ingestion: JSONL** | ✅ `scan.load_turns` | Teams can't install a platform to try us; they can export logs | `{id, question, answer, tool_calls:[{name,args,result}]}` + aliases | — | S | P0 | % of design partners who produce a valid file in < 30 min (target ≥ 80%) | Value |
| F-02 | **Log ingestion: OpenInference/OTel spans** (Phoenix, Arize, Langfuse export, OTLP JSON file) | ⚠️ live Phoenix MCP only (`phoenix_mcp.normalize_span`) | Most teams already trace; asking for a custom export is friction | Offline file importers that reuse `_extract_tool_calls`; group spans by trace → turns | OTel GenAI conventions (unstable) | M | P1 | Second-most-used ingest path among partners | Value |
| F-03 | **Contract schema v1** (successor of `GroundingSpec`) | ⚠️ regex-only `GroundingSpec` | One spec must express claims, field values, decline phrases, completion claims and action policies | Versioned YAML/JSON. `tools` (success predicate, fields), `claims` (extractor + typed value + source field), `actions` (write tools + preconditions), `declines`. Backwards-compatible loader for `GroundingSpec` | — | M | P0 | Every check in F-05..F-08 expressible; partner contracts < 80 lines | Value |
| F-04 | **Report (markdown + JSON)** | ✅ `scan.render_markdown` | The report is the product's first impression and the sales artefact | Add: per-check breakdown, precision caveat, evidence per turn, PII redaction option | F-03 | S | P0 | Partners forward the report internally (ask them) | Value |
| F-05 | **Check: unsupported claim, value-matched** | ⚠️ `grounding.py` checks non-null, not equality | A carrier of "UPS" grounded by a DHL result is a false OK; the core claim is untrue as built | Typed claim extraction → normalise (money, dates, units, case) → compare to the cited field; all matches, not the first; ignore values echoed from the user's message; decline check per claim | F-03 | L | P0 | ≥ 90% precision on the golden set (F-30); 0 known false-OK classes | Value |
| F-06 | **Check: swallowed tool error** | ❌ | Agent says "done" after a write tool errored. Task-0-probe precision **80.4%** | Ledger scan: write tool result matches the error predicate → next assistant text contains a completion claim | F-03 | S | P0 | ≥ 80% precision on partner logs | Value |
| F-07 | **Check: action policy** (preconditions on write calls) | ❌ | 94.6% of tau-bench failures were wrong state-changing actions; nothing we have sees them | Declarative predicates over a write call's args and earlier ledger results (e.g. `cancel_order` requires `order.status == "pending"` from a prior read). Deterministic evaluator; no LLM | F-03, F-13 | L | P1 (gated on E1) | Catches ≥ 1 real failure/week on a partner agent | Value |
| F-08 | **Check: claimed vs executed action** | ❌ | "I've cancelled order #W123" when the call cancelled #W456, or none | Completion-claim extractor (typed: action + entity id) → match against executed write calls by tool and key arg | F-03, F-06 | M | P1 | Precision ≥ 80% on the golden set | Value |
| F-09 | **Undecided-turn handling** (LLM fallback, opt-in) | ✅ `scan --judge` | Rules abstain; some teams want coverage | Keep opt-in; send only undecided turns; show "decided by LLM" distinctly; never mix into precision claims | `[full]` extra | S | P1 | — | Value |

### 2.2 Core differentiating features

| ID | Feature | Status | Problem → why | How | Deps | Cx | Pri | Success measure | Value/Optics |
|---|---|---|---|---|---|---|---|---|---|
| F-10 | **`init`: contract mining** | ❌ (designed in the 2026-08-05 note §4) | Hand-writing regex contracts costs about 1 h per bot for us and is impossible for strangers. **The adoption blocker** | 1. Deterministic mining: tool names, result keys/types, success predicate, value samples, write vs read tools by name and arg heuristics. 2. Optional one-shot LLM proposes claim extractors and declines from sample turns. 3. Emits `contract.yaml` with comments + a coverage summary | F-03 | L | P0 | Stranger reaches ≥ 70% decided coverage in < 30 min | Value |
| F-11 | **Backtest coverage report** | ❌ | Teams need to know what the contract can and can't see before trusting it | Run the contract on N historical turns → decided %, flagged %, abstain reasons, and the "disagreement set" with the optional LLM judge | F-10 | M | P0 | Used in every onboarding call | Value |
| F-12 | **`keep`: failure → regression case** | ⚠️ `Synthesizer` makes adversarial LLM probes, not real cases | Real failures are the best tests; synthetic probes reward "refuse everything" | Case = original input + conversation prefix + recorded tool responses + expected assertions (the check that failed must now pass, plus "must not decline when a tool succeeded") | F-13 | M | P0 | ≥ 50% of flagged turns kept by partners | Value |
| F-13 | **Record/replay cassettes** | ❌ (replay hits **real tools** today) | Replaying production failures against live tools has side effects (refunds, cancellations) and flakes | Cassette = ordered tool calls → responses. Agent-side recorder/replayer via a tiny SDK hook (Python decorator/middleware) or the HTTP adapter's "replay mode". Unexpected calls fail loudly | Adapter contract v2 | L | P0 | Zero live tool calls during `test`; same verdict over 5 runs at temperature 0 | Value |
| F-14 | **`test` / CI gate** | ⚠️ `gate.py` exists; live agent; LLM-scored cases | Prompt, model and tool changes silently regress agents | Run all cases through the agent under the candidate prompt/model with cassettes; score with the deterministic checks; exit non-zero on regression; JUnit XML output; separate "normal traffic" cases so refusal is penalised | F-12, F-13 | M | P0 | Partner adds it to CI and keeps it ≥ 4 weeks | Value |
| F-15 | **Fix proposal** (prompt patch + measured delta) | ⚠️ `Patcher` (injection-prone, single incident) | Teams want a starting point, not just a red light | Patch from a *cluster* of kept cases; quote traffic as data, never as instruction; score on kept + normal cases before showing; never write anywhere until a human approves | F-12, F-14 | M | P2 | Patch accepted (possibly edited) in ≥ 30% of cases | Value; Optics if unscored |
| F-16 | **Open fix as PR** | ✅ `cassandra pr` (with a known branch bug) | Fixes should land through review like code | Keep; fix the `git switch` fallback; body = case list + before/after | F-15 | S | P2 | — | Value |

### 2.3 Developer experience

| ID | Feature | Status | Notes | Cx | Pri |
|---|---|---|---|---|---|
| F-17 | Clean package: import `cassandra_ai`, no top-level `patient`/`dashboard`, pinned-compatible deps | ⚠️ 0.3.0 collides with `cassandra-driver`; `mcp` 2.x breaks `[full]` | **Shipped defect: fix first** | S | P0 |
| F-18 | Errors that say what to do (bad JSONL line, empty contract, no tool_calls present, extractor never fires) | ⚠️ partial | `scan` already names bad lines; extend to contract linting | S | P1 |
| F-19 | `contract lint` + `explain <turn-id>` (shows each check's decision path) | ❌ | Makes deterministic verdicts debuggable; "why was this flagged?" in one command | M | P1 |
| F-20 | 5-minute quickstart with a bundled sample log (TravelPal held-out) | ⚠️ `docs/SCAN.md` | Copy-paste runnable; no keys | S | P0 |
| F-21 | Docs site (mkdocs) | ❌ | After the API stabilises | M | P2 |
| F-22 | Windows/macOS/Linux, Python 3.11–3.13 matrix in CI | ❌ no CI | — | S | P0 |

### 2.4 Collaboration

| ID | Feature | Status | Notes | Cx | Pri |
|---|---|---|---|---|---|
| F-23 | Review queue: confirm or dismiss each flag (labels feed precision stats and the golden corpus) | ❌ | The first thing a *team* pays for. File-based in OSS (`labels.jsonl`), UI in the server | M | P1 (server P2) |
| F-24 | Shareable report link / export (PDF/HTML) with redaction | ❌ | Reports travel to managers and compliance | S | P2 |
| F-25 | Slack/Teams digest of new confirmed failures | ❌ | Where teams live; weekly, not per-event | S | P2 |

### 2.5 Automation and AI capabilities

| ID | Feature | Status | Notes | Cx | Pri |
|---|---|---|---|---|---|
| F-26 | Typed claim extraction with a small model (replace hand regex) | ❌ (decided as "the design decision before Tier 1" on 2026-08-05) | LLM *extracts*, code *decides*. The verdict stays deterministic and auditable | L | P1 |
| F-27 | Incident clustering (group flagged turns by check, tool and claim type) | ❌ | Needed before fix proposals are reliable (TravelPal: "patch from a cluster, not one incident") | M | P2 |
| F-28 | Continuous verification of live traces (the original Watcher loop, rebuilt) | ⚠️ the current Watcher has data-loss races | Server feature. Rule-first, not LLM-first like `Diagnostician.diagnose` today | L | P2 |
| F-29 | Distilled on-prem judge for undecided turns | ❌ | Year 2. Needs thousands of confirmed labels (F-23) | XL | P3 |

### 2.6 Enterprise

| ID | Feature | Status | Notes | Cx | Pri |
|---|---|---|---|---|---|
| F-30 | **Golden labelled corpus + published precision per check** | 🧪 TravelPal labels; tau-bench | Enterprises buy measured precision, not claims. Also our regression suite | M | P0 |
| F-31 | Self-hosted server (one container + Postgres) | ❌ | Fintech/insurance won't send transcripts to a startup | L | P2 |
| F-32 | SSO/SAML, RBAC, audit log of reviews/approvals | ❌ | Standard enterprise gate | L | P3 |
| F-33 | Data controls: PII redaction before storage, retention policies, BYO LLM key/endpoint | ❌ | Regulated buyers' first questions | M | P2 |
| F-34 | Audit export (every verdict + evidence + reviewer, per period) | ❌ | Turns verification into a compliance artefact; strong willingness-to-pay hypothesis for regulated buyers (unvalidated) | M | P3 |

### 2.7 Ecosystem and integrations

| ID | Feature | Status | Notes | Cx | Pri |
|---|---|---|---|---|---|
| F-35 | Recorder hooks for OpenAI Agents SDK, LangGraph, Pydantic AI (cassettes + JSONL export in one line) | ❌ | The fastest path to F-01 + F-13 for new teams | M each | P1 (one framework first) |
| F-36 | GitHub Action (`uses: <org>/verify-action`) | ⚠️ example YAML only | Distribution and retention | S | P1 |
| F-37 | Phoenix / Langfuse importers (read-only) | ⚠️ Phoenix via MCP only | Keep Phoenix as an *integration*, not the architecture (ELv2, single vendor) | M | P2 |
| F-38 | MCP server exposing scan/explain to IDE agents | ⚠️ exists, broken on `mcp` 2.x | Nice-to-have; fix the pin, don't extend | S | P3 |

### 2.8 Long-term / experimental

| ID | Feature | Notes | Pri |
|---|---|---|---|
| F-39 | In-path pre-execution action guard (block a write call that violates the contract) | Same contract as F-07, enforced before the tool runs. Latency and reliability burden; only after post-hoc checks prove precise | P3 |
| F-40 | Vertical check packs (refunds, bookings, claims, KYC) | Paid add-ons; built from partner contracts | P3 |
| F-41 | Cross-customer failure taxonomy/benchmark (opt-in, anonymised) | Moat candidate; requires trust and legal work | P3 |
| F-42 | NLI layer for RAG evidence, multilingual (Hindi) | ✅ code exists but **no production caller**; keep dormant until a RAG customer asks | P3 |

## 3. Explicitly *not* in the product (and why)

| Not building | Why |
|---|---|
| A tracing platform / span viewer / dashboards of latency and cost | Ring 1 is commoditised and free (Sentry, Phoenix, Langfuse). We consume traces. |
| A general "is this answer good?" grader | LLM judges do this badly, and incumbents already sell it. Our verdicts must be checkable. |
| Autonomous prompt changes in production | The degenerate optimum is "refuse everything", and the patcher is injection-prone. Humans approve every change. |
| Hosting Phoenix | Elastic License 2.0 forbids providing it as a managed service. |
| Model fine-tuning for onboarding | Decided on 2026-08-05: zero training data, once-per-customer task, so it's the wrong tool. Mine, propose, backtest instead. |
| More demo agents, more languages, more judge types | Optics. They don't move validation. |
| The ADK `LoopAgent` / Agent Engine envelope as a product surface | A hackathon requirement. `LoopAgent` is deprecated in google-adk 2.13. Keep it as an optional example, out of the core. |

## 4. Interface decision

| Option | Fit | Verdict |
|---|---|---|
| **CLI-first** (local, offline, CI-native) | Matches "try on exported logs before procurement" and "gate in CI". Lowest friction | **Primary** |
| **Library/SDK** (contract + checks + recorder importable in Python) | Needed for recorder hooks (F-35) and for teams embedding checks in their own eval suites | **Primary, same package** |
| GitHub-native (Action + PR comments) | Retention loop; where fixes land | Secondary (Action, PR comment) |
| Web app (server: review queue, history, continuous verification) | What *teams* pay for; built only after the CLI is trusted | Phase 5+ |
| IDE extension, desktop app | No evidence of need | Not planned |
| Standalone API | Server exposes one later; not a starting surface | Later |
