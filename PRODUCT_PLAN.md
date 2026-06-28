# Cassandra — Independence, Upgrade & Product Plan

> Status: **morning brief / plan only. No code was changed producing this.**
> Companion to [`EVAL_PLAN.md`](EVAL_PLAN.md) (the evaluation re-architecture) — read that
> first; it is the technical spine of everything below.
> Scope of this doc: (0) the "are we just an API wrapper?" question, (1) what's
> hackathon-forced vs. core, (2) how to decouple from Phoenix/GCP/Gemini, (3) what the
> product is, (4) how to monetize it, (5) sequencing, (6) decisions only you can make.

---

## 0. "We're just another API wrapper bitch" — the honest answer

You're half right, and the half that's right is the most important thing to fix.

**If Cassandra's value is "we call an LLM to judge another LLM," then yes — it's a wrapper,
it has no moat, the judge can hallucinate, and the whole thing is circular.** A reviewer who
asks *"how do you know the judge is correct?"* has already found the bottom of that well.
That circularity is exactly why the eval re-architecture exists.

**The escape from wrapper-hood is to make the load-bearing judgment NOT an LLM call.** Four
things, in order of how much moat they create:

1. **The deterministic grounding verifier (the real moat).** In a tool-using agent, the
   tool-call ledger is *structured ground truth*: `get_refund_policy("DE") → {found:false}` is
   a fact. Cassandra's core verdict ("the answer asserted something no successful tool
   supports") becomes a **set-membership check over structured telemetry — code, not a
   prompt.** That is not an API wrapper; it's a verifier that *uses* an LLM only for a narrow,
   measured, fallback sub-question. See `EVAL_PLAN.md §3`. This is the single most important
   product decision: **lead with the thing that isn't an LLM.**
2. **The closed loop is a system, not a call.** Detect → diagnose → root-cause → synthesize a
   regression dataset → score baseline vs candidate → patch → replay the original failure →
   red-team → gate in CI. Anyone can wrap a judge. Wiring an *autonomous, telemetry-driven,
   self-verifying improvement loop* that writes back into your observability stack is a
   product. Wrappers don't have a `run_once()` that closes the loop.
3. **The data flywheel = switching cost.** Every real production failure Cassandra catches
   becomes a permanent, versioned **regression suite** (`incident → dataset → CI gate`). After
   six months a customer has hundreds of adversarial datasets minted from *their own*
   incidents. That accumulated, customer-specific corpus is the thing they can't get from a
   competitor and won't want to abandon. The LLM is rented; the datasets are owned.
4. **Telemetry-neutral integration.** If Cassandra plugs into whatever observability stack a
   team already runs (OTel/OpenInference), it's infrastructure, not a toy. Wrappers are
   point solutions; infrastructure earns recurring spend.

So: the answer to "are we a wrapper" is **"only if we let the LLM be the product. The plan is
to demote the LLM to a component and make deterministic verification + the closed loop + the
data flywheel the product."** Every recommendation below serves that.

---

## 1. What's hackathon-forced vs. core

The hackathon (Google Cloud Rapid Agent Hackathon, Arize track) imposed three hard
constraints that are baked into the current codebase. None of them are *product* decisions —
they were *contest* decisions. Inventory:

| Dependency | Why it's here | What it gives us | Lock-in risk | Verdict |
|------------|---------------|------------------|--------------|---------|
| **Arize Phoenix Cloud** (spans, annotations, datasets, prompts via MCP) | Arize track requirement | telemetry store + dataset/prompt registry + write-back | **Medium-High.** SaaS dependency; Phoenix OSS is **Elastic License 2.0 — source-available, NOT OSI open source, and forbids offering it as a hosted service** | **Abstract** behind a backend interface; keep Phoenix as *one* adapter |
| **Vertex Gemini `2.5-flash-lite`** | "must use Gemini" contest rule | the LLM backend | **Low** — `llm.py` already abstracts OpenAI/OpenRouter/Vertex | **Generalize** to a provider interface; drop the Gemini-only assumption |
| **GCP runtime**: Cloud Run, GCE VM, **Agent Engine + ADK**, Firestore, GCS | "built with Agent Builder / Agent Engine" requirement | managed runtime + durable state | **Medium.** ADK/Agent Engine is a thin shell (`loop_agent.py`); Firestore/GCS are behind `state.py` | **Demote** ADK to an optional adapter; containerize; broaden state backends |
| **ngrok tunnel** | GCP blocked serving ports on a fresh account | public ingress for the demo | n/a — accident | **Drop**; deploy to any container host |
| Single-incident-per-cycle + 5s in-process loop | demo determinism | predictable demo | n/a | **Keep as a mode**; add a real queue/worker for production |

**The good news:** the architecture already has the right chokepoints for a clean decoupling.
`cassandra/phoenix_mcp.py` (all Phoenix access), `cassandra/llm.py` (all model calls),
`cassandra/config.py` (all env), `cassandra/state.py` (durable state),
`cassandra/baseline.py` + `cassandra/patient_client.py` (the supervised-agent contract) are
each single seams. Independence is mostly *introducing one interface per seam and writing a
second adapter* — not a rewrite. CLAUDE.md's "never import `patient/` inside `cassandra/`"
discipline already did the hard architectural work.

---

## 2. The independence architecture (what to migrate, and to what)

Principle: **own the contracts, rent the backends.** Define small internal interfaces at each
seam; ship vendor adapters behind them; make the vendor a config choice, not an assumption.

### 2.1 Telemetry independence (the big one) — migrate to OpenTelemetry + a swappable backend

Today: the Patient emits OpenInference spans to Phoenix; Cassandra reads them back through the
Phoenix MCP. That couples both the *producer* and the *consumer* to Phoenix.

**Target:**
- **Instrument on the open standard.** OpenInference is already OTel-compatible, and the
  industry is converging on **OTel GenAI semantic conventions** (prompts, completions, tool
  calls, token usage) — vendor-neutral by design and now natively ingested by Datadog,
  Langfuse, Phoenix, etc. Keep emitting OpenInference, but treat it as "OTLP out," not
  "Phoenix in."
- **Introduce a `TelemetryBackend` interface** (generalize `phoenix_mcp.py`): `query_spans`,
  `annotate`, `create_dataset/add_examples`, `upsert_prompt`. Adapters:
  1. **Phoenix** (self-hosted, single Docker container — easiest self-host) or Phoenix Cloud
     — keep for the Arize story and existing users. *(Mind the EL2.0 resale restriction if
     you ever host it for customers.)*
  2. **Langfuse** (self-hosted is **MIT** — clean for an OSS product; feature parity between
     cloud and self-host; OTLP-native). Strong default for a vendor-neutral posture.
  3. **Raw OTLP / ClickHouse** (or your own store) — for teams that want no extra SaaS.
- **Decouple the dataset/prompt registry from the telemetry store.** Phoenix's dataset/prompt
  APIs are exactly the parts that were awkward (no create-experiment tool; the evaluator runs
  live *because* of that gap — `evaluator.py`). Define an internal `DatasetStore` /
  `PromptRegistry` so synthesized regression suites and candidate prompts live in *your* store
  (Postgres/SQLite/object storage), and *optionally* mirror to Phoenix/Langfuse. This is what
  turns the data flywheel (§0.3) into an asset you own rather than data in someone's SaaS.

Net: the supervised agent can ship traces anywhere; Cassandra reads from any OTLP-compatible
backend; the regression datasets are yours.

### 2.2 LLM provider independence — generalize, don't rewrite

`llm.py` already routes OpenAI / OpenRouter / Vertex. To finish the job:
- Formalize a tiny `LLMProvider` protocol (`structured()`, `text()`) — you already have the
  surface. Either keep the hand-rolled router or adopt **LiteLLM** as the adapter layer to get
  100+ providers + fallback/routing for free. (Hand-rolled keeps deps light; LiteLLM saves
  maintenance. Lean LiteLLM unless the dependency weight matters.)
- **Add a self-hosted/open-weights path** (vLLM / Ollama / TGI) — this is a *sales unlock*:
  regulated/enterprise buyers want on-prem with no data leaving the VPC. "Runs against your
  own model" is a differentiator vs. SaaS-only competitors.
- **Kill the Gemini-only assumption** in docs/config defaults once the contest no longer
  binds you. The retry/backoff logic for Vertex DSQ stays useful but becomes provider-specific
  config, not a global.

### 2.3 Cloud / runtime independence — containerize, demote ADK

- **ADK + Agent Engine → optional adapter.** `loop_agent.py` already isolates ADK to a thin
  `build_adk_agent()` shell over plain-Python `SupervisionPipeline`. Keep ADK as one runtime
  adapter (for anyone on Vertex), but the *default* runtime should be a plain container +
  scheduler (cron/worker/queue). The business logic never imported ADK — preserve that.
- **State backend**: `state.py` does firestore/gcs/local. Add **Postgres** and an
  **S3-compatible** option so durable state isn't GCP-bound.
- **Deployment**: one Dockerfile that runs anywhere (Cloud Run, ECS, Fly, Render, k8s,
  on-prem). Drop the ngrok accident entirely.
- **Scheduler**: replace the 5s in-process demo loop with a proper worker (the in-process loop
  stays as a `DEMO_MODE`).

### 2.4 Summary: the seams and their target interfaces

| Seam (today) | Interface to introduce | Adapters to ship |
|--------------|------------------------|------------------|
| `phoenix_mcp.py` | `TelemetryBackend` | Phoenix (self/cloud), Langfuse, raw OTLP |
| (new) | `DatasetStore` / `PromptRegistry` | Postgres/SQLite/object-store; mirror→Phoenix/Langfuse |
| `llm.py` | `LLMProvider` | OpenAI, Anthropic, Vertex, OpenRouter, **vLLM/Ollama** (or LiteLLM) |
| `state.py` | `StateBackend` (exists) | + Postgres, + S3 |
| `loop_agent.py` ADK shell | `Runtime` adapter | plain worker (default), ADK/Agent Engine (optional) |
| `baseline.py` / `patient_client.py` | supervised-agent contract (exists) | HTTP (exists), + adapters per framework |

---

## 3. The product (what you're actually selling)

### 3.1 Positioning

**"CI/CD for AI-agent reliability."** Cassandra is the system that catches an agent's
production failures, turns each one into a permanent regression test, proves a fix, and blocks
regressions before they ship — grounded in *deterministic verification*, not vibes.

Three nouns it can own, pick the wedge:
- **The eval engine** (deterministic grounding verifier + spec) — the defensible core.
- **The CI gate** (`cassandra-gate`) — the low-friction wedge: "regression-test your prompts
  like code." Easiest thing to adopt; expands into the loop.
- **The autonomous supervisor** (the full loop + cockpit + Phoenix/Langfuse write-back) — the
  high-value end state.

### 3.2 Product surfaces (already exist or near-exist)

| Surface | State today | Product role |
|---------|-------------|--------------|
| Grounding verifier + `GroundingSpec` | proposed (`EVAL_PLAN.md`) | the moat / differentiator |
| `cassandra-gate` CI tool | exists (`gate.py`) | adoption wedge (PLG) |
| `cassandra-mcp` server | exists (`mcp_server.py`) | distribution via Claude/Cursor; "diagnose this turn" |
| Supervision loop | exists (`loop_agent.py`) | the recurring-value core |
| Cockpit + SSE + `/how` | exists (`web/`, `dashboard/`) | the demo + the team dashboard |
| Auto-synthesized regression datasets | exists (`synthesizer.py`) | the data flywheel / switching cost |
| Auto-postmortems | exists (`report.py`, `reports/`) | the "wow" artifact for buyers |

You are **not** starting from zero — most of the product exists; it needs decoupling (§2),
the deterministic eval (`EVAL_PLAN.md`), and packaging.

### 3.3 Upgrade roadmap (phased; aligns with EVAL_PLAN phasing)

- **Phase A — Foundation / credibility (weeks).** Fix the eval (`EVAL_PLAN.md` L0–L3): make
  the verdict deterministic and the metric trustworthy; fix the production-path tool-result
  gap (`EVAL_PLAN.md §5 F1`). This is the prerequisite for *any* paid claim. In parallel:
  introduce the `TelemetryBackend` interface and a Langfuse adapter (proves vendor-neutrality).
- **Phase B — Product (1–2 months).** Self-serve onboarding ("point us at your agent's OTLP
  endpoint + write a 20-line GroundingSpec"); multi-agent / multi-project; spec authoring UX;
  hosted dashboards; the CI gate as a GitHub Action / GitLab template. Provider-agnostic +
  self-hosted-model path.
- **Phase C — Scale (quarter+).** Team features (RBAC/SSO), managed dataset store, judge-jury
  + calibration reporting as a feature, alerting/integrations (Slack/PagerDuty), SOC2 path for
  enterprise.

---

## 4. Monetization & go-to-market

### 4.1 Business model: **open-core**

The market is developer infrastructure; the proven model is open-core (Terraform/HashiCorp,
GitLab, Langfuse). The OSS core is your distribution and R&D engine; proprietary/hosted
features are the monetization arm.

- **Open-source core (MIT/Apache):** the supervision loop, the `cassandra-mcp` server, the CI
  gate, the deterministic verifier + spec format, local single-node run. This drives adoption,
  trust, and inbound. Pick a **permissive OSS license** (MIT/Apache) — *do not* inherit
  Phoenix's EL2.0 posture; permissive is what converts cold leads in dev tooling.
- **Paid (hosted + enterprise):** managed hosting, the owned dataset/prompt store, team
  collaboration, RBAC/SSO, multi-agent fleets, the calibrated judge-jury + precision/recall
  dashboards, alerting/integrations, SLA/support, on-prem/air-gapped, SOC2. Standard open-core
  split: monetize where the OSS deliberately stops (scale, collaboration, governance,
  hosting).

### 4.2 B2B vs B2C

- **B2B is the real market** (and where competitors live). Buyers: platform/ML-eng teams and
  AI-product teams running customer-facing agents who fear silent regressions. Pain is acute,
  budgets exist, value is quantifiable (incidents prevented, eng hours saved).
- **B2C / individual devs**: not a paying segment per se, but the **PLG funnel** — the OSS
  core + MCP server + free CI gate is how individual devs discover you and drag you into their
  employer. Treat "B2C" as top-of-funnel, monetize at the team/org boundary.

### 4.3 Pricing (benchmarked against the field)

The category prices on **seats + usage (traces/spans/eval-runs)**. Reference points: LangSmith
$39/seat/mo + $0.50/1k traces; Braintrust free 1M spans then jumps to $249/mo; Langfuse free
self-host (MIT); Laminar $30–$150/mo by data volume; Arize prices on span/data volume (can get
costly).

Recommended structure:
- **Free / OSS:** self-hosted, single project, community support. (Funnel.)
- **Team (usage + small seat fee):** hosted, per-agent-supervised or per-eval-run metering +
  a low per-seat. *Consider metering on the verb that creates value — "supervised agents" or
  "regression datasets maintained" — not raw spans, so you're not just reselling storage like
  the observability incumbents.* This is a differentiated pricing axis.
- **Enterprise (annual contract):** SSO/RBAC, on-prem/VPC + self-hosted models, SLA, security
  review, design-partner pricing early.

### 4.4 GTM motions

1. **PLG wedge = the CI gate + MCP server.** Lowest friction: "add this GitHub Action to
   regression-test your prompts." Land there, expand to the supervision loop + hosted
   dashboards. The MCP server seeds usage inside Claude Desktop/Cursor where devs already are.
2. **Design partners (3–5).** Teams running customer-facing agents who've been burned by a
   silent regression. Free/cheap in exchange for logos, feedback, and the case study ("caught
   N incidents, cut review time X%"). This is how infra companies start.
3. **Content + category.** Lead with the contrarian, true thesis from `EVAL_PLAN.md`:
   *"Stop trusting an LLM to grade your LLM. Here's how to make agent evals deterministic."*
   That post **is** the marketing — it's defensible, technical, and differentiates instantly
   from the LLM-judge crowd. Pair with the auto-postmortem artifact as the demo.
4. **Distribution via the ecosystem.** OTLP/OpenInference compatibility means "works with your
   existing Phoenix/Langfuse/Datadog." Ship framework adapters (LangChain/LangGraph, ADK,
   raw OTel). Be the reliability layer *on top of* observability, not a competing store.

### 4.5 Competitive landscape & where Cassandra wins

| Player | What they are | Where Cassandra differentiates |
|--------|---------------|-------------------------------|
| **Arize (AX/Phoenix)** | enterprise LLM/agent observability | Cassandra *acts* on the telemetry (autonomous fix+verify loop), and isn't locked to one store |
| **LangSmith** | agent eng platform, LangChain-native | framework-agnostic; deterministic verifier; autonomous loop |
| **Braintrust** | "quality management system," strong CI eval gates | deterministic grounding (not judge-default); auto-synthesized regression suites from real incidents |
| **Langfuse** | OSS observability (MIT), self-host | Cassandra is the *reliability/eval action layer*; can run **on** Langfuse |
| **Guardrails AI** | inline validators / guardrails | Cassandra is offline+continuous supervision & regression, not just inline blocking; complementary |

**The one-line wedge:** *everyone else helps you watch your agent; Cassandra catches the
failure, proves the fix deterministically, and stops it coming back — and it doesn't ask you
to take an LLM judge's word for it.*

### 4.6 Risks (named honestly)

- **Incumbents add the loop.** Arize/LangSmith/Braintrust could bolt on auto-remediation.
  Defense: the deterministic verifier + the owned data flywheel + being store-neutral.
- **"Just an API wrapper" commoditization.** The entire mitigation is `EVAL_PLAN.md` — if the
  core verdict stays an LLM call, this risk is fatal. If it's deterministic, it's a moat.
- **OSS sustainability / freeloading.** Standard open-core tension; mitigate with the
  hosted/governance split and not open-sourcing the team/enterprise plane.
- **Spec authoring friction.** The deterministic path needs a per-agent `GroundingSpec`.
  Mitigation: bundled specs for common agent shapes (support, RAG, ops), spec-authoring UX,
  and graceful fallback to the calibrated judge when no spec exists.

---

## 5. Sequencing (dependency-ordered; still no code)

1. **Decide the strategic forks in §6** (license, telemetry default, hosted-vs-self-host
   first, ICP). Everything else depends on these.
2. **Eval foundation** (`EVAL_PLAN.md` Phase A) — makes the product defensible. Do *before*
   any monetization claim.
3. **One vendor-neutral proof:** add the `TelemetryBackend` interface + a Langfuse adapter
   alongside Phoenix. Proves "not locked to Arize" to yourself and to buyers.
4. **Provider generalization** + self-hosted-model path.
5. **Demote ADK / containerize / broaden state.**
6. **Package the wedge** (CI gate as a GitHub Action; MCP server polish) → first design
   partners.
7. **Hosted plane** (dataset store, dashboards, team features) → first paid tier.

---

## 6. Decisions only you can make (answer these first)

1. **OSS license for the core** — recommend permissive (MIT/Apache) for adoption. Confirm.
2. **Default telemetry backend** — keep Phoenix (Arize story, but EL2.0/SaaS) vs. lead with
   **Langfuse/OTLP** (MIT, vendor-neutral). Recommend: support both, *default and market*
   vendor-neutral.
3. **Hosted-first or self-host-first?** Self-host-first builds trust + on-prem sales; hosted
   monetizes sooner. Recommend self-host OSS core + hosted paid plane in parallel.
4. **ICP / wedge** — which buyer first: platform/ML-eng (CI-gate wedge) or AI-product teams
   (supervision wedge)? Recommend CI-gate wedge → expand.
5. **Keep the GCP/Agent-Engine deployment as a supported adapter, or drop it post-contest?**
   Recommend keep as *optional* (cheap to maintain; nice for Vertex shops), default elsewhere.
6. **Brand/name + whether this stays "Cassandra"** for a commercial product.

---

*Both planning docs (`EVAL_PLAN.md`, this file) are review artifacts. Per your instruction, no
application code was changed; the repo's code state is exactly as you left it.*
