# Cassandra — Architecture

Companion to [PRD.md](PRD.md) and [REQUIREMENTS.md](REQUIREMENTS.md). Requirement IDs
(FR-*, NFR-*) reference REQUIREMENTS.md.

---

## 1. Context Diagram

```
        ┌────────────────────────────────────────────────────────────┐
        │                      Google Cloud                            │
        │                                                              │
  user ─┼─▶ Dashboard (Cloud Run) ──"send message"──▶ The Patient (C1) │
        │        ▲                                         │           │
        │        │ SSE event feed                          │ OpenInference
        │        │                                         ▼           │
        │   Cassandra LoopAgent (C3)              ┌──────────────────┐  │
        │   on Vertex AI Agent Engine ──MCP──────▶│  Phoenix (C2)    │  │
        │        ▲                                │  project:        │  │
        │        │ trigger (≤60s)                 │  patient-prod    │  │
        │   Cloud Function: trace poller          │  + MCP server    │  │
        │                                         └──────────────────┘  │
        │   Secret Manager ── keys ──▶ all components                   │
        │   BigQuery (optional, stretch) ◀── span export                │
        └────────────────────────────────────────────────────────────┘
```

The Patient and Cassandra are two **separate** agents. The only channel between them is
Phoenix telemetry — Cassandra never calls the Patient's internals. This is the whole
point: Cassandra supervises *through observability*, exactly as a real meta-agent would.

---

## 2. The Cassandra Agent Graph

```
LoopAgent("cassandra")                       # FR-L1 — one incident per cycle, then yield
└── SequentialAgent("supervision_pipeline")
    ├── Watcher          # FR-W*  pull new spans from Phoenix via MCP
    ├── Diagnostician    # FR-D*  Gemini-3 LLM-as-judge → classify → annotate via MCP
    ├── Synthesizer      # FR-S*  build adversarial dataset → Phoenix dataset via MCP
    ├── Evaluator        # FR-E*  Phoenix experiment baseline vs candidate via MCP
    └── Patcher          # FR-PA* propose prompt → version in Phoenix → queue A/B via MCP
```

- Reasoning core for every sub-agent: **Gemini 3**.
- Orchestration: **ADK** `LoopAgent` + `SequentialAgent`. Multi-agent structure is used
  because it cleanly maps to the loop — but per the strategy doc it is **not** pitched as
  the novelty (orchestration is table stakes; the *meta* concept is the novelty).
- Shared state: an `Incident` object threads through the pipeline (span id, trace id,
  class, rationale, offending input, observed/expected output, dataset id, experiment id,
  prompt version).

---

## 3. Data Flow (one incident, the demo path)

1. Operator (or Incident Seeder, FR-IS1) sends a customer message to the Patient.
2. Patient calls `get_refund_policy(region)` → tool returns error/None → fragile prompt →
   Patient hallucinates a confident, false refund policy. OpenInference exports the LLM +
   tool spans to Phoenix `patient-prod` (FR-P4).
3. Cloud Function fires (≤60 s) → Watcher queries Phoenix MCP for spans after the cursor
   (FR-W2), advances the cursor (FR-W4), passes the span tree on.
4. Diagnostician runs Gemini-3 LLM-as-judge over the span tree → `hallucination` @ 0.93
   (FR-D1/2) → writes a Phoenix **span annotation** via MCP (FR-D3) → emits `Incident` to
   the dashboard SSE stream (FR-D4).
5. Synthesizer generates 12 diverse adversarial trap prompts + expected answers (FR-S1) →
   creates Phoenix **dataset** via MCP (FR-S2).
6. Evaluator creates a Phoenix **experiment**: baseline (current prompt) over the dataset,
   LLM-as-judge scoring (FR-E1/2) → e.g. 3/12 pass.
7. Patcher generates a hardened system prompt (explicit refuse-on-missing-policy) (FR-PA1)
   → registers it as a new **Phoenix prompt version** via MCP (FR-PA2).
8. Evaluator re-runs the experiment with the candidate prompt (FR-E3) → e.g. 11/12 pass →
   computes delta (FR-E4).
9. Patcher queues the A/B experiment, does **not** promote (FR-PA3, NG1) → emits prompt
   diff (FR-PA4).
10. Dashboard has streamed every step; deep links open the real Phoenix span / dataset /
    experiment (FR-DB2/4). Loop yields; incident deduped by span id (FR-L3).

---

## 4. Phoenix MCP Integration

The required partner integration. All Phoenix access is funneled through a single wrapper
module `cassandra/phoenix_mcp.py` (NFR-10) that speaks to the `@arizeai/phoenix-mcp`
server. Tool families and their owners:

| MCP family | Owner sub-agent | Operation |
|------------|-----------------|-----------|
| projects.list | Watcher | resolve `patient-prod` |
| spans.query / traces.get | Watcher | new spans since cursor |
| annotations.create | Diagnostician | write verdict onto offending span |
| datasets.create / datasets.addExamples | Synthesizer | adversarial dataset |
| experiments.create / .run / .getResults | Evaluator | baseline + candidate scoring |
| prompts.createVersion / .get | Patcher | versioned candidate prompt |

> **Day-1 spike (R1 mitigation):** before any feature code, a throwaway script
> enumerates the live Phoenix MCP tool list and records exact tool names + argument
> schemas. The table above is the *intended* surface; the spike makes it *actual*. Only
> `phoenix_mcp.py` changes if names differ.

---

## 5. Deployment Topology

| Component | Hosting | Notes |
|-----------|---------|-------|
| The Patient (C1) | Cloud Run service | HTTP endpoint; OpenInference exporter configured to Phoenix |
| Cassandra (C3) | Vertex AI Agent Engine | managed agent runtime (primary). Cloud Run fallback if Agent Engine deploy is flaky (R2) |
| Trace poller | Cloud Function + Cloud Scheduler | invokes Cassandra each interval (FR-W1) |
| Dashboard (C4) | Cloud Run service | FastAPI + SSE; serves the public submission URL (NFR-8) |
| Phoenix (C2) | Phoenix Cloud (free) | self-host on Cloud Run is the documented fallback (NFR-5) |
| Secrets | Secret Manager | Phoenix API key, GCP creds (NFR-4) |
| BigQuery | optional | long-term span analytics — stretch only |

State that must persist across poller invocations (Watcher cursor FR-W4, incident dedupe
set FR-L3): a small Firestore collection or a GCS object — chosen for zero-ops simplicity,
not a full database.

---

## 6. Self-Observability (the recursive flourish)

Per NFR-3, Cassandra exports its **own** spans to a separate Phoenix project
`cassandra-meta`. In the demo this is a one-line callout: *"and yes — the agent that
watches agents is itself observable in Phoenix."* It costs almost nothing to wire and
reinforces the unique-idea score.

---

## 7. Technology Choices & Rationale

| Choice | Why |
|--------|-----|
| Gemini 3 | Mandatory; strong at structured reasoning over JSON span trees |
| ADK LoopAgent/SequentialAgent | Mandatory build path; the loop maps 1:1 to the pipeline |
| Vertex AI Agent Engine | Mandatory-recommended managed runtime; less ops than Cloud Run for the agent |
| Phoenix MCP (not SDK) | The required partner MCP integration must be genuine MCP, and it maximizes scored surface coverage |
| FastAPI + SSE dashboard | Smallest reliable path to a live, animated feed for the video |
| Firestore/GCS for cursor | Avoids standing up a DB for two tiny pieces of state |
| Apache-2.0 | OSI-approved, Devpost-detectable top-level license (NFR-8) |

---

## 8. Failure Modes & Safeguards

| Failure | Safeguard |
|---------|-----------|
| Phoenix MCP transient error | Wrapper retries with backoff; poller is idempotent via cursor (FR-W4) |
| Diagnostician false positive | Confidence threshold (FR-D3) + annotations are advisory, never auto-applied |
| Duplicate incident each poll | Dedupe by offending span id (FR-L3) |
| Demo flakiness | Deterministic seeder (FR-IS1, NFR-2); pre-recorded fallback clip kept as insurance |
| Agent Engine deploy issues | Cloud Run fallback path documented and rehearsed before submission week |
