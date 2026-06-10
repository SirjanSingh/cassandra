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
| [docs/PITCH.md](docs/PITCH.md) | The pitch — narrative for the website, Devpost page, and demo video |
| [docs/WORKFLOWS.md](docs/WORKFLOWS.md) | How to actually use Cassandra: IDE copilot, CI prompt gate, live supervision, postmortems |
| [docs/PRD.md](docs/PRD.md) | Product Requirements Document — vision, users, scope, success metrics |
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | Detailed functional & non-functional requirements |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System & agent architecture, data flow, MCP surface |
| [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) | Plain-language design, every workflow narrated, flaws table, security audit, simplifications |
| [docs/sessions/](docs/sessions/) | Per-session change log — the project's durable working memory |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | 25-day solo build plan with checkpoints |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | Shot-by-shot ≤3-minute video script |
| [docs/WINNING_STRATEGY.md](docs/WINNING_STRATEGY.md) | Competitive read & judging-criteria mapping |

## Tech Stack

- **Reasoning core:** Gemini 3 (or direct OpenAI `gpt-4o-mini` / `gpt-4o` integration)
- **Orchestration:** Google Cloud Agent Builder (the officially named build path) —
  ADK `LoopAgent` wrapping a real custom `BaseAgent` supervision cycle (google-adk 2.1.0)
- **Runtime:** Vertex AI Agent Engine
- **Partner MCP (required):** Arize Phoenix MCP server (`@arizeai/phoenix-mcp`) — consumed
- **Published MCP:** a custom `cassandra-mcp` server that exposes Cassandra's supervision as
  callable tools for any agent/IDE (see [Cassandra as an MCP server](#cassandra-as-an-mcp-server))
- **Scheduling:** Cloud Functions (trace poller)
- **UI / hosting:** Cloud Run (dashboard)
- **Secrets:** Secret Manager
- **Optional:** BigQuery (long-term span analytics)

## Cassandra as an MCP server

Cassandra doesn't just *consume* the partner Phoenix MCP — it *publishes its own*. The
`cassandra-mcp` server (`cassandra/mcp_server.py`, built on the MCP Python SDK) exposes the
meta-agent's supervision as tools any other agent or IDE (Claude Desktop, Cursor, …) can call:

| Tool | What it does | Phoenix? |
|------|--------------|----------|
| `diagnose(customer_input, agent_output, tool_calls?)` | LLM-as-judge verdict (hallucination / prompt-drift / tool-failure) | no |
| `synthesize_evals(failure_class, why_it_failed, original_input, bad_output, n?)` | turn one failure into an adversarial eval set | no |
| `propose_patch(current_prompt, failure_summary, triggering_input, bad_output)` | rewrite a system prompt to close the failure + unified diff | no |
| `gate_prompt(prompt, cases, threshold?)` | CI regression gate: score a prompt against eval cases on the live agent; `passed=false` means block the change | no |
| `supervise_latest()` | run the **full** loop on the latest production trace: diagnose → root-cause → synthesize → evaluate → patch → replay → red-team, writing annotations/datasets/prompt versions back into Phoenix — and return a paste-ready markdown **postmortem** | yes |
| `self_evaluate()` | grade Cassandra's **own** diagnostic accuracy against a labeled ground-truth set (introspection / self-improvement) | no |

**Concrete use cases** (full recipes in [docs/WORKFLOWS.md](docs/WORKFLOWS.md)):

- *While building an agent* — ask your IDE assistant: "diagnose this turn", "synthesize 10
  evals for this failure", "propose a patch and show the diff". Zero infrastructure.
- *In CI* — "gate my new prompt against `evals/cases.json` at 80%", or run the same check
  headless with the `cassandra-gate` CLI (see below).
- *On call* — "supervise the latest production trace": one tool call runs the entire loop
  and hands back a postmortem ready to file as a GitHub issue.

Run it (stdio):

```bash
pip install -e .
cassandra-mcp                 # or: python -m cassandra.mcp_server
```

Register it in Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "cassandra": {
      "command": "cassandra-mcp",
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "PHOENIX_BASE_URL": "http://localhost:6006",
        "PHOENIX_API_KEY": "local",
        "PATIENT_ENDPOINT": "http://localhost:8082/chat"
      }
    }
  }
}
```

Now any Claude/Cursor session can say *"diagnose this agent turn"* or *"supervise my latest
production trace"* and Cassandra answers — the meta-agent, distributed.

## CI prompt regression gate (`cassandra-gate`)

Prompts are code, so test them like code. `cassandra-gate` scores a system prompt against
an eval dataset by running every case through your live agent and judging each answer,
then **fails the build** when the pass rate drops below the threshold:

```bash
cassandra-gate --prompt-file prompts/system_prompt.txt \
               --cases evals/cases.json --threshold 0.8
```

The dataset format is exactly what Cassandra's Synthesizer emits, so every production
incident Cassandra handles can be committed as a regression suite that guards all future
prompt changes — failures compound into protection. Ready-to-copy GitHub Actions workflow:
[`examples/github-actions-prompt-gate.yml`](examples/github-actions-prompt-gate.yml).

## Auto-postmortems

Every completed supervision cycle writes `reports/<incident_id>.md` — a paste-ready
postmortem with the diagnosis, severity, root-cause chain, baseline-vs-candidate pass
rates, the prompt diff, before/after replay evidence, and the red-team table. File it as
a GitHub issue (`gh issue create --body-file reports/inc-<id>.md`), drop it in Slack, or
attach it to the PR that applies the patch. The `supervise_latest` MCP tool returns the
same markdown in its `postmortem` field.

## Self-evaluation (introspection loop)

The Arize track awards bonus points to agents that *"use their own observability data to
improve over time."* Cassandra closes that loop on itself two ways:

- **Self-tracing** (`cassandra/instrumentation.py`): Cassandra's own LLM reasoning is
  instrumented with OpenInference and shipped to the **`cassandra-meta`** Phoenix project —
  so the meta-agent is as observable as the agents it supervises.
- **Self-evaluation** (`cassandra/selfeval.py`): it runs a hand-labeled ground-truth trap
  library (`cassandra/traps.py`) through the live Patient and its own Diagnostician, then
  **scores its own verdicts against ground truth** — a diagnostic-accuracy scorecard
  (overall + per failure class). Run it from the dashboard ("Grade my own diagnoses"), the
  `POST /selfeval` endpoint, or the `self_evaluate` MCP tool.

The watcher, watching itself. Each incident also carries a **severity** (failure class ×
confidence) and a **cost/latency delta** of the candidate prompt vs the baseline, and — when
`PHOENIX_EXPERIMENTS_ENABLED=true` — the A/B is also registered as a real Phoenix experiment.

## Repository Layout

```
cassandra/
├── patient/              # C1 — the fragile "ShopBot" victim agent
│   ├── agent.py          #   Gemini-3 / OpenAI agent + FastAPI /chat + OpenInference spans
│   ├── tools.py          #   intentionally flaky get_refund_policy / lookup_order
│   └── instrumentation.py#   OTLP exporter → Phoenix patient-prod
├── cassandra/            # C3 — the meta-agent (8-stage pipeline)
│   ├── models.py         #   Incident (threaded through), Verdict, Severity, Scorecard, …
│   ├── phoenix_mcp.py    #   the single Phoenix MCP gateway (NFR-10)
│   ├── llm.py            #   Gemini 3 / OpenAI / OpenRouter structured/text helper
│   ├── watcher.py        #   FR-W: poll spans since durable cursor (skips session=test)
│   ├── diagnostician.py  #   FR-D: LLM-as-judge → annotate Phoenix span + severity
│   ├── rootcause.py      #   FR-RC: culprit + causal chain + fix strategy
│   ├── synthesizer.py    #   FR-S: adversarial dataset → Phoenix dataset
│   ├── evaluator.py      #   FR-E: live baseline vs candidate scoring + efficiency
│   ├── patcher.py        #   FR-PA: prompt patch → Phoenix prompt version + diff
│   ├── replay.py         #   FR-RP: re-run the original failing input on the patch
│   ├── redteam.py        #   FR-RT: adversarial probes at the live agent
│   ├── selfeval.py       #   FR-SE: grade its own diagnoses vs traps.py ground truth
│   ├── traps.py          #   shared hand-labeled ground-truth trap library
│   ├── instrumentation.py#   self-tracing into cassandra-meta (OpenInference)
│   ├── phoenix_experiments.py # optional on-product Phoenix experiments (flagged)
│   ├── loop_agent.py     #   pipeline + real ADK LoopAgent/BaseAgent shell
│   ├── mcp_server.py     #   cassandra-mcp: publishes supervision as MCP tools (6)
│   ├── gate.py           #   cassandra-gate: CI prompt regression gate (CLI + MCP)
│   ├── report.py         #   auto-postmortem renderer (reports/<incident_id>.md)
│   ├── state.py          #   durable cursor + dedupe (Firestore/local)
│   └── events.py         #   in-process bus → dashboard SSE
├── dashboard/            # C4 — FastAPI: serves ui/index.html + SSE /events + /ask + /selfeval
│   └── ui/index.html     #   self-contained OLED cockpit (no build step)
├── web/                  # legacy React/Vite cockpit — no longer wired in
├── scripts/
│   ├── run_pipeline.py   #   runs one complete end-to-end supervision cycle locally
│   ├── seed_incident.py  #   C5 — deterministic demo trap + labeled set
│   └── spike_enumerate_mcp.py  # Day-1 Phoenix MCP enumeration (de-risk R1)
├── deploy/               # cloudrun.Dockerfile, cloudbuild.yaml, agent_engine.py
├── tests/                # offline unit tests (LLM + MCP mocked)
└── docs/                 # PRD, requirements, architecture, plan, demo, strategy
```

## Run Locally

```bash
pip install -e ".[dev]"
cp .env.example .env            # Fill in OpenAI/Gemini API keys + Phoenix URLs
                                # (public deploys must also set REPLAY_SHARED_SECRET
                                #  on BOTH services; see deploy/cloudbuild.yaml)

# 1. Start the Patient Agent (ShopBot)
uvicorn patient.agent:app --port 8082 --reload

# 2. Start the FastAPI Dashboard (cockpit at http://localhost:8085, animated explainer at /how)
uvicorn dashboard.main:app --port 8085 --reload

# 3. Drive one supervision cycle (seed an incident, poll, diagnose, patch, replay, red-team)
python scripts/run_pipeline.py

# Run offline unit tests
pytest
```

> The cockpit is a single self-contained file (`dashboard/ui/index.html`) served directly by
> the dashboard — no Node/Vite build step. The legacy `web/` React app is no longer wired in.

## Status

**Codebase complete and fully verified.**
All modules byte-compile and live end-to-end integration runs succeed.

| Area | State |
|------|-------|
| Docs (PRD → strategy) | ✅ complete, reconciled with official Devpost page |
| Patient + incident seeder (C1/C5) | ✅ code complete and verified live |
| Cassandra 8-stage pipeline (C3) | ✅ diagnose→root-cause→synthesize→eval→patch→replay→red-team |
| Evaluation | ✅ real baseline-vs-candidate scoring (no stubbed experiments) |
| Dashboard (C4) | ✅ single self-contained cockpit (no build step) — SSE + UI |
| Custom `cassandra-mcp` server | ✅ 6 tools (incl. gate_prompt + self_evaluate), registered + unit-tested |
| CI prompt regression gate | ✅ `cassandra-gate` CLI + `gate_prompt` MCP tool + GitHub Actions example |
| Auto-postmortems | ✅ every cycle writes `reports/<incident_id>.md`; returned by `supervise_latest` |
| Self-evaluation scorecard | ✅ grades its own diagnostic accuracy vs labeled ground truth — **100%** (11/11) on OpenAI |
| Animated explainer page | ✅ self-contained `/how` — every workflow + MCP call I/O, no build step |
| `system_override` hardening | ✅ sandboxed `session_id="test"` path + `REPLAY_SHARED_SECRET` token gate for public deploys (unit + live tested) |
| Self-tracing | ✅ Cassandra's own reasoning traced into the `cassandra-meta` Phoenix project |
| Cost/latency + severity | ✅ candidate-vs-baseline efficiency delta + incident severity |
| Real Phoenix experiments | ✅ optional on-product A/B (`PHOENIX_EXPERIMENTS_ENABLED`, needs live Phoenix) |
| ADK orchestration shell | ✅ real `LoopAgent`+`BaseAgent`, builds against google-adk 2.1.0 |
| Deploy manifests (Cloud Run / Agent Engine) | ✅ written |
| Phoenix MCP surface | ✅ fully integrated and verified via live `@arizeai/phoenix-mcp` |
| Live end-to-end run on Phoenix | ✅ verified live (both Gemini and OpenAI backends) |
| Feedback loop protection | ✅ verified live (test session filtering prevents infinite loops) |
| Tests | ✅ 23 passing (offline; LLM + MCP mocked) |
| Vertex Agent Engine run (needs your GCP creds) | ⛔ pending |
| Hosted URL + demo video | ⛔ pending |

## License

Apache-2.0 — see [LICENSE](LICENSE).
