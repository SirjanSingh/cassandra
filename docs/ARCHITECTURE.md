# Cassandra — Architecture

Companion to [PRD.md](PRD.md) and [REQUIREMENTS.md](REQUIREMENTS.md). Requirement IDs
(FR-*, NFR-*) reference REQUIREMENTS.md.

> **Status: reflects the as-built system (updated 2026-06-02).** The pipeline has grown
> from the original 5 stages to **8** (root-cause, live replay, and red-team were added),
> evaluation now runs **live against the agent** (Phoenix MCP exposes no run-experiment
> tool), Cassandra **publishes its own MCP server**, traces **its own reasoning** into
> Phoenix, and **grades its own diagnostic accuracy**. See §9 for the session changelog.

---

## 1. Context Diagram

```
        ┌────────────────────────────────────────────────────────────┐
        │                      Google Cloud                            │
        │                                                              │
  user ─┼─▶ Dashboard (Cloud Run) ──"send message"──▶ The Patient (C1) │
        │        ▲     │                                   │           │
        │        │ SSE │ /selfeval                         │ OpenInference
        │        │     ▼                                   ▼           │
        │   Cassandra LoopAgent (C3)              ┌──────────────────┐  │
        │   on Vertex AI Agent Engine ──MCP──────▶│  Phoenix (C2)    │  │
        │        │  ▲                              │  projects:       │  │
        │        │  │ trigger / 5s loop            │  patient-prod    │  │
        │        │  Cloud Function: trace poller   │  cassandra-meta  │  │
        │        │                                 │  + MCP server    │  │
        │        └── self-traces ──OpenInference──▶└──────────────────┘  │
        │                                                              │
        │   cassandra-mcp (published) ◀── Claude Desktop / Cursor / any agent
        │   Secret Manager ── keys ──▶ all components                   │
        └────────────────────────────────────────────────────────────┘
```

The Patient and Cassandra are two **separate** agents. The only channel between them is
Phoenix telemetry — Cassandra never calls the Patient's internals (except a sandboxed
`session_id="test"` path used by replay / red-team / evaluation, which the Watcher filters
out so Cassandra never supervises itself into a loop). Cassandra supervises *through
observability*, exactly as a real meta-agent would.

---

## 2. The Cassandra Agent Graph

```
LoopAgent("cassandra")                       # FR-L1 — one incident per cycle, then yield
└── SupervisionAgent (custom ADK BaseAgent)  # runs one SupervisionPipeline.run_once()
    ├── Watcher          # FR-W*   pull new spans from Phoenix via MCP (skip session=="test")
    ├── Diagnostician    # FR-D*   LLM-as-judge → classify → annotate via MCP → severity
    ├── RootCauseAnalyst # FR-RC*  why it broke: culprit + causal chain + fix strategy
    ├── Synthesizer      # FR-S*   build adversarial dataset → Phoenix dataset via MCP
    ├── Evaluator(base)  # FR-E*   score current prompt live over the dataset (+efficiency)
    ├── Patcher          # FR-PA*  propose hardened prompt → Phoenix prompt version via MCP
    ├── Evaluator(cand)  # FR-E*   score candidate prompt; compute pass-rate + cost/latency delta
    ├── TraceReplay      # FR-RP*  re-run the ORIGINAL failing input on the candidate prompt
    └── RedTeam          # FR-RT*  fire synthesized probes at the live agent, current vs candidate
```

- **Reasoning core:** Gemini 3, **or** direct OpenAI (`gpt-4o-mini`/`gpt-4o`), **or**
  OpenRouter — selected at runtime in `cassandra/llm.py` from env. The pipeline logic is
  backend-agnostic.
- **Orchestration:** real ADK — `build_adk_agent()` returns a `LoopAgent` wrapping a
  genuine custom `BaseAgent` (`SupervisionAgent`) whose `_run_async_impl` runs one
  supervision cycle and reports the handled incident through session state (validated
  against `google-adk 2.1.0`). The pipeline *logic* lives in plain, unit-tested Python
  (`SupervisionPipeline`); ADK is the runtime envelope so the mandatory "built with Agent
  Builder/ADK + Agent Engine" requirement is met without coupling logic to the runtime.
- **Shared state:** one `Incident` object threads through the pipeline, enriched at each
  stage (verdict, severity, root cause, dataset, experiment pass-rates, efficiency,
  candidate prompt + diff, replay result, red-team result).

---

## 3. Data Flow (one incident, the demo path)

1. Operator (or Incident Seeder, FR-IS1) sends a customer message to the Patient.
2. Patient calls `get_refund_policy(region)` → tool returns error/None → fragile prompt →
   Patient hallucinates a confident, false refund policy. OpenInference exports the LLM +
   tool spans (with `llm.token_count.total`) to Phoenix `patient-prod` (FR-P4).
3. Watcher queries Phoenix MCP for spans after the cursor (FR-W2), skipping
   `session_id=="test"` probes, advances the cursor (FR-W4), passes the span tree on.
4. Diagnostician runs LLM-as-judge over the span tree → `hallucination` @ 0.93 (FR-D1/2) →
   assigns **severity** from class × confidence (FR-D5) → writes a Phoenix **span
   annotation** via MCP (FR-D3) → emits the `Incident` to the dashboard SSE stream (FR-D4).
5. RootCauseAnalyst explains *why* — culprit, ordered causal chain, contributing factors,
   and a concrete fix strategy for the Patcher (FR-RC1); appends it to the span annotation.
6. Synthesizer generates ~12 diverse adversarial probes + expected answers (FR-S1) →
   creates a Phoenix **dataset** via MCP (FR-S2).
7. Evaluator scores the **current** prompt by running the probes through the live Patient
   (`session_id="test"`) + LLM-judge → e.g. 2/8 pass; records avg tokens + latency (FR-E1/2).
8. Patcher generates a hardened system prompt using the fix strategy (FR-PA1) → registers
   it as a new **Phoenix prompt version** via MCP (FR-PA2) → emits a unified diff (FR-PA4).
9. Evaluator scores the **candidate** prompt over the same dataset → e.g. 8/8 pass →
   computes pass-rate delta **and** the cost/latency `EfficiencyReport` vs baseline (FR-E4).
   When `PHOENIX_EXPERIMENTS_ENABLED`, the A/B is also registered as a real Phoenix
   experiment so it appears on-product (FR-E5).
10. TraceReplay re-runs the **exact original failing input** on the candidate prompt against
    the live Patient and an LLM judge confirms before→after is actually FIXED (FR-RP1).
11. RedTeam fires the synthesized probes at the live Patient under both prompts and reports
    how many survive the patch (FR-RT1).
12. Patcher never auto-promotes (FR-PA3, NG1). Dashboard streamed every step with deep links
    into the real Phoenix span / dataset / prompt (FR-DB2/4). Loop yields; incident deduped
    by span id (FR-L3). Throughout, Cassandra's own reasoning is traced into `cassandra-meta`.

---

## 4. Phoenix MCP Integration (consumed)

All Phoenix access is funneled through a single wrapper `cassandra/phoenix_mcp.py` (NFR-10)
speaking to the `@arizeai/phoenix-mcp` server. Tool names were reconciled against the live
server (`spike_output/phoenix_mcp_tools.json`).

| MCP tool | Owner sub-agent | Operation |
|----------|-----------------|-----------|
| `list-projects` | Watcher | resolve `patient-prod` |
| `get-spans` | Watcher | new spans since cursor (FR-W2) |
| `add-span-annotations` | Diagnostician / RootCause | write verdict + causal analysis onto the span |
| `add-dataset-examples` | Synthesizer | adversarial dataset (created implicitly on first add) |
| `upsert-prompt` | Patcher | versioned candidate prompt |
| `get-experiment-by-id` | Evaluator | read an experiment back when one exists |

> **Important reconciliation:** the Phoenix MCP surface has **no create/run-experiment
> tool** (only read-side: `get-experiment-by-id`, `list-experiments-for-dataset`,
> `get-dataset-experiments`). So the baseline-vs-candidate evaluation is run **live against
> the agent** in `evaluator.py` (real numbers, never stubbed). For an on-product artifact,
> `cassandra/phoenix_experiments.py` optionally calls the **Phoenix Python client**
> (`phoenix.experiments.run_experiment`) — gated by `PHOENIX_EXPERIMENTS_ENABLED`, fully
> guarded so any failure degrades to a no-op.

---

## 5. The cassandra-mcp Server (published)

Cassandra doesn't only consume the partner MCP — it **publishes its own** (`cassandra/
mcp_server.py`, FastMCP). This turns the meta-agent into a tool any other agent or IDE
(Claude Desktop, Cursor) can call, and is a primary Technological-Implementation
differentiator for MCP-savvy judges.

| Tool | Operation | Phoenix? |
|------|-----------|----------|
| `diagnose` | LLM-as-judge verdict on one agent turn (reuses `Diagnostician.judge`) | no |
| `synthesize_evals` | turn a failure into an adversarial eval set | no |
| `propose_patch` | rewrite a system prompt + unified diff | no |
| `supervise_latest` | run the **full** loop on the latest production trace, writing back to Phoenix | yes |
| `self_evaluate` | grade Cassandra's own diagnostic accuracy vs labeled ground truth | no |

Console entry point `cassandra-mcp` (stdio). The same `Diagnostician.judge`,
`Synthesizer`, `Patcher` code backs both the in-process pipeline and the MCP tools — one
source of truth.

---

## 6. Self-Observability & Self-Improvement (the recursive core)

Two mechanisms make the meta-agent observable *to itself* — the explicit bonus criterion
the Arize track rewards ("agents that use their own observability data to improve").

- **Self-tracing** (`cassandra/instrumentation.py`, `init_self_tracing`): instruments
  Cassandra's own OpenAI/OpenRouter reasoning via OpenInference into a dedicated
  `TracerProvider` and ships spans to the `cassandra-meta` Phoenix project (NFR-3). Scoped
  so it never clobbers the Patient's manual spans; idempotent; degrades to a no-op if
  packages/Phoenix are unavailable. Wired into dashboard startup and `run_pipeline`.
- **Self-evaluation** (`cassandra/selfeval.py` + `cassandra/traps.py`): runs a hand-labeled
  ground-truth trap library through the live Patient and Cassandra's own Diagnostician,
  then scores its verdicts against ground truth → a diagnostic-accuracy `Scorecard`
  (overall + per failure class). Exposed via the dashboard ("Grade my own diagnoses"),
  `POST /selfeval`, and the `self_evaluate` MCP tool.

---

## 7. Deployment Topology

| Component | Hosting | Notes |
|-----------|---------|-------|
| The Patient (C1) | Cloud Run service | HTTP `/chat`; OpenInference exporter → Phoenix; returns tokens + latency |
| Cassandra (C3) | Vertex AI Agent Engine | `build_adk_agent()`; Cloud Run fallback if Agent Engine deploy is flaky (R2) |
| Trace poller | Cloud Function + Scheduler | invokes Cassandra each interval (FR-W1); dashboard also runs an in-process 5s loop for the demo |
| Dashboard (C4) | Cloud Run service | FastAPI + SSE; serves the self-contained `dashboard/ui/index.html` (no build step) |
| Phoenix (C2) | Phoenix Cloud or self-hosted | local self-host currently used in dev (NFR-5) |
| Secrets | Secret Manager | Phoenix API key, model keys, GCP creds (NFR-4) |

State across poller invocations (Watcher cursor FR-W4, dedupe set FR-L3): Firestore, GCS,
or local file (`STATE_BACKEND`), chosen for zero-ops simplicity.

> The dashboard is a single self-contained HTML file — the earlier React/Vite app under
> `web/` is no longer wired in. The Cloud Run image no longer runs a Node build.

---

## 8. Technology Choices & Rationale

| Choice | Why |
|--------|-----|
| Gemini 3 / OpenAI / OpenRouter | Mandatory Gemini path + pragmatic fallbacks; all behind `llm.py` |
| ADK LoopAgent + custom BaseAgent | Mandatory build path; real wiring, logic stays unit-testable |
| Vertex AI Agent Engine | Mandatory-recommended managed runtime |
| Phoenix MCP (consumed) + cassandra-mcp (published) | Genuine partner MCP **and** a published MCP — maximal scored surface |
| Live evaluation (not stubbed) | Phoenix MCP lacks a run-experiment tool; live scoring keeps the numbers honest |
| Self-tracing + self-eval | Directly targets the Arize "self-improvement loop" bonus criterion |
| FastAPI + SSE single-file UI | Smallest reliable path to a live animated feed; no build step to deploy |
| Apache-2.0 | OSI-approved, Devpost-detectable top-level license (NFR-8) |

---

## 9. Session Changelog (2026-06-02)

Built this session, on top of the original 5-stage scaffold (commits `768d9de` → `0204122`):

1. **Phase 1 — credibility:** fixed the broken `run_pipeline.py`; replaced stubbed Phoenix
   "experiments" with real live evaluation; collapsed to one self-contained dashboard.
2. **Phase 2 — depth:** published the custom `cassandra-mcp` server (5 tools); replaced the
   empty `SequentialAgent` placeholder with a real ADK `LoopAgent` + custom `BaseAgent`.
3. **Self-evaluation:** shared ground-truth trap library + `SelfEvaluator` scorecard;
   extracted a pure `Diagnostician.judge()` as the single source of truth.
4. **Self-tracing:** Cassandra's own reasoning → `cassandra-meta` Phoenix project.
5. **On-product experiments:** optional real `phoenix.experiments.run_experiment` (flagged).
6. **Cost/latency + severity:** Patient returns tokens + latency; Evaluator computes an
   `EfficiencyReport`; Diagnostician assigns incident `Severity`.

19 offline tests pass. Remaining for submission: live Vertex Agent Engine run, Cloud Run
deploy + hosted URL, ≤3-min demo video.

---

## 10. Failure Modes & Safeguards

| Failure | Safeguard |
|---------|-----------|
| Phoenix MCP transient error | Single wrapper; poller idempotent via cursor (FR-W4) |
| Cassandra supervising itself | `session_id=="test"` probes filtered by the Watcher (verified live) |
| Diagnostician false positive | Confidence threshold (FR-D3); annotations advisory, never auto-applied (NG1) |
| Duplicate incident each poll | Dedupe by offending span id (FR-L3) |
| Phoenix experiment / self-trace env issues | Both guarded → degrade to no-op, never break the loop |
| Demo flakiness | Deterministic seeder (FR-IS1, NFR-2); replay before/after is the reproducible money shot |
| Agent Engine deploy issues | Cloud Run fallback path documented |
