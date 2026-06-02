# Cassandra — Detailed Requirements

**Version:** 1.1 (updated 2026-06-02 to reflect the as-built system) · Companion to
[PRD.md](PRD.md) and [ARCHITECTURE.md](ARCHITECTURE.md). Requirement IDs are stable
references for the implementation plan and test matrix.

> **v1.1 additions:** the pipeline grew to 8 stages — RootCause (FR-RC*), TraceReplay
> (FR-RP*), RedTeam (FR-RT*) — plus severity (FR-D5), cost/latency (FR-E5), a published
> MCP server (C6 / FR-MCP*), and self-evaluation (FR-SE*). Evaluation now runs **live**
> (the Phoenix MCP has no run-experiment tool). The reasoning core is Gemini 3 **or**
> OpenAI **or** OpenRouter (selected at runtime).

---

## 1. Component Inventory

| ID | Component | One-line role |
|----|-----------|---------------|
| C1 | **The Patient** | Deliberately fragile e-commerce support agent — the on-camera victim |
| C2 | **Phoenix + MCP** | Trace store + eval/dataset/prompt backend + the required partner MCP server (consumed) |
| C3 | **Cassandra** | The meta-agent — an 8-stage supervision pipeline in an ADK LoopAgent |
| C4 | **Dashboard** | Cloud Run UI (single self-contained HTML) — the demo surface |
| C5 | **Incident Seeder** | Deterministic script that forces a reproducible failure |
| C6 | **cassandra-mcp** | Cassandra's own published MCP server (supervision-as-tools) |

---

## 2. Functional Requirements

### 2.1 C1 — The Patient (the victim agent)

- **FR-P1** The Patient SHALL be an ADK agent using Gemini 3 that answers e-commerce
  customer-support questions (orders, refunds, shipping).
- **FR-P2** The Patient SHALL expose at least two tools: `lookup_order(order_id)` and
  `get_refund_policy(region)`. Tools SHALL be intentionally flaky: `get_refund_policy`
  returns `None`/error for some regions; `lookup_order` occasionally returns malformed
  data.
- **FR-P3** The Patient's system prompt SHALL be intentionally fragile (no explicit
  instruction to refuse when policy data is missing), causing it to hallucinate a refund
  policy when the tool fails.
- **FR-P4** The Patient SHALL be instrumented with OpenInference/OpenTelemetry and export
  spans (LLM calls + tool calls, with full input/output) to the Phoenix project
  `patient-prod`.
- **FR-P5** The Patient SHALL be invokable via an HTTP endpoint and from the dashboard
  "send customer message" box.

### 2.2 C3 — Cassandra meta-agent

Cassandra is an ADK `LoopAgent` wrapping a custom `BaseAgent` that runs an 8-stage
`SupervisionPipeline` (Watcher → Diagnostician → RootCause → Synthesizer → Evaluator(base)
→ Patcher → Evaluator(candidate) → Replay → RedTeam). Pipeline *logic* is plain,
unit-tested Python; ADK is the runtime envelope. Reasoning core is Gemini 3 / OpenAI /
OpenRouter, selected at runtime behind `llm.py`. All Phoenix reads/writes go through the
Phoenix **MCP server** wrapper (NFR-10); live agent evaluation is direct HTTP to the
Patient because the MCP exposes no run-experiment tool.

#### Sub-agent: Watcher (FR-W*)

- **FR-W1** A Cloud Function SHALL run on a schedule (configurable, default 60s) and
  invoke the Watcher.
- **FR-W2** The Watcher SHALL query Phoenix via MCP for spans in `patient-prod` created
  since the last persisted cursor (high-water timestamp/span id).
- **FR-W3** The Watcher SHALL filter to LLM and tool spans and pass candidate span trees
  (a root LLM span plus its child tool spans) downstream.
- **FR-W4** The Watcher SHALL persist its cursor durably so restarts do not reprocess or
  skip spans.

#### Sub-agent: Diagnostician (FR-D*)

- **FR-D1** For each candidate span tree, the Diagnostician SHALL use Gemini 3 as an
  LLM-as-judge to classify it as exactly one of: `hallucination`, `prompt_drift`,
  `tool_failure`, `ok`.
- **FR-D2** Each verdict SHALL include a natural-language rationale and a confidence in
  `[0,1]`.
- **FR-D3** For any non-`ok` verdict with confidence ≥ threshold (default 0.7), the
  Diagnostician SHALL write a **Phoenix span annotation** (via MCP) on the offending span
  containing label, rationale, and confidence.
- **FR-D4** The Diagnostician SHALL emit a structured `Incident` object (span id, trace id,
  class, rationale, offending input, observed output, expected behavior) to the dashboard
  event stream and to the next sub-agent.
- **FR-D5** The Diagnostician SHALL assign each incident a **severity** (`critical` / `high`
  / `medium` / `low`) derived from failure class × confidence, exposed on the dashboard.

#### Sub-agent: RootCauseAnalyst (FR-RC*)

- **FR-RC1** After a confirmed failure, the RootCauseAnalyst SHALL use the LLM to produce a
  structured causal analysis: the single culprit, an ordered causal chain from trigger to
  bad output, contributing factors, and a concrete `fix_strategy` consumed by the Patcher.
- **FR-RC2** The causal analysis SHALL be appended to the same Phoenix span annotation
  thread (via MCP) so the "why" lives next to the "what" in the customer's own tool.

#### Sub-agent: Synthesizer (FR-S*)

- **FR-S1** Given an `Incident`, the Synthesizer SHALL use Gemini 3 to generate N
  (default 12) adversarial variations of the failing input that probe the same weakness,
  each paired with an expected-correct answer / acceptance criterion.
- **FR-S2** The Synthesizer SHALL create a **Phoenix dataset** (via MCP) named
  `cassandra-<class>-<incident-id>` containing the N examples.
- **FR-S3** Generated examples SHALL be semantically diverse (varied phrasing, region,
  edge values) — not trivial string permutations.

#### Sub-agent: Evaluator (FR-E*)

- **FR-E1** The Evaluator SHALL score the **current** Patient prompt as baseline by running
  each synthesized probe through the live Patient (`session_id="test"`) and judging it.
  *(The Phoenix MCP exposes no run-experiment tool, so the experiment runs live against the
  agent — the numbers are real, never stubbed.)*
- **FR-E2** Scoring SHALL use an LLM-as-judge returning pass/fail per example.
- **FR-E3** After the Patcher proposes a candidate, the Evaluator SHALL score the candidate
  prompt over the same probes.
- **FR-E4** The Evaluator SHALL compute and expose `baseline_pass_rate`,
  `candidate_pass_rate`, and `delta`.
- **FR-E5** The Evaluator SHALL compute a candidate-vs-baseline **EfficiencyReport** (avg
  tokens + latency, with deltas). When `PHOENIX_EXPERIMENTS_ENABLED`, it SHALL also register
  the A/B as a real Phoenix experiment via the Phoenix client (guarded; degrades to no-op).

#### Sub-agent: Patcher (FR-PA*)

- **FR-PA1** Given an `Incident` and its class, the Patcher SHALL use Gemini 3 to produce
  a revised Patient system prompt that specifically closes the failure mode (e.g. an
  explicit refusal-on-missing-policy instruction).
- **FR-PA2** The Patcher SHALL register the candidate prompt as a **new version in
  Phoenix prompt management** (via MCP), with metadata linking it to the incident and
  dataset.
- **FR-PA3** The Patcher SHALL queue an **A/B experiment** (current vs candidate) and
  SHALL NOT auto-promote the candidate to live traffic (enforces PRD NG1).
- **FR-PA4** The Patcher SHALL emit a human-readable unified diff of old vs new prompt to
  the dashboard.

#### Sub-agent: TraceReplay (FR-RP*)

- **FR-RP1** The TraceReplay SHALL re-run the **exact original failing input** against the
  live Patient under the candidate prompt (`system_override`, `session_id="test"`) and use
  an LLM judge to decide whether this specific case is now FIXED, emitting before/after.

#### Sub-agent: RedTeam (FR-RT*)

- **FR-RT1** The RedTeam SHALL fire the synthesized adversarial probes (capped for latency)
  at the live Patient under both the current and candidate prompts and report how many
  survive the patch (current pass-count → candidate pass-count).

#### Loop control (FR-L*)

- **FR-L1** The LoopAgent SHALL process one incident through the full Watcher→Patcher
  chain per cycle and then yield (deterministic, demo-friendly).
- **FR-L2** Each stage transition SHALL emit a timestamped event to the dashboard stream.
- **FR-L3** A processed incident SHALL be deduplicated (by offending span id) so the same
  failure is not re-patched on the next poll.

### 2.3 C4 — Dashboard

- **FR-DB1** The dashboard SHALL render a live, append-only event feed via SSE/WebSocket
  with no manual refresh.
- **FR-DB2** It SHALL show, per incident, in order: the raw customer↔agent exchange, the
  Diagnostician verdict + rationale, a link to the annotated Phoenix span, the synthesized
  dataset (rows visible), the experiment results (baseline vs candidate bars), and the
  prompt diff.
- **FR-DB3** It SHALL provide a "Send customer message" input that calls the Patient
  (drives the live demo).
- **FR-DB4** Deep links SHALL open the corresponding Phoenix span/dataset/experiment in a
  new tab (proves the work landed in the real product).
- **FR-DB5** First meaningful paint and the alert animation SHALL be visually striking
  within the first 10 seconds of an incident (demo requirement).
- **FR-DB6** The dashboard SHALL render, per incident, the **severity** chip, the
  candidate-vs-baseline **efficiency delta** (tokens/latency), the **replay** before/after
  with a FIXED/STILL-BROKEN verdict, and the **red-team** survivor table; and SHALL provide
  a "Grade my own diagnoses" control that calls `POST /selfeval` and shows the scorecard.

### 2.4 C5 — Incident Seeder

- **FR-IS1** A script SHALL send a fixed customer message that deterministically triggers
  the `get_refund_policy` tool failure path and the resulting hallucination, every run.
- **FR-IS2** A shared hand-labeled trap library (`cassandra/traps.py`, single source of
  truth) SHALL cover all failure classes (hallucination, tool_failure, prompt_drift, ok)
  and back the diagnostic-precision metric (FR-SE*).

### 2.5 C6 — cassandra-mcp (published MCP server, FR-MCP*)

- **FR-MCP1** Cassandra SHALL publish an MCP server (`cassandra/mcp_server.py`, FastMCP)
  over stdio via the `cassandra-mcp` console entry point.
- **FR-MCP2** It SHALL expose at least: `diagnose`, `synthesize_evals`, `propose_patch`
  (composable, no Phoenix), `supervise_latest` (full Phoenix-deep loop), and
  `self_evaluate`. Tools SHALL reuse the same sub-agent code as the in-process pipeline.

### 2.6 Self-evaluation (introspection, FR-SE*)

- **FR-SE1** A `SelfEvaluator` SHALL run the shared trap library through the live Patient
  and Cassandra's own Diagnostician, scoring verdicts against ground truth, and return a
  `Scorecard` (overall accuracy + per-failure-class breakdown).
- **FR-SE2** Cassandra SHALL trace its **own** reasoning into the `cassandra-meta` Phoenix
  project (`init_self_tracing`, OpenInference), gated by `SELF_TRACE_ENABLED` and guarded.

---

## 3. Non-Functional Requirements

| ID | Category | Requirement |
|----|----------|-------------|
| NFR-1 | Latency | Seeded failure → annotated Phoenix span in < 10 s end-to-end during demo. |
| NFR-2 | Reliability | The seeded incident path MUST be deterministic — zero reliance on sampling luck for the recording. |
| NFR-3 | Observability | Cassandra itself SHALL export its own spans to a separate Phoenix project `cassandra-meta` (an agent that is itself observable — reinforces the recursive story). |
| NFR-4 | Security | All secrets (Phoenix API key, GCP creds) via Secret Manager; none in repo, env files git-ignored; `.env.example` only. |
| NFR-5 | Portability | Runs against Phoenix Cloud free tier; self-host on Cloud Run as documented fallback. |
| NFR-6 | Cost | Stays within hackathon free/credit budget; default poll interval ≥ 60 s; model calls batched per cycle. |
| NFR-7 | Reproducibility | `README` + one script SHALL bring the full system up from a clean GCP project. |
| NFR-8 | Submission compliance | Public GitHub repo; Apache-2.0 `LICENSE` at repository root, detectable by Devpost; hosted working URL; ≤3-min video. |
| NFR-9 | Code quality | Typed Python, modular per sub-agent, unit tests for classification and synthesis prompt contracts. |
| NFR-10 | Maintainability | Phoenix MCP access isolated behind one wrapper module so a tool-signature change is a one-file fix. |
| NFR-11 | Composability | Cassandra SHALL publish its supervision as an MCP server (C6) callable by any external agent/IDE, reusing the in-process sub-agent code. |
| NFR-12 | Robustness | Optional integrations (self-tracing, on-product Phoenix experiments) SHALL be flag-gated and guarded so any failure degrades to a no-op without breaking the loop. |

---

## 4. Phoenix MCP Surface Coverage (scored capability)

Cassandra MUST exercise, at minimum, these Phoenix MCP tool families end-to-end. Coverage
breadth is a direct Technological-Implementation differentiator in an Arize-judged bucket.

| MCP tool | Used by | Requirement |
|----------|---------|-------------|
| `list-projects` | Watcher | discover `patient-prod` |
| `get-spans` | Watcher | FR-W2 |
| `add-span-annotations` (write) | Diagnostician / RootCause | FR-D3, FR-RC2 |
| `add-dataset-examples` | Synthesizer | FR-S2 |
| `upsert-prompt` (version) | Patcher | FR-PA2 |
| `get-experiment-by-id` (read) | Evaluator | FR-E (read-back) |

> The Phoenix MCP has **no run-experiment tool**, so baseline/candidate scoring runs live
> against the agent (FR-E1/3); the optional on-product experiment (FR-E5) uses the Phoenix
> **Python client**, not MCP. Beyond consuming the partner MCP, Cassandra also **publishes**
> its own MCP server (C6 / FR-MCP*) — depth on *both* sides of MCP.

---

## 5. Acceptance Criteria (Definition of Done, testable)

- **AC-1** From a clean deploy, running the Incident Seeder once produces an annotated
  span in Phoenix `patient-prod` within 10 s (NFR-1, FR-D3).
- **AC-2** That same incident yields a Phoenix dataset of ≥ 12 diverse examples (FR-S1/2).
- **AC-3** A live baseline-vs-candidate evaluation over the synthesized dataset shows a
  clearly visible positive delta (candidate pass-rate − baseline pass-rate); the live
  **replay** of the original input reports FIXED (FR-E4, FR-RP1). When
  `PHOENIX_EXPERIMENTS_ENABLED`, a real Phoenix experiment also exists (FR-E5).
- **AC-4** A new prompt version exists in Phoenix prompt management linked to the incident,
  with an A/B experiment queued and the candidate NOT live (FR-PA2/3, NG1).
- **AC-5** The dashboard shows the full chain for that incident with working deep links
  into Phoenix (FR-DB2/4).
- **AC-6** ≥ 5 Phoenix MCP tool families were called during the run (§4).
- **AC-7** Repo is public with a Devpost-detectable top-level Apache-2.0 LICENSE; hosted
  dashboard URL is reachable; demo video ≤ 3:00 (NFR-8).
- **AC-8** Diagnostic precision ≥ 90% on the 20-case hand-labeled trap set (FR-IS2).

---

## 6. Test Matrix (high level)

| Test | Validates |
|------|-----------|
| Unit: Diagnostician classification on 20 labeled traps | FR-D1, AC-8 |
| Unit: Synthesizer output schema + diversity heuristic | FR-S1, FR-S3 |
| Unit: Phoenix MCP wrapper contract (mocked) | NFR-10 |
| Integration: seeder → annotation (live Phoenix) | AC-1 |
| Integration: full loop one incident → all 5 MCP families | AC-1..6 |
| Manual: dashboard visual / latency dry-run before recording | FR-DB5, NFR-1 |
| Manual: submission checklist walkthrough | NFR-8, AC-7 |
