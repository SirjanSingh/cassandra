# Session Log: 2026-06-18 — Eval re-architecture + independence/product plan (planning only)

## Scope

Research + planning session. **No application code changed** (owner explicitly wanted the
repo's code state preserved). Two deliverables produced, both at repo root:

- [`EVAL_PLAN.md`](../../EVAL_PLAN.md) — proposed evaluation re-architecture (the answer to
  reviewers' "LLM-as-judge is unreliable / how do you know the judge is correct?").
- [`PRODUCT_PLAN.md`](../../PRODUCT_PLAN.md) — decouple from hackathon-forced deps
  (Phoenix/Arize, GCP/Vertex/Gemini, Agent Engine), productization, and monetization/GTM.

## Key findings (from reading the code, not assumptions)

1. **F1 — the self-eval measures a DIFFERENT code path than production. (Latent bug, important.)**
   `selfeval.py:42` reads `tool_calls` straight from the Patient's `/chat` HTTP response and
   feeds them to the judge. The **production** path does not: `normalize_span`
   (`phoenix_mcp.py:251`) sets `tool_calls = raw.get("tool_calls", [])`, but the Patient
   records tools as the span attribute `tool.calls` *nested under* `attributes`
   (`patient/agent.py:209`); and `Diagnostician.diagnose` reads `span.tool_calls or
   span.raw.get("tool.calls")` (`diagnostician.py:86`) — both at the top level, where it
   doesn't live. ⇒ **In production the Diagnostician judges with no tool results.** The
   reported 100% trap-suite accuracy is an artifact of the self-eval harness, not what runs
   in prod. Canonical Germany hallucination still gets caught (absence-of-grounding is
   visible from output alone), but `tool_failure` / `ok` discrimination is almost certainly
   still degraded on the live pipeline and unmeasured.
2. **F2 — trap labels are on inputs, not (input, output, tools) triples.** Patient runs at
   `temperature=0.4`; a benign run's correct verdict is `ok` but gets scored against a fixed
   `hallucination` label → marked wrong. Caps achievable accuracy, injects noise.
3. **F3 — headline eval metric is broken.** 06-11 note + `reports/inc-U3BhbjozMDE3.md` show
   baseline 12% == candidate 12% while **replay = FIXED**. `Evaluator._judge` never sees tool
   results and grades against the Synthesizer's free-text `expected_answer` (which may be a
   concrete policy), so a correctly-declining candidate fails. A deterministic grounding
   check recovers the true ≈0%→≈100% signal the replay already shows.
4. **F4 — "determinism" overstated.** Only the Diagnostician passes `temp=0`; evaluator/
   replay/redteam use the 0.2 default. And `temp=0` ≠ deterministic for LLMs.
5. **Licensing:** Arize Phoenix OSS is **Elastic License 2.0** (source-available, NOT OSI
   open source; restricts hosted-service resale). Langfuse self-host is **MIT**. Both speak
   OTLP/OpenTelemetry — the escape hatch for backend independence.

## Proposed eval architecture (EVAL_PLAN.md)

Core realization: 3 of the 4 failure classes are decided by reading the **structured tool
ledger**, not prose. Collapse the 4-way fuzzy classification into ONE irreducible NL
judgment ("concrete claim vs honest decline"); derive the class structurally. Four layers:
**L0** telemetry oracle (fix the tool-ledger gap in `normalize_span`) · **L1** deterministic
`GroundingChecker` driven by a declarative `GroundingSpec` (PRIMARY; cites the tool call;
reproducible) · **L2** demoted LLM judge (one cited boolean; fallback for no-spec/open-domain;
optional jury) · **L3** meta-eval harness that scores L2 vs the L1 oracle on the *production*
path with per-class precision/recall/F1 + a judge-vs-oracle CI gate. The judge becomes a
calibrated exception, not the default. This is also the answer to "are we just an API
wrapper" — the load-bearing verdict stops being an LLM call.

## Product/independence plan (PRODUCT_PLAN.md)

Own the contracts, rent the backends. Existing chokepoints (`phoenix_mcp`, `llm`, `config`,
`state`, `baseline`/`patient_client`) make this mostly "add one interface + a 2nd adapter per
seam," not a rewrite. Introduce `TelemetryBackend` (Phoenix self/cloud, **Langfuse/MIT**, raw
OTLP) + an owned `DatasetStore`/`PromptRegistry`; generalize `llm.py` (+ self-hosted models
via vLLM/Ollama or LiteLLM); demote ADK/Agent Engine to an optional runtime adapter +
containerize; broaden `state.py` (Postgres/S3). Business model: **open-core** (permissive OSS
core = loop + MCP + gate + verifier; paid = hosted/owned dataset store/team/RBAC/SLA/on-prem).
GTM: PLG via the CI gate + MCP server → design partners → "stop trusting an LLM to grade your
LLM" content as category creation. Differentiator vs Arize/LangSmith/Braintrust/Langfuse/
Guardrails: autonomous detect→fix→verify→regression-gate loop + **deterministic** verification
+ store-neutral + the owned regression-dataset flywheel as switching cost.

## Verification

None — planning only, no behavior changed, no tests run. The findings above (esp. F1) are
the recommended *first* things to verify empirically with a production-path test before any
implementation.

## Open items (for the owner's review)

- Review `EVAL_PLAN.md` and `PRODUCT_PLAN.md`; answer the §6 strategic forks in PRODUCT_PLAN
  (OSS license, default telemetry backend, hosted-vs-self-host-first, ICP/wedge, keep GCP
  adapter?, brand).
- First implementation step regardless of strategy: fix F1 (telemetry oracle / L0) + add a
  production-path test that asserts the tool ledger reaches the judge — it tells you the
  *real* current accuracy.
