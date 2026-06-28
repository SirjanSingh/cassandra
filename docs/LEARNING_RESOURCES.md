# Cassandra v2 — Learning Resources (what to learn, and where)

> **Status:** study guide (2026-06-28), branch `cassandra-v2`. Companion to
> [`PROJECT_EXPLAINER.md`](PROJECT_EXPLAINER.md) (what the project *is*) and
> [`MARKET_AND_ALTERNATIVES.md`](MARKET_AND_ALTERNATIVES.md) (the decisions).
> **How to use it:** go top to bottom. Each section says *why you need it for Cassandra*, the
> **official docs** (always current), and **YouTube guidance** (channel names + exact search
> phrases — these stay valid even when individual videos get deleted; I deliberately don't list
> specific video URLs because those rot).

> A note on YouTube: search the **phrase in quotes** plus **"2026"** (or the current year) to
> get fresh results — this field moves fast and a 2023 tutorial is often already wrong.

---

## 0. Suggested order (don't learn it all — learn it in this sequence)

1. Python + async (you already use it — fill gaps) →
2. FastAPI (the web layer Cassandra + the Patient use) →
3. LLM app basics (prompts, structured output) →
4. **LiteLLM** (your chosen model layer) →
5. OpenTelemetry / tracing concepts →
6. **Langfuse** (your chosen telemetry backend) →
7. LLM evaluation + LLM-as-judge (the heart of Cassandra) →
8. Docker (to run it all) →
9. MCP + agents (your distribution surface + the broader context).

You can stop being a beginner at any layer and come back — the project already works; this is
about *understanding and extending* it.

---

## 1. Python + async/await
**Why:** all of Cassandra is async Python (`async def`, `await`). If `await` is fuzzy, the
pipeline code is hard to follow.
- Docs: https://docs.python.org/3/library/asyncio.html
- YouTube: channel **ArjanCodes** — search `"ArjanCodes asyncio"` and `"python async await explained"`. Also **Tech With Tim** → `"python asyncio tutorial 2026"`.

## 2. FastAPI
**Why:** the Patient (`patient/agent.py`) and dashboard (`dashboard/main.py`) are FastAPI apps;
endpoints like `/chat`, `/ask`, SSE all live here.
- Docs (excellent, beginner-friendly): https://fastapi.tiangolo.com/tutorial/
- YouTube: search `"FastAPI full course 2026"` (channel **freeCodeCamp**), and **ArjanCodes** → `"FastAPI best practices"`.

## 3. LLM application basics (prompts, structured output)
**Why:** Cassandra's `llm.py` has `structured()` (typed output via Pydantic) and `text()`.
Understanding prompts + JSON/structured output is core.
- Pydantic docs: https://docs.pydantic.dev/latest/
- YouTube: search `"LLM structured output pydantic 2026"`, `"prompt engineering crash course 2026"`. Channels: **freeCodeCamp**, **Underfitted**, **AI Jason**.

## 4. LiteLLM — your chosen model layer ✅
**Why:** v2 plan adopts LiteLLM as the single interface to 140+ model providers, replacing the
hand-rolled router in `llm.py`. Learn both the **SDK** (call from code) and the **Proxy**
(standalone gateway).
- Docs: https://docs.litellm.ai/docs/
- Proxy/gateway intro: https://docs.litellm.ai/docs/simple_proxy
- Repo (read the README — it's a good map): https://github.com/BerriAI/litellm
- YouTube: search `"LiteLLM tutorial 2026"`, `"LiteLLM proxy gateway"`. Also good explainer: https://a2a-mcp.org/blog/what-is-litellm
- Self-hosted models to pair with it later (§ self-hosted decision): **Ollama** (https://ollama.com — laptop) and **vLLM** (https://docs.vllm.ai — server). YouTube: `"Ollama tutorial 2026"`, `"vLLM serving tutorial"`.

## 5. OpenTelemetry & tracing concepts
**Why:** the universal "black box" standard. v2 makes Cassandra emit/read **OTLP** so it's
vendor-neutral. You need the vocabulary: *trace*, *span*, *attribute*, *exporter*.
- OTel for LLMs (start here): https://opentelemetry.io/blog/2024/llm-observability/
- OTel docs: https://opentelemetry.io/docs/
- **OpenInference** (the LLM-specific span conventions Phoenix/Langfuse use): https://github.com/Arize-ai/openinference
- YouTube: search `"OpenTelemetry explained 2026"`, `"distributed tracing for beginners"`. Channel **SigNoz** has practical OTel content.

## 6. Langfuse — your chosen telemetry backend ✅
**Why:** v2 plan leads with Langfuse (MIT-licensed → you can build a business on it) as the
store for the agent's traces, datasets, and prompts; Phoenix becomes one optional adapter.
- Get started: https://langfuse.com/docs/observability/get-started
- Self-hosting (Docker Compose, runs locally in minutes): https://langfuse.com/self-hosting/local
- Full self-host guide: https://langfuse.com/self-hosting
- LiteLLM → Langfuse integration (your two choices talking to each other): https://docs.litellm.ai/docs/observability/langfuse_otel_integration
- Practical 2026 walkthrough (Langfuse + vLLM): https://pyimagesearch.com/2026/05/18/llm-observability-with-self-hosted-langfuse-and-vllm/
- YouTube: search `"Langfuse tutorial 2026"`, `"Langfuse self host docker"`, `"Langfuse LLM observability"`. The **Langfuse** channel posts official walkthroughs.

## 7. LLM evaluation & LLM-as-judge (the heart of Cassandra)
**Why:** this is *what Cassandra does* — and `EVAL_PLAN.md` argues for replacing the fragile
LLM-judge with **deterministic** checks. To extend the project, understand both sides.
- DeepEval (read this to understand deterministic vs judge metrics): https://github.com/confident-ai/deepeval
- Opik eval concepts (heuristic vs LLM-judge): https://www.comet.com/docs/opik/
- Conceptual explainer: https://cameronrwolfe.substack.com/p/agent-evals
- "LLM-as-a-judge" overview: https://en.wikipedia.org/wiki/LLM-as-a-Judge
- YouTube: search `"LLM as a judge explained 2026"`, `"LLM evaluation tutorial"`, `"agent evaluation deepeval"`. Channels: **Confident AI**, **Weights & Biases**, **AI Engineer** (conference talks are gold here).
- **Read `EVAL_PLAN.md` in this repo alongside these** — it ties the theory to *your* code.

## 8. Docker & containers
**Why:** v2 plan = "one Dockerfile that runs anywhere" (drop GCP-specific deployment). You'll
run Langfuse via Docker Compose and ship Cassandra as a container.
- Docs: https://docs.docker.com/get-started/
- YouTube: search `"Docker crash course 2026"` (channels **TechWorld with Nana**, **freeCodeCamp**), `"docker compose tutorial"`.

## 9. MCP (Model Context Protocol) & agents (broader context)
**Why:** Cassandra ships its own MCP server (`cassandra-mcp`) — a key distribution surface
(usable inside Claude Desktop / Cursor). Plus general agent literacy helps.
- MCP intro: https://modelcontextprotocol.io/introduction
- YouTube: search `"Model Context Protocol explained 2026"`, `"build an MCP server"`. Channels: **AI Engineer**, **Matt Williams**, **Anthropic**.
- General agents landscape (skim, don't drown): https://github.com/ARUNAGIRINATHAN-K/awesome-ai-agents-2026

---

## 10. Highest-leverage starting point

If you only do three things this week:
1. **Langfuse local quickstart** (https://langfuse.com/self-hosting/local) — spin it up, send it
   one trace, click around. Makes "telemetry backend" concrete in 30 minutes.
2. **LiteLLM SDK quickstart** (https://docs.litellm.ai/docs/) — call two different models with
   one line each. Makes "provider independence" concrete.
3. **Read `EVAL_PLAN.md` + watch one "LLM as a judge" talk** — this is the idea your whole
   product is built on; everything else is plumbing around it.
</content>
