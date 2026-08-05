# CLAUDE.md

> **Orientation:** read [docs/CODEBASE_MAP.md](docs/CODEBASE_MAP.md) first — compact map of stack, entry points, flow, and gotchas.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠ Known-broken (audited 2026-08-05 — do not treat these as working)

The project is moving from hackathon demo to product. Two audits found defects that are **still
open**; read them before trusting any verdict, metric, or deployment claim in this repo.

- **[docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md)** — security + load. 3 CRITICAL, 4 HIGH.
  Reproduce the load numbers with `python scripts/stress_probe.py` (offline, no LLM spend).
- **[docs/sessions/2026-08-05-code-audit-and-launch-plan.md](docs/sessions/2026-08-05-code-audit-and-launch-plan.md)**
  — correctness audit + the launch plan (scope, hours, sequencing).

Load-bearing facts, so no future session re-derives or contradicts them:

1. **The grounding oracle is not trustworthy yet.** It checks that a tool call *happened*, not
   that the claim *matches* it (`grounding.py:139-141`) — a successful `lookup_order` returning
   DHL scores an answer of "UPS" as OK. Its extractors also over-fire, and decline markers are
   unreachable once any claim matches (`grounding.py:85-96`), so honest refusals get flagged.
   Measured: 3 of 5 verdicts wrong. **Don't cite pass-rates as evidence of anything yet.**
2. **"Refuse everything" is the degenerate optimum** of the whole pipeline — eval, replay and
   red-team all reward it and nothing measures regression on normal traffic.
3. **`system_override` fails open when `REPLAY_SHARED_SECRET` is unset** (`patient/agent.py:67`),
   and `session_id=="test"` hijacks are invisible to the Watcher. Never relax this gate; the fix
   is to fail *closed*. (Earlier notes call this "deferred by design" — that is superseded.)
4. **Never start the supervision loop per web instance.** `dashboard/main.py:34-57` does this
   today and `cloudbuild.yaml` sets no `--max-instances`. The worker must be split out and run as
   exactly one leader-elected process.
5. **State is not concurrency-safe.** `state.py` dedupe is a 500-entry array with
   non-transactional read-modify-write, and it does blocking I/O from async code. Two instances
   lose each other's writes (measured).
6. **The Python import package must be renamed to `cassandra_ai`** before any release —
   `cassandra` is owned by `cassandra-driver` on PyPI. Dist name `cassandra-ai`, CLI stays
   `cassandra`. The Cassandra brand is unaffected (it is the *product* name; the company name is
   a separate, still-open decision).

When you fix one of these, update the audit doc and this list in the same change.

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
   **Then re-read this file top to bottom and reconcile it with what the session actually did:**
   - **Repository structure** — any module added, removed, renamed or repurposed? Any new
     top-level directory? Update the map. This is the one that rots fastest and hurts most.
   - **Known-broken** — did you fix an item (remove it, and update `docs/SECURITY_AUDIT.md`),
     or find a new one (add it)? Never leave a fixed defect listed as broken, and never leave a
     known defect unlisted.
   - **Commands / Architecture / Deployment** — did a command, convention, seam or deploy fact
     change? A stale instruction here silently misleads every future session.

   Treat CLAUDE.md as **code that ships with the repo**: it is wrong until proven current, and
   updating it is part of the task, not an optional epilogue. If nothing changed, say so
   explicitly in the session note rather than skipping the check.
4. **`.env` / settings changes don't take effect until the servers restart** — `get_settings()`
   is cached (`reload_settings()` exists for scripts/tests). Note this whenever you touch config.

A `Stop` hook in `.claude/settings.local.json` prints a reminder of this protocol; the protocol
itself lives here.

## Repository structure (CANONICAL — keep this current every session)

This is the authoritative module-level map. `docs/CODEBASE_MAP.md` is the orientation
narrative (stack, flow, gotchas) at directory level; **when you add, remove, rename or
repurpose a module, update this section in the same change** (and `CODEBASE_MAP.md` if a
whole directory changed). A stale map costs every future session real time.

```
cassandra/     the meta-agent (agent-agnostic — never imports patient/)
patient/       the supervised demo agent, "ShopBot" (agent.py, flaky tools.py, instrumentation.py)
dashboard/     FastAPI + SSE cockpit; ui/index.html is the no-build fallback at /cockpit
web/           PRIMARY React/Vite frontend (edit web/src/**); built by the Dockerfile webbuild stage
tests/         offline pytest suite — LLM + MCP mocked, no live services needed
scripts/       one-shot drivers: run_pipeline (thin wrapper), seed_incident, stress_probe, MCP spike
deploy/        cloudrun.Dockerfile, cloudbuild.yaml, agent_engine.py, vm_startup.sh
functions/     trace_poller (scheduled Watcher driver)
examples/      third-party adapter template, gate cases, GitHub Actions prompt gate
docs/          design refs + sessions/ (newest note = last session's state)
```

### `cassandra/` by role

**Pipeline stages** — each takes and returns the one `Incident`, enriching it in place:
`watcher.py` → `diagnostician.py` → `rootcause.py` → `synthesizer.py` → `evaluator.py`
(baseline) → `patcher.py` → `evaluator.py` (candidate) → `replay.py` → `redteam.py`.
`loop_agent.py` orchestrates them (`SupervisionPipeline.run_once`) and holds the thin ADK shell.

**Verdict layer** (what decides pass/fail — the product's core):
- `grounding.py` — deterministic verifier + `GroundingSpec`. Pure: no LLM, no network, no env.
- `oracle.py` — the shared scoring contract: grounding first, LLM judge only on abstain/no ledger.
  Used by `evaluator.py`, `redteam.py`, `replay.py`, `gate.py` — change scoring here, once.
- `models.py` — `Incident`, `Verdict`, `SpanRecord` and every other shared type.

**Seams** (the single chokepoints — keep them single; this is what makes the product portable):
- `config.py` — ALL env access (`get_settings()`, cached; `reload_settings()` for tests/scripts)
- `llm.py` — ALL model calls (`structured()` / `text()`), backend chosen at runtime
- `phoenix_mcp.py` — ALL Phoenix MCP access (NFR-10)
- `state.py` — durable cursor + dedupe (`STATE_BACKEND`: firestore | gcs | local)
- `patient_client.py` — ALL live probes to the supervised agent (the documented HTTP contract)
- `baseline.py` — resolves the supervised agent's current prompt (file → span → demo fallback)
- `events.py` — in-process pub/sub feeding the dashboard SSE

**Entry points:** `cli.py` (the `cassandra` console script; lazy per-subcommand imports),
`run_once.py` (one full cycle), `mcp_server.py` (published `cassandra-mcp` tools),
`gate.py` (`cassandra-gate` CI prompt-regression gate), `banner.py`.

**Self-observability:** `instrumentation.py` (Cassandra's own spans → `cassandra-meta`),
`selfeval.py` + `traps.py` (grades its own diagnostic accuracy vs hand-labeled ground truth),
`report.py` (auto-postmortem → `reports/<id>.md`).

**Optional:** `phoenix_experiments.py` (on-product A/B, gated by `PHOENIX_EXPERIMENTS_ENABLED`).

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

# Unified CLI (pip-installed console script — banner + subcommands):
cassandra                        # banner + command list
cassandra dashboard [--port N]   # dashboard + SSE cockpit (default 8085)
cassandra run                    # one full supervision cycle (== python scripts/run_pipeline.py)
cassandra gate ...               # CI prompt-regression gate (passthrough to cassandra-gate)
cassandra mcp                    # MCP server over stdio (== cassandra-mcp; emits zero stdout)
```

The CLI (`cassandra/cli.py`) lazy-imports per subcommand so `cassandra`/`--help` stay instant;
`cassandra run` delegates to `cassandra/run_once.py` (the runner lives in the package now so
it ships in the wheel — `scripts/run_pipeline.py` is a thin wrapper). PyPI dist name is
`cassandra-ai`; the import package stays `cassandra`.

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

**The current deployment is demo-grade, not production-grade** — see
[docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) §4 for the required changes. In short: the live
demo is a single GCE VM fronted by an **ngrok** tunnel (no WAF/DDoS/TLS you control, SPOF, and
`vm_startup.sh` pins a **stale image**, so a reboot rolls prod back). `cloudbuild.yaml` deploys
both services `--allow-unauthenticated` with no instance cap and **no test gate before deploy**,
and on Cloud Run the background supervision loop is CPU-throttled between requests so it does not
reliably run at all. `/selfeval` takes no request body and runs the trap library through the LLM —
it is an open denial-of-wallet endpoint. Don't add features to this path; the P1 fix is to split
the supervision worker out of the web service.
