# Cassandra — The Meta-Agent That Watches Other Agents

> An AI agent that babysits other AI agents. Cassandra watches production agents through
> Arize Phoenix traces, catches hallucinations, prompt drift, and tool-call failures in
> real time, auto-synthesizes evaluation datasets from the failing traces, runs
> LLM-as-judge evaluations, and proposes A/B-ready prompt patches — all from inside Phoenix.

**Hackathon:** Google Cloud Rapid Agent Hackathon — *Building Agents for Real-World Challenges*
**Partner track:** Arize (Phoenix — LLM observability & evaluation)
**Submission deadline:** 2026-06-12 02:30 IST (= 2026-06-11 14:00 PDT) · internal ship target 2026-06-11
**Verified against the official Devpost page on 2026-05-17** (6,582 participants, $60k total)

---

## The Problem

Every team running LLM agents in production has the same unsolved problem: **agents fail
silently.** A customer-facing agent confidently invents a refund policy. A prompt drifts
after a model upgrade. A tool call fails and the agent hallucinates around the gap.

Today this is caught by **humans staring at dashboards**, sampling traces by hand, writing
eval datasets manually, and editing prompts on intuition. It does not scale, it is slow,
and most failures are never caught at all.

## The Idea

Cassandra closes that loop autonomously. It is, recursively, **an agent whose job is to
supervise other agents.** It runs the exact workflow Phoenix was built for — but
automated, continuous, and self-improving:

```
 monitor ─▶ diagnose ─▶ synthesize evals ─▶ run experiment ─▶ propose patch ─▶ (loop)
```

## Why This Wins the Arize Bucket

- **Quality of the Idea (25%)** — A beautifully recursive concept: an agent that audits
  agents. Almost every other entry will *be* an agent; almost none will be an agent
  *about* agents. Memorable and original.
- **Technological Implementation (25%)** — Exercises nearly the entire Phoenix MCP tool
  surface: traces, spans, annotations, datasets, experiments, prompt management. Arize
  judges are Phoenix engineers; this is non-trivial, deep, on-product usage.
- **Potential Impact (25%)** — Every production LLM team has this exact pain and currently
  solves it with eyeballs.
- **Design (25%)** — A live dashboard where a failure is caught, annotated, turned into a
  dataset, and patched — visibly, in seconds, on camera.

See [docs/WINNING_STRATEGY.md](docs/WINNING_STRATEGY.md) for the full judging-criteria map.

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/PRD.md](docs/PRD.md) | Product Requirements Document — vision, users, scope, success metrics |
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | Detailed functional & non-functional requirements |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System & agent architecture, data flow, MCP surface |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | 25-day solo build plan with checkpoints |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | Shot-by-shot ≤3-minute video script |
| [docs/WINNING_STRATEGY.md](docs/WINNING_STRATEGY.md) | Competitive read & judging-criteria mapping |

## Tech Stack

- **Reasoning core:** Gemini 3
- **Orchestration:** Google Cloud Agent Builder (the officially named build path) —
  `LoopAgent` + `SequentialAgent` via ADK/Agent Engine as the underlying runtime
- **Runtime:** Vertex AI Agent Engine
- **Partner MCP (required):** Arize Phoenix MCP server (`@arizeai/phoenix-mcp`)
- **Scheduling:** Cloud Functions (trace poller)
- **UI / hosting:** Cloud Run (dashboard)
- **Secrets:** Secret Manager
- **Optional:** BigQuery (long-term span analytics)

## Repository Layout

```
cassandra/
├── patient/              # C1 — the fragile "ShopBot" victim agent
│   ├── agent.py          #   Gemini-3 agent + FastAPI /chat + OpenInference spans
│   ├── tools.py          #   intentionally flaky get_refund_policy / lookup_order
│   └── instrumentation.py#   OTLP exporter → Phoenix patient-prod
├── cassandra/            # C3 — the meta-agent
│   ├── models.py         #   Incident object threaded through the pipeline
│   ├── phoenix_mcp.py    #   the single Phoenix MCP gateway (NFR-10)
│   ├── llm.py            #   Gemini 3 structured/text helper
│   ├── watcher.py        #   FR-W: poll spans since durable cursor
│   ├── diagnostician.py  #   FR-D: LLM-as-judge → annotate Phoenix span
│   ├── synthesizer.py    #   FR-S: adversarial dataset → Phoenix dataset
│   ├── evaluator.py      #   FR-E: baseline vs candidate Phoenix experiment
│   ├── patcher.py        #   FR-PA: prompt patch → Phoenix prompt version
│   ├── loop_agent.py     #   pipeline + thin ADK LoopAgent shell
│   ├── state.py          #   durable cursor + dedupe (Firestore/local)
│   └── events.py         #   in-process bus → dashboard SSE
├── dashboard/            # C4 — Cloud Run SSE dashboard + live UI
├── functions/trace_poller/  # scheduled Cloud Function (drives one cycle)
├── scripts/
│   ├── seed_incident.py  #   C5 — deterministic demo trap + labeled set
│   └── spike_enumerate_mcp.py  # Day-1 Phoenix MCP enumeration (de-risk R1)
├── deploy/               # cloudrun.Dockerfile, cloudbuild.yaml, agent_engine.py
├── tests/                # offline unit tests (LLM + MCP mocked)
└── docs/                 # PRD, requirements, architecture, plan, demo, strategy
```

## Run Locally

```bash
pip install -e ".[dev]"
cp .env.example .env            # fill GCP project + Phoenix key

# 0. (once) confirm the live Phoenix MCP tool surface, then reconcile phoenix_mcp.py
python -m scripts.spike_enumerate_mcp

# 1. the Patient
uvicorn patient.agent:app --port 8081
# 2. the dashboard
uvicorn dashboard.main:app --port 8080      # open http://localhost:8080
# 3. drive one supervision cycle
python -m scripts.seed_incident             # make the Patient hallucinate
python -c "import asyncio;from cassandra.loop_agent import SupervisionPipeline;\
asyncio.run(SupervisionPipeline().run_once())"

pytest                                       # offline unit tests
```

## Status

**Codebase scaffolded and committed** (public: https://github.com/SirjanSingh/cassandra).
All modules byte-compile; offline unit tests cover the MCP helpers, models/state, and the
Diagnostician decision boundary.

| Area | State |
|------|-------|
| Docs (PRD → strategy) | ✅ complete, reconciled with official Devpost page |
| Patient + incident seeder (C1/C5) | ✅ code complete — not yet run live |
| Cassandra 5 sub-agents + loop (C3) | ✅ code complete — logic unit-tested offline |
| Dashboard (C4) | ✅ code complete — SSE + UI |
| Deploy manifests (Cloud Run / Agent Engine) | ✅ written — not yet deployed |
| Phoenix MCP surface | ⚠️ assumed; `# SPIKE-RECONCILE` markers pending Day-1 spike |
| Live end-to-end run on Phoenix Cloud | ⛔ blocked on GCP/Phoenix credentials |
| Hosted URL + demo video (submission items) | ⛔ pending |

Anything touching the live Phoenix MCP or exact ADK/Vertex APIs is written against the
documented surface and marked `# SPIKE-RECONCILE`; the enumeration spike confirms real
tool names before Phase-2 feature work. See [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)
for the full timeline.

## License

Apache-2.0 — see [LICENSE](LICENSE).
