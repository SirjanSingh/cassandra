# Cassandra — Alternatives, Competition & Market Report

> **Status:** research brief (2026-06-28). No application code changed. Written on branch
> `research/alternatives-and-market`.
> **Purpose:** answer three questions you asked — (1) what can replace the things the
> hackathon *forced* you to use (Arize Phoenix, Vertex Gemini, GCP/ADK), (2) who else is in
> this market and what are their ideas, (3) how to make Cassandra better as a real tool people
> can use.
> **Read with:** [`PRODUCT_PLAN.md`](../PRODUCT_PLAN.md) (the independence/business plan) and
> [`EVAL_PLAN.md`](../EVAL_PLAN.md) (the deterministic-eval re-architecture that is the moat).

---

## 0. The one-paragraph summary

Everything the hackathon forced on you is **swappable**, and your codebase already has the
seams to swap them (`phoenix_mcp.py`, `llm.py`, `state.py`, `loop_agent.py`). The
observability/eval market is **crowded** (Langfuse, LangSmith, Braintrust, Arize, Opik,
Laminar, Helicone, DeepEval…), so "another tracing dashboard" is dead on arrival. The **only**
two players doing the thing closest to Cassandra's real idea — *autonomously fixing the agent,
not just watching it* — are **Braintrust** (CI eval gates + AI prompt optimization) and
**Comet Opik** (Agent Optimizer). Neither leads with **deterministic, telemetry-grounded
verification** the way `EVAL_PLAN.md` proposes. That gap — "stop trusting an LLM to grade your
LLM" + a closed detect→fix→verify→gate loop + an owned regression-dataset flywheel — is the
wedge. The decoupling work is what lets you *say* it credibly (vendor-neutral, runs on your
stack, runs on your own models).

---

## 1. Replacing the hackathon-forced dependencies

### 1.1 Arize Phoenix → telemetry backend you don't have to marry

**Why it's here:** Arize-track requirement. **The catch:** Phoenix OSS is **Elastic License
2.0** — source-available, *not* OSI open-source, and it **forbids offering it as a hosted
service**. Fine for the contest, a problem if you ever host a product on it.

| Option | License | Self-host | Why consider it | Notes |
|---|---|---|---|---|
| **Langfuse** | **MIT** | Yes (full parity) | The clean open-source default; OTLP-native; ClickHouse-backed; free self-host | Strongest fit for an open-core product — no resale restriction |
| **Arize Phoenix** | ELv2 | Yes (1 container) | Keeps the Arize story; ships **OpenInference**, the most-adopted OTel LLM span conventions | Keep as *one* adapter, not the foundation |
| **OpenLLMetry** (Traceloop) | Apache-2.0 | Yes | Pure OpenTelemetry instrumentation, one line of setup; vendor-neutral "OTLP out" | Use as the *emit* standard, ship spans anywhere |
| **Helicone** | Apache-2.0 | Yes | Proxy-based, very low-friction | Lighter than Langfuse |
| **Laminar** | Apache-2.0 | Yes | Agent-observability focused, data-volume pricing | Newer entrant |
| **Raw OTLP → ClickHouse / your store** | — | Yes | No extra SaaS at all | Maximum control, more to build |

**Recommendation:** instrument on **OpenTelemetry / OpenInference** (so the *producer* isn't
locked in), introduce the `TelemetryBackend` interface from `PRODUCT_PLAN.md §2.1`, and make
**Langfuse (MIT)** the default adapter while **keeping Phoenix as an option** for the Arize
narrative. This is the single most important decoupling for the "are we locked to Arize?"
objection.

- Langfuse vs Arize comparison: https://langfuse.com/faq/all/best-phoenix-arize-alternatives
- Phoenix alternatives roundup: https://laminar.sh/article/arize-phoenix-alternatives-2026
- Arize alternatives (Confident AI): https://www.confident-ai.com/knowledge-base/compare/top-arize-ai-alternatives-and-competitors-compared
- OTel/observability landscape (SigNoz): https://signoz.io/comparisons/llm-observability-tools/

### 1.2 Vertex Gemini → any provider, including your own models

**Why it's here:** the "must use Gemini" contest rule. **Lock-in risk: low** — `llm.py`
already routes OpenAI/OpenRouter/Vertex. To finish the job:

- **LiteLLM** — open-source gateway/proxy, one OpenAI-compatible interface to **140+
  providers / 2,500+ models**, plus cost tracking, fallbacks, load-balancing. ~40k stars.
  Either adopt it as your adapter layer or keep the hand-rolled router and mirror its protocol.
  https://github.com/BerriAI/litellm
- **Self-hosted / open-weights path** (the *enterprise sales unlock* — "no data leaves your
  VPC"):
  - **vLLM** — high-throughput inference server for open models (Llama/Mistral/Qwen).
  - **Ollama** — local/dev runtime.
  - These are **runtimes, not gateways** — put LiteLLM in front of them. A common production
    stack is **LiteLLM (routing) + vLLM (serving) + an observability tool**.

**Recommendation:** formalize the tiny `LLMProvider` protocol you already have, add a LiteLLM
adapter + a self-hosted-model path, and drop the Gemini-only assumption from docs/config
defaults once the contest no longer binds you. Keep the Vertex 429/503 backoff as
provider-specific config.

- LiteLLM 2026 guide: https://a2a-mcp.org/blog/what-is-litellm
- LLM gateway alternatives: https://contabo.com/blog/best-llm-gateways/

### 1.3 GCP / ADK / Agent Engine → containerize, demote ADK to optional

**Why it's here:** the "built with Agent Builder / Agent Engine" requirement. ADK is a thin
shell over your plain-Python `SupervisionPipeline` already.

- **ADK is Apache-2.0 and runs anywhere `pip install` works** — so you can keep it as an
  *optional* runtime adapter for Vertex shops without being GCP-bound. (Note: ADK hit GA on
  2026-05-19 with a v2.0 graph-based engine.)
- **Provider-agnostic frameworks** if you ever want to move off ADK: **LangGraph** (most
  battle-tested in production; explicit graph model), **CrewAI** (fastest to stand up,
  role-based), **AutoGen**, **Semantic Kernel**, **Smolagents**. All run anywhere Python runs.
- **Runtime/state:** replace the 5s in-process demo loop with a real worker/queue (keep
  in-process as `DEMO_MODE`); broaden `state.py` beyond Firestore/GCS to **Postgres + S3**;
  ship **one Dockerfile that runs on Cloud Run, ECS, Fly, Render, k8s, or on-prem**; drop the
  ngrok tunnel.

**Recommendation:** the business logic never imported ADK — preserve that. Default runtime =
plain container + scheduler; ADK/Agent Engine = optional adapter.

- Agent framework comparison: https://www.firecrawl.dev/blog/best-open-source-agent-frameworks
- ADK vs LangGraph vs CrewAI: https://1337skills.com/blog/2026-04-17-agent-framework-wars-google-adk-langchain-crewai-comparison/
- ADK vs LangGraph (ZenML): https://www.zenml.io/blog/google-adk-vs-langgraph

---

## 2. The competitive landscape (who else is here, and their ideas)

Think of the market as **three concentric rings**. Cassandra's ambition lives in the
innermost, least-crowded ring.

### Ring 1 — Observability / tracing (crowded, commoditized)
Watch the agent, store spans, show dashboards.

| Player | License / model | Their idea | Relevance to you |
|---|---|---|---|
| **Langfuse** | MIT, OSS + cloud | "LangSmith without the LangChain lock-in"; self-host | Best **backend to run *on*** (not compete with) |
| **LangSmith** | Commercial (LangChain) | Richest tracing for LangChain/LangGraph; annotation queues | Framework-coupled; you're framework-agnostic |
| **Arize (AX / Phoenix)** | Enterprise + ELv2 OSS | Enterprise observability; OpenInference standard | The track you entered; you *act* on telemetry, they watch it |
| **Helicone / Laminar / Lunary / Portkey** | Apache/MIT mixes | Proxy/observability, data-volume pricing | Lower-friction trace stores |

### Ring 2 — Evaluation frameworks (active, differentiated on *how* you grade)
Score outputs; some support CI gates.

| Player | Their idea | The interesting bit for Cassandra |
|---|---|---|
| **DeepEval** (Confident AI) | "Pytest for LLMs," 50+ metrics | **DAG metric = deterministic multi-step scoring that avoids LLM-judge non-determinism** — validates your `EVAL_PLAN.md` thesis directly |
| **Braintrust** | Eval-driven dev: tracing + evals + **CI/CD quality gates** + **AI prompt optimization** | **Closest to your loop.** Gates releases on evals; optimizes prompts automatically |
| **Comet Opik** | OSS observability + **Agent Optimizer (6 algorithms to auto-refine prompts/tools)** + heuristic *and* LLM-judge metrics | **The other closest competitor.** Explicitly splits **deterministic ("heuristic") vs LLM-as-judge** metrics |
| **MLflow / RAGAS / G-Eval** | Eval primitives | Building blocks, not products |

### Ring 3 — Autonomous detect→fix→verify (sparse — this is your lane)
Close the loop: not just *find* the regression, but *propose a fix, prove it, and gate it.*

- **Braintrust** and **Opik** are the only mainstream tools meaningfully in this ring, and
  both treat the **optimizer/judge as the product**.
- A wave of **"self-healing / self-evolving agent"** research and OSS exists but is mostly
  experimental, not productized: OpenAI's *Self-Evolving Agents* cookbook, Karpathy's 630-line
  autoresearch (Mar 2026), assorted "self-healing multi-agent" write-ups.
- **Nobody mainstream leads with deterministic, telemetry-grounded verification + an owned
  regression-dataset flywheel minted from real production incidents.** That is the open space.

**Sources:**
- LangSmith alternatives (Braintrust): https://www.braintrust.dev/articles/langsmith-alternatives-2026
- Opik repo: https://github.com/comet-ml/opik
- Opik product: https://www.comet.com/site/products/opik/
- DeepEval / deterministic vs judge: https://qalified.com/blog/top-llm-evaluation-tools/
- Eval tool roundup (no-vendor): https://techsy.io/en/blog/best-llm-evaluation-tools
- Top agent eval tools 2026: https://www.goodeyelabs.com/articles/top-ai-agent-evaluation-tools-2026
- Self-evolving agents (OpenAI cookbook): https://developers.openai.com/cookbook/examples/partners/self_evolving_agents/autonomous_agent_retraining
- Self-improving agents 2026 guide: https://o-mega.ai/articles/self-improving-ai-agents-the-2026-guide
- Awesome AI agents 2026 (landscape): https://github.com/ARUNAGIRINATHAN-K/awesome-ai-agents-2026

---

## 3. Where Cassandra wins (the honest positioning)

Everyone in Rings 1–2 **helps you watch** your agent. Cassandra's pitch is one sentence:

> **Everyone else helps you watch your agent. Cassandra catches the failure, proves the fix
> deterministically, and stops it coming back — and it doesn't ask you to take an LLM judge's
> word for it.**

Four things create the moat (none of which is "we call an LLM"):

1. **Deterministic, telemetry-grounded verification** (the `EVAL_PLAN.md` Grounding Verifier).
   The tool-call ledger is structured ground truth; the core verdict becomes *code, not a
   prompt*. This is the answer to both "how do you know the judge is right?" and "you're just
   an API wrapper." **Lead with this.** Note both Opik and DeepEval are *also* moving toward
   deterministic metrics — so this is validated as a direction, but you must move to stay ahead.
2. **The closed loop is a system, not a call** — detect → diagnose → root-cause → synthesize a
   regression dataset → score baseline vs candidate → patch → replay → red-team → gate.
3. **The data flywheel = switching cost** — every real incident becomes a permanent, versioned
   regression suite the customer owns. After months, that customer-specific corpus is the thing
   competitors can't replicate.
4. **Store- and provider-neutral** — runs *on* Langfuse/Phoenix/OTLP, against any model
   including self-hosted. Infrastructure, not a point tool.

---

## 4. How to make it a tool people actually use (prioritized)

**Tier 0 — credibility (must come first; see `EVAL_PLAN.md`).** Fix the production-path
tool-ledger gap (F1) and build the deterministic verifier. Until the load-bearing verdict is
*not* an LLM call, every claim above is unprovable. This is a prerequisite, not a feature.

**Tier 1 — the adoption wedge (lowest friction).**
- **CI gate as a GitHub Action / GitLab template** — "regression-test your prompts like code."
  This is how dev-infra companies land. Braintrust proves the demand for eval-gated releases.
- **Polish `cassandra-mcp`** — distribution inside Claude Desktop / Cursor where devs already
  are ("diagnose this turn").

**Tier 2 — independence proofs (make the pitch true).**
- Add the `TelemetryBackend` interface + a **Langfuse adapter** alongside Phoenix.
- Add a **LiteLLM / self-hosted-model** path.
- Containerize; demote ADK to optional.

**Tier 3 — product surface.**
- Self-serve onboarding: "point us at your OTLP endpoint + write a 20-line `GroundingSpec`."
- Multi-agent / multi-project; spec-authoring UX; hosted dashboards.
- The auto-postmortem artifact (you already generate these) is the "wow" demo for buyers.

**Business model:** open-core (MIT/Apache core = loop + MCP + gate + deterministic verifier;
paid = hosted, owned dataset store, team/RBAC/SSO, self-hosted-model enterprise, SLA). Meter on
the *verb that creates value* — "agents supervised" / "regression suites maintained" — not raw
spans, so you're not reselling storage like the observability incumbents. (Full detail in
`PRODUCT_PLAN.md §4`.)

---

## 5. Decisions this research surfaces (for you)

> **Decided 2026-06-28:** #1 → **Langfuse** (Phoenix kept as adapter); #2 → **LiteLLM**.
> Plain-language rationale for all five is in §7; the open ones (#3 self-hosted, #4 wedge, plus
> license/brand) have recommendations in [`PROJECT_EXPLAINER.md`](PROJECT_EXPLAINER.md) §7.

1. ✅ **Default telemetry backend** — **Langfuse/OTLP (MIT, vendor-neutral)**, Phoenix kept as
   an adapter. *(Decided.)*
2. ✅ **LLM layer** — adopt **LiteLLM** as the adapter. *(Decided.)*
3. **Self-hosted-model path now or later** — it's the enterprise unlock, but adds scope.
4. **Wedge** — CI-gate-first (platform/ML-eng buyers) vs supervision-loop-first (AI-product
   teams). Braintrust/Opik success suggests **CI-gate-first**.
5. **Differentiate fast** — Opik and DeepEval are already moving toward deterministic metrics.
   Your edge is the *combination* (deterministic verifier **+** autonomous fix/verify loop **+**
   owned flywheel **+** store-neutrality), not any single piece. Don't let the eval re-arch slip.

---

## 6. All links, by topic

**Phoenix / observability alternatives**
- https://langfuse.com/faq/all/best-phoenix-arize-alternatives
- https://laminar.sh/article/arize-phoenix-alternatives-2026
- https://www.confident-ai.com/knowledge-base/compare/top-arize-ai-alternatives-and-competitors-compared
- https://www.confident-ai.com/knowledge-base/compare/10-llm-observability-tools-to-evaluate-and-monitor-ai-2026
- https://signoz.io/comparisons/llm-observability-tools/
- https://www.firecrawl.dev/blog/best-llm-observability-tools
- https://laminar.sh/article/2026-04-23-top-6-agent-observability-platforms
- https://latitude.so/blog/best-ai-agent-observability-tools-2026-comparison
- https://glassbrain.dev/blog/arize-ai-alternatives

**Eval / agent-quality platforms (competitors)**
- https://www.braintrust.dev/articles/langsmith-alternatives-2026
- https://www.braintrust.dev/articles/best-llm-tracing-tools-2026
- https://www.braintrust.dev/articles/langfuse-alternatives-2026
- https://mlflow.org/top-5-agent-observability-tools/
- https://www.confident-ai.com/knowledge-base/compare/top-7-llm-observability-tools
- https://techsy.io/en/blog/best-llm-evaluation-tools
- https://www.goodeyelabs.com/articles/top-ai-agent-evaluation-tools-2026
- https://qalified.com/blog/top-llm-evaluation-tools/

**Opik / DeepEval / deterministic eval (closest ideas)**
- https://github.com/comet-ml/opik
- https://www.comet.com/site/products/opik/
- https://www.comet.com/docs/opik/
- https://trilogyequity.com/blog/comet-opik-open-source-lllm-evals/

**Autonomous / self-healing agents (the lane)**
- https://developers.openai.com/cookbook/examples/partners/self_evolving_agents/autonomous_agent_retraining
- https://o-mega.ai/articles/self-improving-ai-agents-the-2026-guide
- https://github.com/ARUNAGIRINATHAN-K/awesome-ai-agents-2026
- https://github.com/ai-boost/awesome-harness-engineering

**LLM provider / runtime independence**
- https://github.com/BerriAI/litellm
- https://a2a-mcp.org/blog/what-is-litellm
- https://contabo.com/blog/best-llm-gateways/
- https://pinggy.io/blog/best_ai_llm_routers_openrouter_alternatives/

**Agent frameworks (ADK alternatives)**
- https://www.firecrawl.dev/blog/best-open-source-agent-frameworks
- https://www.langchain.com/resources/ai-agent-frameworks
- https://1337skills.com/blog/2026-04-17-agent-framework-wars-google-adk-langchain-crewai-comparison/
- https://www.zenml.io/blog/google-adk-vs-langgraph
- https://www.requesty.ai/blog/best-ai-agent-sdks-compared-2026-langchain-crewai-openai-anthropic-google

---

## 7. The five decisions explained in plain language (no jargon)

These restate §5's five decisions for a non-specialist reader: what the term means, what the
project does *today*, and what actually changes if you choose differently.

**Background terms used below:**
- **Telemetry** = the record of what the supervised agent did (what it was asked, what it
  answered, which tools it called). A **flight recorder / black box** for the agent. Cassandra
  reads this to find failures.
- **Backend** = the database/service where that black-box data is stored.
- **Adapter** = a small piece of code that lets the project talk to one specific outside
  service — like a **travel power-plug adapter**: same device, different socket. Building
  around adapters means you can swap the vendor without rebuilding Cassandra.

### 7.1 Default telemetry backend — Langfuse vs Phoenix
- **What it is:** which service stores the agent's black-box data by default.
- **Today:** wired to **Arize Phoenix** (hackathon required it).
- **Problem:** Phoenix's license (Elastic License 2.0) **legally forbids selling it as a
  hosted service** — fine for a contest, a wall for a paid hosted product.
- **The choice:** **Langfuse** is **MIT-licensed** — legally free to build a business on.
  **OTLP** is just the *universal standard format* for this data (like PDF for documents); if
  Cassandra speaks OTLP it can plug into almost anything.
- **What changing it does:** make Cassandra speak the universal standard and treat Phoenix as
  one swappable plug. ⇒ you can legally sell it, and tell customers "we work with whatever you
  already use." **Recommended.**

### 7.2 LLM layer — LiteLLM vs hand-rolled router
- **What it is:** the code that actually calls the AI model. A **router** picks *which* model
  each request goes to.
- **Today:** a **hand-rolled router** you wrote (switches Gemini / OpenAI / OpenRouter). Works,
  but knows few providers and you maintain it.
- **The choice:** **LiteLLM** is a free off-the-shelf tool already connecting to **140+
  providers** through one interface.
- **What changing it does:** *Adopt LiteLLM* → instantly support almost every model + free
  extras (cost tracking, automatic fallback) but adds an outside dependency. *Keep hand-rolled*
  → stays lightweight and fully under your control, but you add each new provider yourself. A
  "convenience vs. lightness" trade; LiteLLM usually wins for a product aiming wide.

### 7.3 Self-hosted-model path — now or later
- **What it is:** running the AI model **on your/the customer's own computers** instead of
  calling Google/OpenAI's cloud. Tools: **vLLM** (server-grade), **Ollama** (laptop-grade).
- **Today:** Cassandra only talks to *cloud* AI (Vertex Gemini); every request leaves the
  machine.
- **Why it matters:** regulated buyers (banks, hospitals, government) often **legally can't
  let data leave their network**. "Runs entirely inside your walls, nothing goes out" unlocks
  expensive enterprise deals — the **enterprise unlock**.
- **What changing it does:** *Now* → can pitch enterprise immediately, but it's extra work
  before you have customers. *Later* → stay focused on the core, add it when a real enterprise
  lead asks. Purely a *timing* call; "later" is the safe default unless a buyer is knocking.

### 7.4 Wedge — CI-gate-first vs supervision-loop-first
- **What it is:** the **wedge** = the first, smallest thing you get people to adopt — the foot
  in the door. Sell one easy win, then expand.
- **CI-gate-first:** "CI" is the automated check that runs whenever a developer changes code; a
  "gate" passes/fails it. So: *"add Cassandra to your pipeline and it blocks prompt changes
  that make your agent worse — spell-check for AI quality before release."* Low effort to try;
  appeals to engineering/platform teams.
- **Supervision-loop-first:** lead with the full autonomous system that watches the *live*
  agent and fixes failures. Higher value, bigger ask, appeals to AI-product teams.
- **What changing it does:** changes **who you target and what you polish first**. Nothing is
  deleted — it's sequencing + marketing emphasis. **CI-gate-first recommended** because
  Braintrust and Opik (closest competitors) won doing exactly that.

### 7.5 Differentiate fast — don't let the eval re-architecture slip
- **What it is:** "differentiate" = what makes you clearly *not* a copy. "Eval
  re-architecture" = the rebuild in [`EVAL_PLAN.md`](../EVAL_PLAN.md) that makes Cassandra's
  core judgment **deterministic** (same input → same provable answer, like a calculator)
  instead of asking an LLM (which can vary and can't prove it's right). Instead of asking an AI
  "did the agent lie?", you **check the agent's actual tool records** — facts, not opinions.
- **The warning:** **Opik** and **DeepEval** are *already* adding deterministic checks, so that
  one idea alone won't stay unique.
- **What this means:** the hard-to-copy advantage is the **whole combination**: (1)
  deterministic verifier + (2) the autonomous fix-and-verify loop + (3) the "flywheel" (every
  real failure caught becomes a permanent test the customer *owns*) + (4) store-neutrality. No
  competitor has all four. **"Don't let it slip"** = finish the combination soon; each piece
  alone is being copied, only the *bundle* is the moat.

**Through-line:** §7.1–7.3 = *stop being locked to what the hackathon forced* (Phoenix, Gemini,
cloud-only) so Cassandra is flexible and sellable. §7.4–7.5 = *pick your entry point and move
fast on the one thing that makes you special.*
</content>
</invoke>
