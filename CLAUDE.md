# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session Protocol (READ FIRST — keep the project's memory rich)

This repo keeps a durable, written memory so every session starts with full context. **You
must maintain it** — it is not optional:

1. **At the start of a session**, skim the newest file in [`docs/sessions/`](docs/sessions/)
   (and this file). That is where the last session recorded what changed, why, and what's
   still open. `docs/SYSTEM_DESIGN.md` is the deep architecture + workflow reference.
2. **After each successful, behavior-changing task**, update the running session note
   `docs/sessions/<YYYY-MM-DD>-<topic>.md` (create it on the first such task of the session):
   what changed, why (the decision, not just the diff), files touched, and how you verified it.
   Trivial/no-op turns don't need an entry.
3. **At session end**, make sure that session note is complete (scope, changes, verification,
   open items) and update any docs whose *behavior* changed — `README.md`, `docs/ARCHITECTURE.md`,
   `docs/SYSTEM_DESIGN.md` — plus the auto-memory `MEMORY.md` index when something durable was learned.
4. **`.env` / settings changes don't take effect until the servers restart** — `get_settings()`
   is cached (`reload_settings()` exists for scripts/tests). Note this whenever you touch config.

A `Stop` hook in `.claude/settings.local.json` prints a reminder of this protocol; the protocol
itself lives here.

## What this is

Cassandra is a **meta-agent that supervises other LLM agents** through Arize Phoenix
observability. It polls Phoenix traces of a production agent ("the Patient"), diagnoses
failures (hallucination / prompt-drift / tool-failure) with an LLM-as-judge, synthesizes
adversarial eval datasets from the failure, scores baseline-vs-candidate prompts live,
proposes a hardened prompt patch, replays the original failing input, and red-teams the
fix — writing annotations/datasets/prompt-versions back into Phoenix. It is a Google Cloud
Rapid Agent Hackathon entry (Arize track). Deep design context lives in `docs/` (PRD,
REQUIREMENTS with FR-*/NFR- IDs, ARCHITECTURE).

## Commands

```bash
pip install -e ".[dev]"          # install package + dev deps (pytest, ruff, mypy)
cp .env.example .env             # then fill in keys / Phoenix URLs

pytest                           # all offline tests (LLM + MCP mocked; no live services needed)
pytest tests/test_diagnostician.py            # one file
pytest tests/test_diagnostician.py::test_name # one test
ruff check .                     # lint (line-length 100, py311)
mypy cassandra patient dashboard # type-check

# Run the system locally (three processes):
uvicorn patient.agent:app --port 8082 --reload      # 1. the Patient (ShopBot) — exposes /chat
uvicorn dashboard.main:app --port 8085 --reload     # 2. dashboard + SSE cockpit (also runs a 5s in-process supervision loop)
python scripts/run_pipeline.py                      # 3. drive ONE full end-to-end supervision cycle

cassandra-mcp                    # run Cassandra's own published MCP server over stdio
```

Note: `.env.example`, `cassandra/config.py` defaults, and the documented run ports all
agree now (dashboard 8085, patient 8082). `REPLAY_SHARED_SECRET` gates the Patient's
`system_override` on public deploys (set it on both services or replay/eval/red-team 
silently lose the override). **Frontend (as of 2026-06-11): the `web/` React/Vite app is
the primary UI**, built by the Dockerfile `webbuild` stage and served at `/`;
`dashboard/main.py` mounts the self-contained `dashboard/ui/index.html` at `/cockpit` (and
as the fallback when `web/dist` is absent — e.g. `pytest`/local runs with no `npm build`).
Edit `web/src/**` for the deployed frontend; the single-file cockpit is the no-build
fallback. SSE/`/ask`/`/selfeval` contracts are shared by both.

## Architecture

Two **separate** agents that communicate *only* through Phoenix telemetry:

- **`patient/`** — the fragile victim agent ("ShopBot"). FastAPI `/chat`, intentionally
  flaky tools (`patient/tools.py`), exports OpenInference spans to Phoenix `patient-prod`.
  `patient.agent.FRAGILE_SYSTEM_PROMPT` is the demo baseline prompt Cassandra improves
  (for non-demo agents the baseline comes from `cassandra/baseline.py`'s resolver chain).
- **`cassandra/`** — the meta-agent. The pipeline is an 8-stage cycle in
  `loop_agent.py:SupervisionPipeline.run_once()`:
  `Watcher → Diagnostician → RootCauseAnalyst → Synthesizer → Evaluator(baseline) →
  Patcher → Evaluator(candidate) → TraceReplay → RedTeam`. One incident per cycle, deduped
  by span id. Each stage lives in its own module (`watcher.py`, `diagnostician.py`, etc.).

Key conventions to preserve when editing:

- **One `Incident` object threads through every stage** (`cassandra/models.py`), enriched
  in place (verdict → severity → root_cause → dataset → experiment pass-rates → efficiency
  → candidate_prompt → replay → redteam). Stages take and return an `Incident`.
- **All Phoenix MCP access goes through the single gateway `cassandra/phoenix_mcp.py`**
  (NFR-10). The live Phoenix MCP surface has **no create/run-experiment tool** — that is
  why evaluation runs *live against the agent* in `evaluator.py` rather than via a Phoenix
  experiment. `cassandra/phoenix_experiments.py` is an optional on-product A/B gated behind
  `PHOENIX_EXPERIMENTS_ENABLED`.
- **All env access goes through `cassandra/config.py:get_settings()`** (cached `Settings`).
  Never read `os.environ` directly.
- **All LLM calls go through `cassandra/llm.py`** (`structured()` for Pydantic-typed
  output, `text()` for free text). Backend is selected at runtime by env, in this
  precedence: `OPENAI_API_KEY` set → OpenAI; else `GEMINI_API_KEY` starting with `sk-or-`
  → OpenRouter; else Vertex Gemini. Gemini calls have built-in 429/503 backoff (Vertex
  Dynamic Shared Quota) — keep that retry wrapper. **The hosted demo runs on Vertex
  Gemini `gemini-2.5-flash-lite`** (the hackathon requires Gemini; OpenAI is non-compliant).
  Two Vertex gotchas, both load-bearing: (1) **hold the genai client in a local across the
  `await`** — a bare `_client().aio...` temporary is GC'd mid-request → "client has been
  closed"; (2) `gemini-2.5-flash` was DSQ-exhausted on the trial project (sustained 429s) so
  we use **flash-lite** (looser pool) and the burst stages (evaluator) are concurrency-bounded
  with a semaphore. Location must be a real region (never `global`).
- **Feedback-loop safety:** Cassandra drives the Patient for replay/red-team/eval using
  `session_id="test"`, and the `Watcher` filters out `session_id=="test"` spans so
  Cassandra never supervises its own probes into an infinite loop. Do not remove this filter.
- **The pipeline is agent-agnostic — never import from `patient/` inside `cassandra/`.**
  The baseline system prompt is resolved per incident by `cassandra/baseline.py`
  (`BASELINE_PROMPT_FILE` → the span's `llm.input_messages` system message → bundled
  ShopBot prompt as demo fallback), and **all live probes to the supervised agent go
  through `cassandra/patient_client.py:ask_patient()`** — that module documents the HTTP
  contract a third-party agent implements (template: `examples/adapter_template.py`,
  guide: "Bring your own agent" in `docs/WORKFLOWS.md`). The Phoenix prompt name is
  `PATIENT_PROMPT_NAME` (default `patient-shopbot-system`), not a hardcoded string.
- **ADK is a thin runtime envelope, not the logic.** `build_adk_agent()` wraps
  `SupervisionPipeline` in a real `LoopAgent` + custom `BaseAgent` (google-adk 2.1.0) to
  satisfy the "built with ADK / Agent Engine" requirement. All business logic stays in
  plain, unit-tested Python so tests need no ADK runtime.
- **Same code backs the pipeline and the published MCP server.** `cassandra/mcp_server.py`
  (`cassandra-mcp`, FastMCP) reuses `Diagnostician.judge`, `Synthesizer`, `Patcher` — one
  source of truth. The pure `Diagnostician.judge()` is shared by the pipeline, MCP, and
  self-eval; keep it side-effect-free.

Self-observability (the recursive core, targets the Arize bonus criterion):
`cassandra/instrumentation.py:init_self_tracing()` ships Cassandra's own reasoning spans
to the `cassandra-meta` Phoenix project; `cassandra/selfeval.py` + `cassandra/traps.py`
grade Cassandra's own diagnostic accuracy against a hand-labeled ground-truth trap library.

## Deployment

`deploy/` holds `cloudrun.Dockerfile`, `cloudbuild.yaml`, and `agent_engine.py` (Vertex AI
Agent Engine entry). Durable state (Watcher cursor + dedupe set) is backed by Firestore /
GCS / local file, selected by `STATE_BACKEND` (`cassandra/state.py`).
