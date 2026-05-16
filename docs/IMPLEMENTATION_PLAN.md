# Cassandra — Implementation Plan

Solo build, ~25 working days from 2026-05-17 to the 2026-06-11 14:00 PDT deadline.
Ship target: 2026-06-10 (1-day buffer). Requirement IDs reference
[REQUIREMENTS.md](REQUIREMENTS.md).

---

## Timeline Overview

| Phase | Days | Theme | Exit gate |
|-------|------|-------|-----------|
| 0 | D1–2 | Foundations + MCP spike | Phoenix MCP enumerated; repo public w/ LICENSE |
| 1 | D3–5 | The Patient (victim) | Seeded message produces a hallucination span in Phoenix |
| 2 | D6–10 | Watcher + Diagnostician | **Annotation written back into Phoenix UI** |
| 3 | D11–14 | Synthesizer | Phoenix dataset auto-built from a real failure |
| 4 | D15–19 | Evaluator + Patcher | Full loop closes; experiment shows pass-rate lift |
| 5 | D20–22 | Dashboard + deploy | Live feed on Cloud Run; Cassandra on Agent Engine |
| 6 | D23–25 | Video + submission | Devpost submitted with buffer |

**Hard checkpoint — end of D10:** annotation write-back must work. It is the technical
crux *and* the opening shot of the video. If it slips, cut Synthesizer scope (FR-S);
never cut this.

---

## Phase 0 — Foundations (D1–2)

- [ ] GCP project; enable Vertex AI, Cloud Run, Cloud Functions, Cloud Scheduler,
      Secret Manager, Firestore. Confirm **Gemini 3 access in target region** (R2).
- [ ] Create free **Phoenix Cloud** space; API key → Secret Manager (NFR-4).
- [ ] **MCP enumeration spike (R1):** throwaway script connects to `@arizeai/phoenix-mcp`,
      lists every tool, dumps exact names + arg schemas. Reconcile against
      ARCHITECTURE.md §4 table. *This gate de-risks the entire build.*
- [ ] Init repo: structure below, `pyproject.toml`, **Apache-2.0 `LICENSE` at root**
      (NFR-8 — do this Day 1, not Day 25), `.env.example`, README stub. Push **public**.

Exit: Phoenix MCP surface known and documented; repo public + licensed.

## Phase 1 — The Patient (D3–5)

- [ ] ADK + Gemini 3 e-commerce support agent (FR-P1).
- [ ] `lookup_order`, `get_refund_policy` tools, intentionally flaky (FR-P2).
- [ ] Fragile system prompt that hallucinates on missing policy (FR-P3).
- [ ] OpenInference instrumentation → Phoenix `patient-prod` (FR-P4).
- [ ] Incident Seeder script — deterministic failing message (FR-IS1) + 20-case labeled
      trap library (FR-IS2).

Exit: running the seeder reliably yields a hallucination span visible in Phoenix.

## Phase 2 — Watcher + Diagnostician (D6–10)  ← crux phase

- [ ] `phoenix_mcp.py` wrapper (NFR-10) over the spiked tool surface.
- [ ] Cloud Function + Scheduler trigger, ≤60s (FR-W1).
- [ ] Watcher: query spans since cursor, durable cursor in Firestore (FR-W2/3/4).
- [ ] Diagnostician: Gemini-3 LLM-as-judge → class + rationale + confidence (FR-D1/2).
- [ ] **Write Phoenix span annotation via MCP** (FR-D3) — verify it renders in Phoenix UI.
- [ ] Emit `Incident` object (FR-D4).
- [ ] Unit test: classification ≥90% on 20-case trap set (AC-8).

Exit (hard checkpoint): seeded failure → annotated Phoenix span < 10s (AC-1).

## Phase 3 — Synthesizer (D11–14)

- [ ] Gemini-3 generates 12 diverse adversarial variants + expected answers (FR-S1/3).
- [ ] Create Phoenix dataset via MCP (FR-S2).
- [ ] Unit test: output schema + diversity heuristic (FR-S3).

Exit: a real failing trace becomes a populated Phoenix dataset automatically (AC-2).

## Phase 4 — Evaluator + Patcher (D15–19)

- [ ] Evaluator: Phoenix experiment, baseline run, LLM-as-judge scoring (FR-E1/2).
- [ ] Patcher: Gemini-3 hardened prompt (FR-PA1); register Phoenix prompt version
      (FR-PA2).
- [ ] Evaluator: candidate run; compute baseline/candidate/delta (FR-E3/4).
- [ ] Patcher: queue A/B, **no auto-promote** (FR-PA3, NG1); emit prompt diff (FR-PA4).
- [ ] LoopAgent wiring: one incident/cycle, dedupe by span id (FR-L1/3).

Exit: end-to-end loop closes; experiment shows clear lift (AC-3/4); ≥5 MCP families
exercised (AC-6).

## Phase 5 — Dashboard + Deploy (D20–22)

- [ ] FastAPI + SSE dashboard; live append-only feed (FR-DB1).
- [ ] Per-incident panel: exchange → verdict → annotated-span link → dataset → experiment
      bars → prompt diff (FR-DB2).
- [ ] "Send customer message" box (FR-DB3); Phoenix deep links (FR-DB4); striking first
      10s animation (FR-DB5).
- [ ] Deploy Patient + Dashboard to Cloud Run; Cassandra to Agent Engine (Cloud Run
      fallback ready, R2). Self-observability to `cassandra-meta` (NFR-3).
- [ ] BigQuery span sink — **only if ahead of schedule** (stretch, NG/PRD §6).

Exit: public hosted URL reachable; full loop demoable live.

## Phase 6 — Video + Submission (D23–25)

- [ ] Rehearse demo against latency budget (NFR-1); record pre-emptive fallback clip
      (R3 insurance).
- [ ] Record + edit ≤3:00 video per [DEMO_SCRIPT.md](DEMO_SCRIPT.md).
- [ ] README polish; architecture diagram; run instructions (NFR-7).
- [ ] Submission checklist (AC-7): public repo ✓, top-level Apache-2.0 LICENSE detectable
      ✓, hosted URL ✓, ≤3-min video ✓, Devpost form ✓, **Arize track selected** ✓.
- [ ] Submit by **D25 / 2026-06-10**, ≥1 day before the 06-11 14:00 PDT deadline.

---

## Repository Layout

```
cassandra/
├── README.md
├── LICENSE                     # Apache-2.0, root, Devpost-detectable (NFR-8)
├── pyproject.toml
├── .env.example
├── docs/                       # this documentation set
├── patient/                    # C1 — the victim
│   ├── agent.py  tools.py  instrumentation.py
├── cassandra/                  # C3 — the meta-agent
│   ├── loop_agent.py  watcher.py  diagnostician.py
│   ├── synthesizer.py  evaluator.py  patcher.py
│   └── phoenix_mcp.py          # single MCP wrapper (NFR-10)
├── dashboard/                  # C4
│   ├── main.py  ui/
├── functions/trace_poller/     # FR-W1 scheduled function
├── deploy/                     # agent_engine.py, cloudrun.Dockerfile, cloudbuild.yaml
├── scripts/seed_incident.py    # C5 (FR-IS*)
└── tests/
```

---

## Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| R1 | Phoenix MCP surface differs from assumptions | Med | High | Day-1 enumeration spike before any feature code; all access behind `phoenix_mcp.py` |
| R2 | Gemini 3 / Agent Engine quota or availability | Med | High | Confirm region + quota Day 1; Cloud Run fallback for Cassandra |
| R3 | Failure not reproducible on camera | Med | High | Deterministic seeder (FR-IS1, NFR-2); pre-recorded fallback clip |
| R4 | Scope creep (BigQuery, A2A, multi-tenant) | High | Med | PRD Non-Goals are binding; stretch only if ahead at D20 |
| R5 | D10 crux slips | Med | High | Reserve D9–10 as pure buffer for the annotation path; cut Synthesizer before cutting crux |
| R6 | Submission mechanics missed last-minute | Low | High | LICENSE + public repo on Day 1; checklist run at D24, submit D25 |

---

## Cut-Down Ladder (if behind)

Drop in this order; never violate the line below it:

1. BigQuery analytics (stretch) — already optional.
2. Self-observability to `cassandra-meta` (NFR-3) — nice flourish, not core.
3. 20-case precision metric automation — demo on the seeded case only.
4. Synthesizer diversity polish (FR-S3) — fewer/simpler variants still tells the story.

**Never cut below here:** Patient hallucinates → Cassandra annotates Phoenix span →
synthesizes a dataset → experiment shows a lift → versioned candidate prompt. That five-
beat chain *is* the submission. Without it there is no demo.

---

## Day-1 Action List

1. Create + configure GCP project; confirm Gemini 3 + Agent Engine in region.
2. Create Phoenix Cloud space; key → Secret Manager.
3. Run the Phoenix MCP enumeration spike; commit the recorded tool schema.
4. `git init`, push public, add Apache-2.0 LICENSE at root, scaffold the tree above.
