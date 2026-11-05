# Cassandra — System Design, Workflows, Flaws & Security

> A plain-language tour of how the whole thing fits together, every workflow narrated end to
> end, the known flaws (with what's real vs. stale), the security posture, and where the design
> can be simplified. Companion to [ARCHITECTURE.md](ARCHITECTURE.md) (which is the formal,
> requirement-indexed view) and the animated explainer at **`/how`** on the dashboard.

Last substantive update: 2026-06-05 (see [docs/sessions/](sessions/) for the change log).

---

## 1. The one-paragraph mental model

There are **two separate agents**. The **Patient** ("ShopBot") is a deliberately fragile
customer-support agent that answers `/chat` and emits OpenInference traces to Arize Phoenix.
**Cassandra** is the meta-agent: it never touches the Patient's code — it watches the Patient
*through Phoenix telemetry*, and when it sees a failure it runs a fixed pipeline that diagnoses
the failure, explains the root cause, synthesizes an eval dataset from it, scores the current
prompt vs. a hardened candidate live against the agent, proposes the patch, and replays the
original failing input to prove the fix. It writes its findings (annotations, datasets, prompt
versions) back into Phoenix, traces its *own* reasoning into a separate Phoenix project, and can
even grade its own diagnostic accuracy. The same supervision code is also **published as an MCP
server** so any other agent/IDE can call it.

```
 The Patient  ──OpenInference traces──▶  Phoenix  ◀──MCP get-spans──  Cassandra
 (ShopBot)                              (patient-prod)                (8-stage pipeline)
     ▲                                  (cassandra-meta) ◀─self-traces─┘
     └───────────── sandboxed session_id="test" (replay / eval / red-team only) ───────────┘
```

---

## 2. Components

| Component | Path | What it is |
|-----------|------|-----------|
| **The Patient** | `patient/` | Fragile ShopBot. FastAPI `/chat`, flaky tools, OpenInference spans → `patient-prod`. |
| **Cassandra pipeline** | `cassandra/` | The 8-stage supervision loop + the ADK runtime shell. |
| **Phoenix gateway** | `cassandra/phoenix_mcp.py` | The single module that talks the partner MCP (NFR-10). |
| **cassandra-mcp** | `cassandra/mcp_server.py` | Cassandra's *own* published MCP server (5 tools). |
| **Dashboard** | `dashboard/` | FastAPI: serves the cockpit + the `/how` explainer, SSE feed, `/ask`, `/selfeval`. |
| **Self-eval** | `cassandra/selfeval.py` + `cassandra/traps.py` | Grades Cassandra's own diagnoses vs. labeled ground truth. |
| **Config** | `cassandra/config.py` | The one place env is read (`get_settings()`), backend selection. |
| **LLM** | `cassandra/llm.py` | The one place LLM calls happen (`structured()`, `text()`), backend-agnostic. |

The legacy React app under `web/` is **no longer wired in** (see §10).

---

## 3. The telemetry-only boundary (and why it can't loop)

Cassandra and the Patient share **exactly one** channel: Phoenix telemetry. Cassandra reads the
Patient's production spans and writes annotations back — it never calls the Patient's internals…
*except* a deliberate sandbox: replay, red-team, and evaluation drive the live Patient with
`session_id="test"` (and a `system_override` to test candidate prompts). Two guards keep this
from becoming a feedback loop where Cassandra supervises its own probes:

1. **The Watcher drops `session_id=="test"` spans** (`watcher.py`) — so test traffic is never
   diagnosed.
2. **The Patient only honors `system_override` on the `session_id=="test"` path**
   (`patient/agent.py:resolve_override`) — so the override is both safe (see §9) and scoped.

---

## 4. The Incident object (the spine)

One `Incident` (`cassandra/models.py`) is created per failing span and **threads through every
stage**, getting enriched in place. By the end it carries: `span`, `verdict` + `severity`,
`root_cause`, `dataset_id` + `dataset_examples`, `experiment` (baseline/candidate pass-rates +
delta), `efficiency` (token/latency deltas), `candidate_prompt` + diff, `replay`, `redteam`, and
the current `stage`. Every sub-agent takes an `Incident` and returns the same `Incident`. This is
why the pipeline reads as a clean linear story.

---

## 5. Workflow A — the supervision pipeline (one incident)

Orchestrated by `cassandra/loop_agent.py:SupervisionPipeline.run_once()`. Each stage is its own
module. "MCP tool" is the Phoenix partner tool the stage calls through `phoenix_mcp.py`.

| # | Stage (module) | Input | What it does | Output | Phoenix MCP tool |
|---|----------------|-------|--------------|--------|------------------|
| 1 | **Watcher** (`watcher.py`) | durable cursor | poll spans since cursor; skip `session=="test"`; keep only trees with input+output | a fresh `Incident` | `get-spans` |
| 2 | **Diagnostician** (`diagnostician.py`) | span input/output **+ tool results** | LLM-as-judge (temp 0) → classify `hallucination / prompt_drift / tool_failure / ok` + confidence + severity | verdict; annotate span | `add-span-annotations` |
| 3 | **RootCauseAnalyst** (`rootcause.py`) | the diagnosed span | culprit + ordered causal chain + a fix strategy for the Patcher | root-cause summary | `add-span-annotations` |
| 4 | **Synthesizer** (`synthesizer.py`) | failure class + why | generate ~12 diverse adversarial probes + expected behavior | a Phoenix dataset | `add-dataset-examples` |
| 5 | **Evaluator — baseline** (`evaluator.py`) | dataset + current prompt | run each probe through the **live** Patient + LLM judge | baseline pass-rate + avg tokens/latency | live (no run-experiment tool) |
| 6 | **Patcher** (`patcher.py`) | fix strategy + failing turn | rewrite the system prompt to close the failure; unified diff; **never auto-promoted** | candidate prompt → prompt version | `upsert-prompt` |
| 7 | **Evaluator — candidate** (`evaluator.py`) | same dataset + candidate prompt | re-run live; pass-rate delta + cost/latency `EfficiencyReport` | candidate pass-rate + deltas | live (+ optional Phoenix experiment) |
| 8 | **TraceReplay** (`replay.py`) | the **exact** original failing input | re-run on the candidate prompt; judge confirms before→after | `FIXED` / `STILL BROKEN` | live |
| 9 | **RedTeam** (`redteam.py`) | synthesized probes | fire them at the live Patient under both prompts | how many survive the patch | live |

> The README/ARCHITECTURE call this the "8-stage" pipeline because root-cause, replay and
> red-team were layered onto the original five; the table above is the faithful as-built order.

**Why evaluation is "live" and not a Phoenix experiment:** the `@arizeai/phoenix-mcp` surface has
**no create/run-experiment tool** (only read-side `get-experiment-by-id`,
`list-experiments-for-dataset`). So `evaluator.py` runs the probes against the live agent for real,
honest numbers. `cassandra/phoenix_experiments.py` *optionally* also records a first-class Phoenix
experiment via the Python client, gated behind `PHOENIX_EXPERIMENTS_ENABLED` and fully guarded.

---

## 6. Workflow B — the published `cassandra-mcp` server

`cassandra/mcp_server.py` (FastMCP, console entry `cassandra-mcp`, stdio) re-exposes the same
`Diagnostician.judge`, `Synthesizer`, `Patcher` code as MCP tools — one source of truth:

| Tool | Input → Output | Touches Phoenix? |
|------|----------------|------------------|
| `diagnose` | one agent turn → failure-class verdict | no |
| `synthesize_evals` | a failure → adversarial eval set | no |
| `propose_patch` | prompt + failure → hardened prompt + diff | no |
| `supervise_latest` | (none) → runs the **full** loop on the latest production trace, writing back to Phoenix | **yes** |
| `self_evaluate` | (none) → Cassandra's own diagnostic-accuracy scorecard | no |

Any Claude Desktop / Cursor session that registers `cassandra-mcp` can now say *"diagnose this
agent turn"* or *"supervise my latest trace."* The animated `/how` page shows each tool's JSON
request → reasoning → JSON response.

---

## 7. Workflow C — self-evaluation (the recursive loop)

`selfeval.py` runs the hand-labeled trap library (`traps.py`) through the live Patient
(`session_id="test"`) and Cassandra's own `Diagnostician.judge`, then scores the verdicts against
ground truth → a `Scorecard` (overall + per-class). Exposed three ways: the dashboard button,
`POST /selfeval`, and the `self_evaluate` MCP tool.

**The judge must see the tool results.** The single biggest accuracy fix this project has had was
plumbing the Patient's **tool call results** into the judge — without them the judge only sees a
fluent reply and over-flags grounded answers as hallucinations. The Patient now returns its
`tool_calls` in the `/chat` response; `selfeval` forwards them to `judge()`.

Trap taxonomy (what a correct verdict is):
- **hallucination** — invented *facts/policy* not supported by any tool (e.g. a refund policy for a
  region where `get_refund_policy` returned `{found:false}`).
- **tool_failure** — misreported a *data-lookup result* (order status/carrier/ETA) the tool didn't
  actually return (e.g. an order that exists but has null carrier/eta, where the agent invents them).
- **prompt_drift** — abandoned role/format (poem, pirate speak).
- **ok** — grounded in a successful tool result, *or* honestly surfaced that data was unavailable.

---

## 8. Workflow D — the dashboard & SSE

`dashboard/main.py` serves the self-contained cockpit (`dashboard/ui/index.html`) and the animated
explainer (`dashboard/ui/how-it-works.html`, routes `/how` and `/how-it-works`). On startup it
calls `init_self_tracing()` and launches an in-process 5-second `SupervisionPipeline.run_once()`
loop (the demo cadence; in production a Cloud Function drives it). Each stage publishes a
`PipelineEvent` to an in-process bus (`events.py`), streamed to the browser over SSE at `/events`.
`/ask` proxies a customer message to the Patient; `/selfeval` returns the scorecard as JSON.

---

## 9. LLM backend selection (and the caching gotcha)

All model calls go through `cassandra/llm.py`. Backend is chosen at runtime from env, in this
precedence (`config.py`):

1. `OPENAI_API_KEY` set → **OpenAI** (`gpt-4o-mini`). *This is the current default* — it avoids the
   Vertex Dynamic-Shared-Quota 429 throttling documented in [the 2026-06-04 session note](sessions/2026-06-04-vertex-quota-and-fixes.md).
2. else `GEMINI_API_KEY` starts with `sk-or-` → **OpenRouter** (OpenAI-compatible wire).
3. else → **Vertex Gemini** (auths via ADC, not an API key).

`Settings.model_provider` / `model_name` derive the active provider so e.g. `upsert-prompt` tags
the prompt version with `OPENAI` vs `GOOGLE` correctly (previously hardcoded `GOOGLE`).

> **Gotcha:** `get_settings()` is `@lru_cache`d and `load_dotenv` runs at import — so **editing
> `.env` does nothing until the process restarts.** Long-running servers must be restarted after a
> `.env` change. Scripts/tests can call `config.reload_settings()` to re-read without a new process.
> Gemini calls additionally ride a 429/503 backoff (`_gen_with_retry`); classifiers pass
> `temperature=0` for deterministic verdicts.

> **Honesty caveat (v2, `cassandra-v2`):** "deterministic" applies only to the **Diagnostician**
> (`temperature=0`); the evaluator / replay / red-team judges use the `0.2` default. And
> `temperature=0` does **not** make an LLM truly deterministic (Vertex Gemini varies run-to-run).
> A genuinely deterministic verdict requires the code-based grounding verifier proposed in
> `EVAL_PLAN.md` (L1), not just a temperature setting. See `EVAL_PLAN.md` §5 (F4).

---

## 10. Flaws & status (reconciliation)

The flaw list that kicked off the 2026-06-05 session was partly stale. Ground-truth status:

| # | Reported flaw | Real status | Resolution |
|---|---------------|-------------|------------|
| 1 | `run_pipeline.py` hardcodes port 8082 in its error string | Cosmetic (matched `.env`), could drift | Now derives the port from `s.patient_endpoint`. |
| 2 | `normalize_span` can't parse nested attribute keys (failing test) | **Not failing** — committed test uses flat keys; `_flat_str` was flat-only | Added defensive nested-key fallback + a nested-key test. |
| 3 | `get_settings()` lru_cache → stale env | **Real** | Added `reload_settings()`; documented the "restart after `.env`" rule (§9, CLAUDE.md). |
| 4 | Evaluator stubs return `{"status":"queued"}`, pass-rates always 0.0 | **Outdated** — `evaluator.py` already scores live | No stub exists; left as the real live evaluator. |
| 5 | `create_prompt_version` hardcodes `model_provider="GOOGLE"` | **Real** | Now uses `s.model_provider` / `s.model_name`. |
| — | Diagnostician accuracy ≈ 18% (prior session's open item) | **Real, biggest item** | Plumbed tool results into the judge, sharpened the taxonomy, made it deterministic → **100%** on the trap suite (18→64→91→100). ⚠️ **See F1 below — this number measured the self-eval path only.** |
| — | **F1: the 100% measured the wrong code path** | **Real (fixed on `cassandra-v2`)** | `normalize_span` read a top-level `tool_calls` key that never existed, so in **production** the Diagnostician judged with **no** tool ledger (the self-eval HTTP path *did* pass tools — hence 100%). Fixed via `_extract_tool_calls` (telemetry oracle / `EVAL_PLAN.md` L0); production path now feeds the ledger to the judge. **Re-run `selfeval` to record the true production-path accuracy as the new baseline.** |
| — | Patient (gpt-4o-mini) no longer hallucinated → demo broken | **Discovered this session** | Strengthened `FRAGILE_SYSTEM_PROMPT` so the model fabricates on missing data again (the canonical failure). |
| — | `system_override` was an open prompt-override surface | **Real (security)** | Gated to `session_id=="test"` via `resolve_override` (§11). |
| — | `LoopAgent` deprecation warning (google-adk) | Cosmetic | Left as-is to avoid churn before ship; migrate to `Workflow` later. |

---

## 11. Security audit

**Posture:** this is a hackathon demo, not a hardened production deployment — but the credibility
bar is "nothing embarrassing." Findings and actions:

| Area | Finding | Action |
|------|---------|--------|
| Secrets in git | **Clean** — git history and tracked files contain no keys; `.env` is gitignored, `.env.example` has only placeholders. | Keep `.env` untracked; never log secrets. |
| Live keys in working tree | Real Gemini/OpenAI/Phoenix keys live in the local `.env` and were surfaced in a working session. | **Rotate** the surfaced keys (owner action — see checklist). |
| `system_override` | Was honored for *any* caller → an unauthenticated party could replace ShopBot's whole system prompt and drive its tools (prompt-injection / instruction override). | **Fixed** — `resolve_override` honors it only on `session_id=="test"`; covered by `tests/test_patient_security.py` and verified live. |
| Patient endpoint exposure | `/chat` is unauthenticated by design for the demo. | In production, put the Patient behind network/auth; the override gate is the in-app backstop. |
| Dashboard proxy | `/ask` forwards to `PATIENT_ENDPOINT` from config (not user-supplied) → no SSRF. | None. |
| Dependencies | Pinned to minimums in `pyproject.toml`. | Run `pip-audit` before ship (follow-up). |

**Secret-rotation / hygiene checklist (owner):**
- [ ] Rotate the OpenAI key, the Gemini API key, and the Phoenix API key that were in `.env`.
- [ ] Confirm `.env` is still gitignored (`git check-ignore .env`) and never `git add -f`'d.
- [ ] In deployed environments, source secrets from Secret Manager, not a file.
- [ ] (Optional) `pip-audit` / `npm audit` (the latter only if `web/` is revived).

---

## 12. Simplification recommendations

Applied this session (low-risk):
- **Single source for the active provider/model** — `config.model_provider` / `model_name` now feed
  `phoenix_mcp.create_prompt_version` (no more hardcoded `GOOGLE`).
- **Single source for the Patient port** — `run_pipeline.py` derives it from `patient_endpoint`.

Recommended, **not** applied (to avoid risk right before ship — documented so the next session can):
- **Centralize OpenAI/Gemini client construction.** The `is_openai / is_openrouter / Vertex`
  branching and client building is duplicated in `llm.py`, `patient/agent.py`, and
  `phoenix_experiments.py`. Extract one client factory + one `provider()` helper. Pure refactor,
  but it touches the hot path that was just verified working — do it deliberately, with tests.
- **Retire the legacy `web/` React app.** It is unwired, adds a Node toolchain and `node_modules`
  bloat, and confuses reviewers about which UI is live. Safe to delete (the live UI is the
  self-contained `dashboard/ui/*.html`). Left in place pending owner confirmation.

---

## 13. Run & verify

```bash
pip install -e ".[dev]"
# .env already has OPENAI_API_KEY set (active backend). Restart servers after any .env change.

python -m uvicorn patient.agent:app   --port 8082 --host 127.0.0.1   # the Patient (ShopBot)
python -m uvicorn dashboard.main:app  --port 8085 --host 127.0.0.1   # cockpit + /how + SSE + APIs
python scripts/run_pipeline.py                                        # drive one full supervision cycle

pytest                                   # offline suite (LLM + MCP mocked)
```

- Cockpit: <http://127.0.0.1:8085>  ·  Animated explainer: <http://127.0.0.1:8085/how>
- Self-eval scorecard: `POST http://127.0.0.1:8085/selfeval` (or the dashboard button).
- Diagnostic accuracy on the trap suite was reported **100%** (11/11; hallucination 4/4,
  tool_failure 2/2, prompt_drift 2/2, ok 3/3) on the OpenAI backend — but ⚠️ that number came
  from the **self-eval HTTP path**, which fed tool results to the judge; the **production** path
  did not (F1, §10). After the `cassandra-v2` telemetry-oracle fix, **re-run `selfeval` to
  capture the real production-path accuracy** (expected lower, especially on `tool_failure`/`ok`).
