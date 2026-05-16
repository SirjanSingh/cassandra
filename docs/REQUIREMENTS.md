# Cassandra — Detailed Requirements

**Version:** 1.0 · Companion to [PRD.md](PRD.md) and [ARCHITECTURE.md](ARCHITECTURE.md)
Requirement IDs are stable references for the implementation plan and test matrix.

---

## 1. Component Inventory

| ID | Component | One-line role |
|----|-----------|---------------|
| C1 | **The Patient** | Deliberately fragile e-commerce support agent — the on-camera victim |
| C2 | **Phoenix + MCP** | Trace store + eval/experiment/dataset/prompt backend + the required partner MCP server |
| C3 | **Cassandra** | The meta-agent (LoopAgent of 5 specialists) |
| C4 | **Dashboard** | Cloud Run UI — the demo surface |
| C5 | **Incident Seeder** | Deterministic script that forces a reproducible failure |

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

Cassandra is an ADK `LoopAgent` wrapping a `SequentialAgent` of five sub-agents. Every
Phoenix interaction MUST go through the Phoenix **MCP server** (not a direct SDK call) so
the MCP integration is genuine and the surface coverage is maximal.

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

#### Sub-agent: Synthesizer (FR-S*)

- **FR-S1** Given an `Incident`, the Synthesizer SHALL use Gemini 3 to generate N
  (default 12) adversarial variations of the failing input that probe the same weakness,
  each paired with an expected-correct answer / acceptance criterion.
- **FR-S2** The Synthesizer SHALL create a **Phoenix dataset** (via MCP) named
  `cassandra-<class>-<incident-id>` containing the N examples.
- **FR-S3** Generated examples SHALL be semantically diverse (varied phrasing, region,
  edge values) — not trivial string permutations.

#### Sub-agent: Evaluator (FR-E*)

- **FR-E1** The Evaluator SHALL create a **Phoenix experiment** (via MCP) running the
  synthesized dataset against the current Patient prompt as baseline.
- **FR-E2** Scoring SHALL use an LLM-as-judge eval (Gemini 3) returning pass/fail per
  example with rationale.
- **FR-E3** After the Patcher proposes a candidate, the Evaluator SHALL run the same
  dataset against the candidate prompt as a second experiment run/variant.
- **FR-E4** The Evaluator SHALL compute and expose `baseline_pass_rate`,
  `candidate_pass_rate`, and `delta`.

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

### 2.4 C5 — Incident Seeder

- **FR-IS1** A script SHALL send a fixed customer message that deterministically triggers
  the `get_refund_policy` tool failure path and the resulting hallucination, every run.
- **FR-IS2** The seeder SHALL support a small library (~20) of hand-labeled trap inputs
  used for the diagnostic-precision metric.

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

---

## 4. Phoenix MCP Surface Coverage (scored capability)

Cassandra MUST exercise, at minimum, these Phoenix MCP tool families end-to-end. Coverage
breadth is a direct Technological-Implementation differentiator in an Arize-judged bucket.

| MCP family | Used by | Requirement |
|------------|---------|-------------|
| Projects / list | Watcher | discover `patient-prod` |
| Spans / traces query | Watcher | FR-W2 |
| Span annotations (write) | Diagnostician | FR-D3 |
| Datasets (create + add examples) | Synthesizer | FR-S2 |
| Experiments (create + run + read results) | Evaluator | FR-E1, FR-E3, FR-E4 |
| Prompt management (version + retrieve) | Patcher | FR-PA2 |

---

## 5. Acceptance Criteria (Definition of Done, testable)

- **AC-1** From a clean deploy, running the Incident Seeder once produces an annotated
  span in Phoenix `patient-prod` within 10 s (NFR-1, FR-D3).
- **AC-2** That same incident yields a Phoenix dataset of ≥ 12 diverse examples (FR-S1/2).
- **AC-3** A Phoenix experiment exists with baseline and candidate runs; candidate
  pass-rate − baseline pass-rate ≥ a clearly visible positive delta (target baseline ≤4/12,
  candidate ≥10/12) (FR-E4).
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
