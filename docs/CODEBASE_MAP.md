# Codebase Map — Cassandra

_Generated 2026-07-20 @ 22e5562 — regenerate when stale (see the codebase-map skill)._

## What this is
Cassandra is a **meta-agent that supervises other LLM agents** through Arize Phoenix
observability. It polls Phoenix traces of a production agent ("the Patient"), diagnoses failures
(hallucination / prompt-drift / tool-failure), synthesizes adversarial evals, scores
baseline-vs-candidate prompts live, proposes a hardened prompt patch, replays the failing input,
and red-teams the fix — writing annotations/datasets/prompt-versions back into Phoenix. Google
Cloud Rapid Agent Hackathon entry (Arize track).

## Stack
- Language / runtime: **Python ≥ 3.11** (hatchling build; packages: `patient`, `cassandra`, `dashboard`)
- Backend framework: **FastAPI + uvicorn**, SSE via `sse-starlette`
- Frontend: **React 18 + Vite + TypeScript + Tailwind** (`web/`), plus a no-build single-file cockpit
- Agent runtime: **google-adk** (thin `LoopAgent` envelope); MCP via `mcp` client
- LLM: **Vertex Gemini `gemini-2.5-flash-lite`** in the hosted demo (OpenAI/OpenRouter fallbacks in `llm.py`)
- Infra: Phoenix MCP (observability), Firestore/GCS/local for state, Cloud Run + Vertex Agent Engine

## Commands
| Purpose | Command |
|---------|---------|
| Install | `pip install -e ".[dev]"` then `cp .env.example .env` |
| Run (3 procs) | `uvicorn patient.agent:app --port 8082 --reload` · `uvicorn dashboard.main:app --port 8085 --reload` · `python scripts/run_pipeline.py` |
| Frontend dev | `cd web && npm run dev` (build: `npm run build`) |
| Test | `pytest` (offline; LLM+MCP mocked) — one file: `pytest tests/test_diagnostician.py` |
| Lint / typecheck | `ruff check .` · `mypy cassandra patient dashboard` |
| MCP server | `cassandra-mcp` (stdio) · CI gate: `cassandra-gate` |
| Deploy | `deploy/cloudbuild.yaml` + `deploy/cloudrun.Dockerfile` / `deploy/agent_engine.py` |

## Entry points
- `patient/agent.py` (`app`) — the fragile victim agent "ShopBot"; FastAPI `/chat`. Run on :8082.
- `dashboard/main.py` (`app`) — dashboard + SSE cockpit; also runs a 5s in-process supervision loop. :8085.
- `scripts/run_pipeline.py` — drives ONE full end-to-end supervision cycle.
- `cassandra/loop_agent.py` (`SupervisionPipeline.run_once`) — the 8-stage pipeline core.
- `cassandra/mcp_server.py` (`main` → `cassandra-mcp`) — published MCP server, reuses pipeline stages.
- `cassandra/gate.py` (`main` → `cassandra-gate`) — CI prompt-regression gate.

## Directory map

> **Canonical structure lives in `CLAUDE.md` → "Repository structure"** (module-level, kept
> current every session). This section is the directory-level summary; if the two disagree,
> CLAUDE.md wins — and fix the drift.

- `cassandra/` — the meta-agent; one module per pipeline stage (see flow below) + `config.py`, `llm.py`, `models.py`, `phoenix_mcp.py` gateway.
- `patient/` — the supervised demo agent (ShopBot): `agent.py`, intentionally flaky `tools.py`, `instrumentation.py`.
- `dashboard/` — FastAPI dashboard + SSE; `ui/index.html` is the self-contained `/cockpit` fallback.
- `web/` — primary React/Vite frontend (edit `web/src/**`); built by Dockerfile `webbuild` stage, served at `/`.
- `scripts/` — one-shot drivers (`run_pipeline`, `seed_incident`, MCP spike).
- `deploy/` — Cloud Run Dockerfile, cloudbuild, Vertex Agent Engine entry, VM startup.
- `docs/` — deep design refs: `SYSTEM_DESIGN.md`, `ARCHITECTURE.md`, `PRD.md`, `REQUIREMENTS.md` (FR/NFR IDs), `WORKFLOWS.md`, `sessions/` (per-session notes — read newest first).
- `tests/` — offline pytest suite (LLM + MCP mocked). `examples/` — third-party agent adapter template.

## Primary flow
One `Incident` object threads through and is enriched in place at each stage:
`Watcher → Diagnostician → RootCauseAnalyst → Synthesizer → Evaluator(baseline) → Patcher → Evaluator(candidate) → TraceReplay → RedTeam`
One incident per cycle, deduped by span id. Live probes to the supervised agent go through
`cassandra/patient_client.py:ask_patient()`.

## Gotchas & risky files
- **`.env`/settings changes need a server restart** — `get_settings()` is cached (`reload_settings()` for tests).
- **All Phoenix MCP access goes through `cassandra/phoenix_mcp.py`** (NFR-10). No live create/run-experiment tool → eval runs live in `evaluator.py`, not as a Phoenix experiment.
- **All env via `config.py:get_settings()`; all LLM via `llm.py`** (`structured()`/`text()`) — never read `os.environ` or call SDKs directly.
- **Vertex Gemini traps:** hold the genai client in a local across `await` (bare temporary is GC'd → "client closed"); use flash-lite (flash was DSQ-exhausted); location must be a real region, never `global`.
- **Feedback-loop safety:** Cassandra probes with `session_id="test"` and the `Watcher` filters those out — don't remove the filter or it self-supervises infinitely.
- **Never import from `patient/` inside `cassandra/`** — the pipeline is agent-agnostic; baseline resolved by `cassandra/baseline.py`.
- `REPLAY_SHARED_SECRET` must be set on **both** services or replay/eval/red-team silently lose the `system_override`.

## Where to learn more
- `CLAUDE.md` (root) — conventions + session protocol. `docs/SYSTEM_DESIGN.md` — deep architecture.
- `docs/sessions/` — newest note = last session's changes/open items. `docs/REQUIREMENTS.md` — FR-*/NFR- IDs.
