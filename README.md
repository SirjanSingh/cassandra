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

## Status

Greenfield. Day-0 documentation set. See the implementation plan for the build timeline.

## License

Apache-2.0 — see [LICENSE](LICENSE).
